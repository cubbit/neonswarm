"""
TCP sniffer that fires a callback when a byte threshold is crossed within
an inactivity window.

Design notes
------------
* All K8s pod-to-pod traffic on a node flows through the ``cni0`` bridge
  before VXLAN encapsulation, so sniffing on ``cni0`` yields raw TCP and
  structurally excludes external NodePort traffic, Netbird (``100.64/10``),
  and LAN (``192.168/16``). The BPF filter then restricts both source and
  destination to the flannel pod CIDR for a second belt-and-braces layer.
* Packet counting is delegated to :class:`ByteAccumulator` so the hot-path
  state machine is unit-testable without scapy.
* Callbacks are invoked **outside** the lock. The previous design held the
  accumulator lock while calling the user callback, which deadlocked the
  inactivity timer when the callback blocked on I/O.
* Inactivity detection is polled from the supervisor loop (1 Hz) via
  ``ByteAccumulator.tick``, removing the per-packet ``threading.Timer``
  thread churn of the old implementation.
* The sniffer is supervised: ``run_forever`` catches exceptions from scapy
  and restarts the capture with exponential backoff. Only a shutdown event
  breaks the loop cleanly.
"""

import logging
import os
import time
from pathlib import Path
from threading import Event
from typing import Callable

from scapy.all import sniff, TCP, IP

from utils.loggable import Loggable

from threshold_sniffer.byte_accumulator import ByteAccumulator

# Default CNI bridge on K3s/flannel. Configurable via --interface.
DEFAULT_INTERFACE = "cni0"

# Default flannel pod CIDR on K3s. Configurable via --pod-cidr.
DEFAULT_POD_CIDR = "10.42.0.0/16"

# How often the supervisor polls the accumulator for inactivity. The
# inactivity timeout is a caller-supplied separate knob; this just bounds
# the resolution.
_INACTIVITY_POLL_INTERVAL_S = 1.0

# Health marker path. Touched on every supervisor iteration (success or
# error) so a Kubernetes liveness probe can distinguish a running loop
# from a hung one.
_HEALTH_FILE = Path("/tmp/healthy")

# Backoff for scapy restart after a capture error.
_CAPTURE_RESTART_BASE_DELAY_S = 1.0
_CAPTURE_RESTART_MAX_DELAY_S = 30.0


class ThresholdSniffer(Loggable):
    """
    Sniffs TCP traffic on a configured interface, counts payload bytes from
    packets matching the filter, and fires ``on_start`` / ``on_stop``
    callbacks around a threshold-crossed window.
    """

    def __init__(
        self,
        port: int | None,
        threshold_bytes: int,
        inactivity_timeout_s: float,
        size_filter_bytes: int | None,
        host: str | None = None,
        iface: str | None = None,
        pod_cidr: str = DEFAULT_POD_CIDR,
        log_level: int = logging.INFO,
    ) -> None:
        """
        Args:
            port: Optional TCP port to restrict the capture to. ``None``
                captures any TCP port (recommended for cluster-wide
                pod-to-pod tracking).
            threshold_bytes: Byte count that triggers ``on_start``.
            inactivity_timeout_s: Seconds of no qualifying packets before
                firing ``on_stop`` and resetting the counter.
            size_filter_bytes: Minimum TCP payload size to count.
                Packets below this size are ignored in the Python layer
                (the BPF ``greater`` clause already drops most, but TCP
                segment payloads are computed after the IP+TCP headers so
                this is the final authoritative check).
            host: Optional IP to restrict the filter (``host <ip>`` in
                BPF). Rarely needed when ``pod_cidr`` is set.
            iface: Interface to sniff. Defaults to ``cni0``.
            pod_cidr: Flannel pod CIDR. Both source and destination must
                be in this range for a packet to be counted.
            log_level: Python logging level.
        """
        super().__init__(log_level)

        self._port = port
        self._host = host
        self._iface = iface or DEFAULT_INTERFACE
        self._pod_cidr = pod_cidr
        self._size_filter_bytes = size_filter_bytes or 0
        self._threshold_bytes = threshold_bytes
        self._inactivity_timeout_s = inactivity_timeout_s

        self._accumulator = ByteAccumulator(
            threshold_bytes=threshold_bytes,
            inactivity_timeout_s=inactivity_timeout_s,
        )

        self._stop_event = Event()

        # Caller-assigned callbacks. Called from whichever thread fires
        # them (the scapy capture thread for ``on_start``, the supervisor
        # thread for ``on_stop``). The accumulator's internal lock is
        # released before invocation so callbacks may block.
        self.on_start_sniffing: Callable[[], None] | None = None
        self.on_stop_sniffing: Callable[[], None] | None = None

    # ---- packet path ----------------------------------------------------

    def _handle_packet(self, packet) -> None:
        """Called by scapy for each packet matching the BPF filter."""
        if IP not in packet or TCP not in packet:
            return

        try:
            payload_len = len(packet[TCP].payload)
            if payload_len < self._size_filter_bytes:
                return

            self.logger.debug(
                "%s:%s → %s:%s | flags=%s | payload=%d bytes",
                packet[IP].src,
                packet[TCP].sport,
                packet[IP].dst,
                packet[TCP].dport,
                packet[TCP].flags,
                payload_len,
            )

            transition = self._accumulator.add(payload_len)
            if transition.started:
                self.logger.info(
                    "threshold crossed: %d bytes in flight", transition.total_bytes
                )
                self._fire(self.on_start_sniffing, "on_start_sniffing")

        except Exception:
            # The scapy capture thread must never die from a packet
            # handler error — log and keep going.
            self.logger.exception("error processing packet")

    # ---- supervisor -----------------------------------------------------

    def run_forever(self) -> None:
        """
        Main entry point. Runs the scapy capture and polls the accumulator
        for inactivity in a single foreground thread. Restarts the capture
        with exponential backoff on errors. Exits cleanly on
        :meth:`request_stop`.
        """
        bpf_filter = self._build_bpf_filter()
        self.logger.info(
            "starting capture: iface=%s filter=%r threshold=%d bytes inactivity=%.1fs",
            self._iface,
            bpf_filter,
            self._threshold_bytes,
            self._inactivity_timeout_s,
        )

        if os.geteuid() != 0:
            self.logger.warning(
                "running without root privileges — capture may be incomplete"
            )

        attempt = 0
        try:
            while not self._stop_event.is_set():
                self._touch_health()
                try:
                    sniff(
                        iface=self._iface,
                        filter=bpf_filter,
                        prn=self._handle_packet,
                        store=False,
                        timeout=_INACTIVITY_POLL_INTERVAL_S,
                        stop_filter=lambda _pkt: self._stop_event.is_set(),
                    )
                    # Each sniff() timeout is a supervisor tick.
                    self._tick()
                    attempt = 0  # clean exit from sniff() resets backoff
                except (KeyboardInterrupt, SystemExit):
                    self.logger.info("shutdown requested from capture")
                    self._stop_event.set()
                    break
                except Exception:
                    attempt += 1
                    delay = min(
                        _CAPTURE_RESTART_MAX_DELAY_S,
                        _CAPTURE_RESTART_BASE_DELAY_S * (2 ** (attempt - 1)),
                    )
                    self.logger.exception(
                        "capture error (attempt %d), restarting in %.1fs",
                        attempt,
                        delay,
                    )
                    # Touch the health file before and after the wait so the
                    # liveness probe does not race us during max backoff (30s).
                    self._touch_health()
                    self._stop_event.wait(delay)
                    self._touch_health()
        finally:
            # Shutdown path — guaranteed to run even if a BaseException
            # (KeyboardInterrupt, SystemExit) or an unexpected error
            # escapes the inner loop. This is how the LEDs reliably turn
            # off on shutdown.
            if self._accumulator.is_active:
                self._fire(self.on_stop_sniffing, "on_stop_sniffing")
            self._accumulator.reset()
            self.logger.info("sniffer loop exited cleanly")

    def _tick(self) -> None:
        """Check the accumulator for inactivity and touch the health file."""
        transition = self._accumulator.tick()
        if transition.stopped:
            self.logger.info("inactivity window elapsed, stopping animation")
            self._fire(self.on_stop_sniffing, "on_stop_sniffing")
        self._touch_health()

    def request_stop(self) -> None:
        """Request a clean shutdown. Safe to call from any thread."""
        self._stop_event.set()

    # ---- BPF construction -----------------------------------------------

    def _build_bpf_filter(self) -> str:
        """
        Build a BPF expression that only matches traffic we care about:

        * TCP only (excludes UDP, ICMP, etc.)
        * Both endpoints inside the flannel pod CIDR (``10.42.0.0/16``
          by default) — structurally excludes NodePort, Netbird, LAN.
        * Optionally restricted to a specific source port or host.

        The deliberately absent clauses from the previous filter are:

        * ``tcp[13] & 0x08 != 0`` (PSH flag) — this was wrong. Most bulk
          data segments do not carry PSH; only the last segment of each
          application write does. Filtering on PSH under-counted real
          downloads and over-counted small control responses.
        * ``greater N`` raw packet length — rejected in favour of the
          Python-layer payload-size check in ``_handle_packet``, which is
          authoritative (BPF sees the IP packet length including headers,
          which is only loosely correlated with the TCP payload size).
        """
        parts = [
            "tcp",
            f"src net {self._pod_cidr}",
            f"dst net {self._pod_cidr}",
        ]
        if self._port is not None:
            parts.append(f"src port {self._port}")
        if self._host:
            parts.append(f"host {self._host}")
        return " and ".join(parts)

    # ---- helpers --------------------------------------------------------

    def _fire(self, callback: Callable[[], None] | None, name: str) -> None:
        """Invoke a user callback out-of-lock, swallowing exceptions."""
        if callback is None:
            return
        try:
            callback()
        except Exception:
            self.logger.exception("%s callback raised", name)

    def _touch_health(self) -> None:
        """Update the liveness probe marker."""
        try:
            _HEALTH_FILE.touch(exist_ok=True)
        except Exception:
            self.logger.warning("failed to touch health file %s", _HEALTH_FILE)
