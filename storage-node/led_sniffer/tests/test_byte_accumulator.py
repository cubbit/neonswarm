"""Tests for ByteAccumulator — pure logic, no hardware deps."""

import pytest

from threshold_sniffer.byte_accumulator import (
    AccumulatorTransition,
    ByteAccumulator,
)


class TestConstruction:
    def test_rejects_zero_threshold(self):
        with pytest.raises(ValueError):
            ByteAccumulator(threshold_bytes=0, inactivity_timeout_s=1.0)

    def test_rejects_negative_threshold(self):
        with pytest.raises(ValueError):
            ByteAccumulator(threshold_bytes=-1, inactivity_timeout_s=1.0)

    def test_rejects_zero_timeout(self):
        with pytest.raises(ValueError):
            ByteAccumulator(threshold_bytes=100, inactivity_timeout_s=0)


class TestAdd:
    def test_no_transition_below_threshold(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        t = acc.add(500, now=0.0)
        assert t == AccumulatorTransition(started=False, stopped=False, total_bytes=500)
        assert acc.is_active is False

    def test_transition_started_when_threshold_crossed(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        t1 = acc.add(600, now=0.0)
        assert t1.started is False
        t2 = acc.add(500, now=0.1)
        assert t2.started is True
        assert t2.total_bytes == 1100
        assert acc.is_active is True

    def test_transition_started_fires_only_once(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        acc.add(1500, now=0.0)
        t = acc.add(500, now=0.1)
        assert t.started is False
        assert t.total_bytes == 2000
        assert acc.is_active is True

    def test_ignores_zero_byte_count(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        t = acc.add(0, now=0.0)
        assert t == AccumulatorTransition(total_bytes=0)
        assert acc.is_active is False

    def test_ignores_negative_byte_count(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        acc.add(500, now=0.0)
        t = acc.add(-100, now=0.1)
        assert t.total_bytes == 500  # unchanged


class TestTick:
    def test_tick_while_idle_is_noop(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        t = acc.tick(now=100.0)
        assert t == AccumulatorTransition(total_bytes=0)

    def test_tick_while_active_within_window_is_noop(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        acc.add(1500, now=0.0)
        t = acc.tick(now=3.0)  # 3s < 5s timeout
        assert t.stopped is False
        assert acc.is_active is True

    def test_tick_fires_stopped_after_inactivity_window(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        acc.add(1500, now=0.0)
        t = acc.tick(now=6.0)
        assert t.stopped is True
        assert t.total_bytes == 0
        assert acc.is_active is False

    def test_tick_stopped_resets_counter(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        acc.add(1500, now=0.0)
        acc.tick(now=6.0)
        assert acc.total_bytes == 0

        # New activity after reset should restart the state machine.
        t = acc.add(500, now=7.0)
        assert t.started is False
        t2 = acc.add(600, now=7.1)
        assert t2.started is True

    def test_activity_pushes_inactivity_deadline(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        acc.add(1500, now=0.0)

        # 3s later — still active
        acc.add(100, now=3.0)
        t = acc.tick(now=7.5)  # 7.5 - 3.0 = 4.5s < 5s
        assert t.stopped is False
        assert acc.is_active is True

        # Another 5.1s with no activity
        t = acc.tick(now=12.6)  # 12.6 - 3.0 = 9.6s > 5s
        assert t.stopped is True

    def test_sub_threshold_bytes_are_reset_after_inactivity(self):
        """
        A burst of bytes that never reaches the threshold must be garbage
        collected after the inactivity window so it cannot combine with a
        much-later unrelated packet to fire a spurious 'started'.
        """
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        acc.add(500, now=0.0)
        assert acc.is_active is False
        assert acc.total_bytes == 500

        # Long gap — no tick fires stopped (never became active) but the
        # idle sub-threshold bytes are dropped.
        t = acc.tick(now=100.0)
        assert t.stopped is False   # never was active
        assert t.total_bytes == 0
        assert acc.total_bytes == 0

        # A later small packet cannot tip into 'started' because the
        # earlier bytes are gone.
        t2 = acc.add(600, now=100.1)
        assert t2.started is False
        assert t2.total_bytes == 600

    def test_threshold_of_one_byte_triggers_immediately(self):
        acc = ByteAccumulator(threshold_bytes=1, inactivity_timeout_s=1.0)
        t = acc.add(1, now=0.0)
        assert t.started is True
        assert t.total_bytes == 1


class TestReset:
    def test_reset_clears_state(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        acc.add(1500, now=0.0)
        assert acc.is_active is True

        acc.reset()
        assert acc.is_active is False
        assert acc.total_bytes == 0

    def test_add_after_reset_rebuilds_from_zero(self):
        acc = ByteAccumulator(threshold_bytes=1000, inactivity_timeout_s=5)
        acc.add(1500, now=0.0)
        acc.reset()

        t = acc.add(500, now=1.0)
        assert t.started is False
        assert t.total_bytes == 500
