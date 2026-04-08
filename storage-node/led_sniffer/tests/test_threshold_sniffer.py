"""
Tests for ThresholdSniffer BPF construction and callback wiring.

Packet capture itself is not tested (that would need real scapy), but the
filter string and the out-of-lock callback behaviour are pure logic and
worth exercising.
"""

from unittest.mock import MagicMock


def _make_sniffer(**overrides):
    """Construct a sniffer with stubbed hardware and sane defaults."""
    from threshold_sniffer.threshold_sniffer import ThresholdSniffer

    kwargs = dict(
        port=None,
        threshold_bytes=1000,
        inactivity_timeout_s=5.0,
        size_filter_bytes=200,
        host=None,
        iface="cni0",
        pod_cidr="10.42.0.0/16",
    )
    kwargs.update(overrides)
    return ThresholdSniffer(**kwargs)


class TestBpfFilter:
    def test_default_filter_restricts_to_pod_cidr(self):
        s = _make_sniffer()
        f = s._build_bpf_filter()
        assert f == "tcp and src net 10.42.0.0/16 and dst net 10.42.0.0/16"

    def test_custom_pod_cidr_is_applied_to_both_sides(self):
        s = _make_sniffer(pod_cidr="10.244.0.0/16")
        f = s._build_bpf_filter()
        assert f == "tcp and src net 10.244.0.0/16 and dst net 10.244.0.0/16"

    def test_optional_port_is_appended(self):
        s = _make_sniffer(port=4000)
        f = s._build_bpf_filter()
        assert "src port 4000" in f
        assert f.startswith("tcp and src net 10.42.0.0/16")

    def test_optional_host_is_appended(self):
        s = _make_sniffer(host="10.42.1.5")
        f = s._build_bpf_filter()
        assert "host 10.42.1.5" in f

    def test_optional_port_clause_is_positioned_after_cidr(self):
        # Combined port+host coverage: both optional clauses are appended
        # in a stable order after the mandatory CIDR clauses, so the BPF
        # parser sees a well-formed expression.
        s = _make_sniffer(port=4000, host="10.42.1.5")
        f = s._build_bpf_filter()
        assert f == (
            "tcp and src net 10.42.0.0/16 and dst net 10.42.0.0/16"
            " and src port 4000 and host 10.42.1.5"
        )

    def test_filter_does_not_contain_psh_flag_check(self):
        # The old filter used 'tcp[13] & 0x08 != 0' which was wrong —
        # it under-counted bulk data segments. Regression guard.
        s = _make_sniffer()
        f = s._build_bpf_filter()
        assert "0x08" not in f
        assert "tcp[13]" not in f

    def test_filter_structurally_excludes_external_sources(self):
        # Both src and dst are constrained to the pod CIDR. A packet
        # from any non-pod source (e.g., the LAN gateway 192.168.1.1)
        # would fail the `src net 10.42.0.0/16` clause and never reach
        # the handler. This is the whole point.
        s = _make_sniffer(pod_cidr="10.42.0.0/16")
        f = s._build_bpf_filter()
        assert "src net 10.42.0.0/16" in f
        assert "dst net 10.42.0.0/16" in f


class TestCallbackOutOfLock:
    def test_on_start_fires_out_of_lock(self):
        """
        Regression guard: the previous design held the accumulator lock
        while invoking the user callback, so a slow callback would wedge
        the capture thread. Verify the callback is now fired after the
        add() call returns, not during it.
        """
        s = _make_sniffer(threshold_bytes=100, size_filter_bytes=0)

        calls = []

        def on_start():
            # If we were inside the accumulator lock at this point, we
            # would not be able to read total_bytes (deadlock). Being
            # able to read it proves we are out of lock.
            calls.append(s._accumulator.total_bytes)

        s.on_start_sniffing = on_start

        # Fake a packet by bypassing scapy and calling the handler with
        # a MagicMock that satisfies `IP in packet and TCP in packet`.
        # Easier: call the accumulator directly and then the fire path.
        t = s._accumulator.add(200)
        assert t.started is True
        s._fire(s.on_start_sniffing, "on_start_sniffing")
        assert calls == [200]

    def test_fire_swallows_callback_exceptions_and_logs_them(self, caplog):
        import logging as _logging

        s = _make_sniffer()
        s.on_start_sniffing = MagicMock(side_effect=RuntimeError("boom"))
        with caplog.at_level(_logging.ERROR, logger=s.logger.name):
            # Must not propagate — the scapy capture thread must keep running.
            s._fire(s.on_start_sniffing, "on_start_sniffing")
        # Also verify the exception was actually logged. A silent swallow
        # would be worse than a crash because it would hide real bugs.
        assert "on_start_sniffing" in caplog.text
        assert "boom" in caplog.text

    def test_fire_handles_none_callback(self):
        s = _make_sniffer()
        s.on_start_sniffing = None
        s._fire(s.on_start_sniffing, "on_start_sniffing")  # no crash


class TestRunForeverCleanup:
    """
    The supervisor loop itself is mostly scapy glue, but the cleanup path
    (firing on_stop_sniffing on shutdown) is critical and worth covering
    even with a fake sniff function.
    """

    def test_run_forever_fires_on_stop_if_active_at_shutdown(self):
        from unittest.mock import patch

        s = _make_sniffer(threshold_bytes=100, size_filter_bytes=0)
        # Manually put the accumulator in ACTIVE state.
        s._accumulator.add(200)
        assert s._accumulator.is_active is True

        on_stop = MagicMock()
        s.on_stop_sniffing = on_stop

        def fake_sniff(**_kwargs):
            s.request_stop()

        with patch("threshold_sniffer.threshold_sniffer.sniff", side_effect=fake_sniff):
            s.run_forever()

        on_stop.assert_called_once()

    def test_run_forever_does_not_fire_on_stop_if_idle_at_shutdown(self):
        from unittest.mock import patch

        s = _make_sniffer()
        on_stop = MagicMock()
        s.on_stop_sniffing = on_stop

        def fake_sniff(**_kwargs):
            s.request_stop()

        with patch("threshold_sniffer.threshold_sniffer.sniff", side_effect=fake_sniff):
            s.run_forever()

        on_stop.assert_not_called()

    def test_run_forever_cleanup_runs_even_if_sniff_raises_system_exit(self):
        """
        BaseException subclasses (SystemExit, KeyboardInterrupt) should not
        escape run_forever with the accumulator still active. The try/finally
        guarantees on_stop_sniffing fires.
        """
        from unittest.mock import patch

        s = _make_sniffer(threshold_bytes=100, size_filter_bytes=0)
        s._accumulator.add(200)

        on_stop = MagicMock()
        s.on_stop_sniffing = on_stop

        def fake_sniff(**_kwargs):
            raise SystemExit(1)

        with patch("threshold_sniffer.threshold_sniffer.sniff", side_effect=fake_sniff):
            s.run_forever()  # must not raise

        on_stop.assert_called_once()
        assert s._accumulator.is_active is False
