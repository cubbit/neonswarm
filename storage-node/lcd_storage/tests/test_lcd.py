"""Tests for LCDController frame diffing logic (with stubbed CharLCD)."""

from unittest.mock import MagicMock, patch

import pytest


def _make_controller():
    """Build an LCDController with a mocked CharLCD backend."""
    # Import inside the function so the conftest stubs are fully in place.
    from lcd.lcd import LCDController

    with patch("lcd.lcd.CharLCD") as fake_cls:
        fake = MagicMock()
        fake_cls.return_value = fake
        ctrl = LCDController(i2c_addr=0x27)
        # Replace the instance's backing LCD with our mock for assertions.
        ctrl._lcd = fake
        return ctrl, fake


class TestWriteDiffing:
    def test_first_write_performs_clear_and_writes_all_rows(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])

        fake.clear.assert_called_once()
        assert fake.write_string.call_count == 2
        # First frame is cached
        assert ctrl._last_frame == ["hello", "world"]

    def test_identical_second_write_is_noop(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])
        fake.reset_mock()

        ctrl.write(["hello", "world"])

        fake.clear.assert_not_called()
        fake.write_string.assert_not_called()

    def test_partial_change_writes_only_changed_row(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])
        fake.reset_mock()

        ctrl.write(["hello", "earth"])

        fake.clear.assert_not_called()
        assert fake.write_string.call_count == 1

    def test_force_triggers_full_rewrite_even_if_same(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])
        fake.reset_mock()

        ctrl.write(["hello", "world"], force=True)

        fake.clear.assert_called_once()
        assert fake.write_string.call_count == 2

    def test_row_count_change_triggers_full_rewrite(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])
        fake.reset_mock()

        ctrl.write(["just one"])

        fake.clear.assert_called_once()
        assert fake.write_string.call_count == 1

    def test_written_lines_are_padded_to_full_width(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hi", "bye"])

        # Every write_string call should receive a 16-char padded string.
        for call in fake.write_string.call_args_list:
            arg = call.args[0]
            assert len(arg) == ctrl.COLS, f"{arg!r} is not padded to {ctrl.COLS}"

    def test_string_input_accepted(self):
        ctrl, fake = _make_controller()
        ctrl.write("single line")
        assert ctrl._last_frame == ["single line"]

    def test_too_many_rows_raises(self):
        ctrl, _ = _make_controller()
        with pytest.raises(ValueError):
            ctrl.write(["a", "b", "c"])

    def test_clear_resets_cache(self):
        ctrl, fake = _make_controller()
        ctrl.write(["hello", "world"])
        ctrl.clear()
        assert ctrl._last_frame == []
        fake.reset_mock()

        # Next write should be a full rewrite, not a no-op.
        ctrl.write(["hello", "world"])
        fake.clear.assert_called_once()
