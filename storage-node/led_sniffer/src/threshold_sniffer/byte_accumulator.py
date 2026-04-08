"""
Pure-Python byte accumulator with threshold and inactivity semantics.

Extracted from ``threshold_sniffer.py`` so the hot-path logic can be unit
tested without importing scapy or touching real packets.

State machine
-------------
- IDLE: ``total_bytes = 0``, not "active".
- add(n) increases ``total_bytes``. If it crosses the configured threshold
  and we are not yet active, the state transitions to ACTIVE and the
  caller is expected to fire the "started" side-effect.
- If no packet arrives within ``inactivity_timeout_s`` the state goes back
  to IDLE and the caller fires the "stopped" side-effect.

The accumulator itself does **not** own the timer or the side effects. It
just returns structured verdicts from ``add`` / ``tick`` which the caller
uses to drive the external actions (timer, LED strip, logging). This split
is what makes it unit-testable.
"""

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class AccumulatorTransition:
    """
    What happened as a result of an ``add`` or ``tick`` call.

    Exactly one of ``started`` / ``stopped`` can be True per call; both can
    also be False (no state change).
    """

    started: bool = False
    stopped: bool = False
    total_bytes: int = 0


class ByteAccumulator:
    """
    Thread-safe counter that fires a one-shot "started" transition when the
    accumulated byte count first crosses a threshold, and a "stopped"
    transition after a period of inactivity.

    All public methods are safe to call from multiple threads; the internal
    lock is released before returning the transition so callers can safely
    invoke blocking side-effects (LED writes, logging) without holding it.
    """

    def __init__(self, threshold_bytes: int, inactivity_timeout_s: float) -> None:
        if threshold_bytes <= 0:
            raise ValueError("threshold_bytes must be positive")
        if inactivity_timeout_s <= 0:
            raise ValueError("inactivity_timeout_s must be positive")

        self._threshold = threshold_bytes
        self._timeout = inactivity_timeout_s
        self._lock = threading.Lock()
        self._total = 0
        self._active = False
        self._last_packet_time: float | None = None

    def add(self, byte_count: int, *, now: float | None = None) -> AccumulatorTransition:
        """
        Record ``byte_count`` bytes at time ``now`` (defaults to ``time.monotonic()``).

        Returns a transition describing the state change, if any.
        """
        if byte_count <= 0:
            return AccumulatorTransition(total_bytes=self.total_bytes)

        at = time.monotonic() if now is None else now
        with self._lock:
            self._total += byte_count
            self._last_packet_time = at
            started = not self._active and self._total >= self._threshold
            if started:
                self._active = True
            return AccumulatorTransition(started=started, total_bytes=self._total)

    def tick(self, *, now: float | None = None) -> AccumulatorTransition:
        """
        Check for inactivity and garbage-collect stale state.

        Two separate things happen here:

        1. If the accumulator is **active** and the inactivity window has
           elapsed, return a "stopped" transition and drop back to IDLE
           with a cleared counter.
        2. If the accumulator is **idle** but has accumulated sub-threshold
           bytes from a burst that never reached the trigger, drop those
           bytes after the same inactivity window. Without this, a small
           trickle of unrelated packets could accumulate over minutes or
           hours and eventually fire a spurious "started" transition long
           after the burst ended.

        Intended to be called on a regular cadence (e.g. 1 Hz) from a
        background supervisor, rather than driven by an external timer
        thread. This removes the need for a separate ``threading.Timer``
        per inactivity window, which was a source of thread explosions
        and lock-ordering hazards in the previous design.
        """
        at = time.monotonic() if now is None else now
        with self._lock:
            if self._last_packet_time is None:
                return AccumulatorTransition(total_bytes=self._total)
            if at - self._last_packet_time < self._timeout:
                return AccumulatorTransition(total_bytes=self._total)

            # Inactivity window elapsed → reset regardless of state.
            was_active = self._active
            self._active = False
            self._total = 0
            self._last_packet_time = None
            return AccumulatorTransition(stopped=was_active, total_bytes=0)

    def reset(self) -> None:
        """Force the accumulator back to IDLE. Used on shutdown."""
        with self._lock:
            self._active = False
            self._total = 0
            self._last_packet_time = None

    @property
    def total_bytes(self) -> int:
        """Current accumulated byte count."""
        with self._lock:
            return self._total

    @property
    def is_active(self) -> bool:
        """True if the accumulator has crossed the threshold and not yet timed out."""
        with self._lock:
            return self._active
