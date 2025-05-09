from scapy.all import sniff, TCP, IP, conf
import os
from threading import Timer, Lock
from typing import Optional, Callable
from utils.loggable import Loggable
import logging


class ThresholdSniffer(Loggable):
    """
    Sniffs TCP traffic on a given interface and port, accumulating payload bytes,
    and triggers a callback once a byte‐threshold is reached. The counter resets
    after a configurable period of inactivity.

    Attributes:
        on_sniff (Optional[Callable[[], None]]):
            Called when the accumulated payload exceeds the threshold.
    """

    def __init__(
        self,
        port: int,
        threshold_bytes: int,
        inactivity_timeout_s: float,
        size_filter_bytes: Optional[int],
        host: Optional[str],
        iface: Optional[str] = None,
        log_level: int = logging.INFO,
    ) -> None:
        """
        Initialize the ThresholdSniffer.

        Args:
            host: IP address to filter (both src and dst). If None, captures from any host.
            port: TCP port number to monitor.
            iface: Network interface name. If None, scapy's default is used.
            threshold_bytes: Number of bytes to accumulate before triggering start callback.
            inactivity_timeout_s: Seconds of no packets before triggering stop callback.
            size_filter_bytes: Minimum payload size (in bytes) to consider.
            log_level: Logging level for the internal logger.
        """
        super().__init__(log_level)

        self._host = host
        self._port = port
        self._iface = iface
        self._threshold_bytes = threshold_bytes
        self._size_filter_bytes = size_filter_bytes
        self._inactivity_timeout_s = inactivity_timeout_s

        self._data_volume: int = 0
        self._timer: Optional[Timer] = None
        self._lock = Lock()
        self._sniffing_active = False

        # User can assign callbacks
        self.on_start_sniffing: Optional[Callable[[], None]] = None
        self.on_stop_sniffing: Optional[Callable[[], None]] = None

    def _handle_packet(self, packet) -> None:
        """
        Callback for each sniffed packet. Accumulates payload length and
        triggers start callback if threshold is reached.

        Args:
            packet: Packet object from scapy.
        """
        if IP not in packet or TCP not in packet:
            return

        try:
            payload_len = len(packet[TCP].payload)

            if self._size_filter_bytes and payload_len < self._size_filter_bytes:
                return

            self.logger.debug(
                "%s:%s → %s:%s | Flags=%s | Payload=%d bytes",
                packet[IP].src,
                packet[TCP].sport,
                packet[IP].dst,
                packet[TCP].dport,
                packet[TCP].flags,
                payload_len,
            )

            with self._lock:
                self._data_volume += payload_len

                # Trigger start callback once when threshold is passed
                if (
                    not self._sniffing_active
                    and self._data_volume >= self._threshold_bytes
                ):
                    self._sniffing_active = True

                    if callable(self.on_start_sniffing):
                        self.on_start_sniffing()

            # Reset inactivity timer on each qualifying packet
            self._reset_timer()

        except Exception as e:
            self.logger.error("Error processing packet: %s", e, exc_info=True)

    def _reset_timer(self) -> None:
        """
        Cancel any existing inactivity timer and start a new one
        to call stop callback after inactivity_timeout_s.
        """
        with self._lock:
            if self._timer:
                self._timer.cancel()

            self._timer = Timer(self._inactivity_timeout_s, self._clean)
            self._timer.daemon = True
            self._timer.start()

    def _clean(self) -> None:
        """
        Called after inactivity: triggers stop callback and resets state.
        """
        with self._lock:
            # Only fire stop if we were previously active
            if self._sniffing_active:
                self._sniffing_active = False

                if callable(self.on_stop_sniffing):
                    self.on_stop_sniffing()

            # Reset data volume and timer
            if self._data_volume > 0:
                self._data_volume = 0

            if self._timer:
                self._timer.cancel()
                self._timer = None

            self.logger.debug("Data volume reset after inactivity and stopped sniffing")

    def sniff(self) -> None:
        """
        Start sniffing TCP traffic on the specified interface and port.
        Blocks until interrupted (Ctrl-C) or an error occurs.
        """
        self.logger.info(
            "Starting sniff on port %d (host=%s, iface=%s)",
            self._port,
            self._host or "any",
            self._iface or "default",
        )

        # Capture packets in both directions with PSH flag set
        bpf_filter = f"tcp src port {self._port} and tcp[13] & 0x08 != 0"
        if self._host:
            bpf_filter += f" and host {self._host}"

        iface = self._iface or conf.iface
        self.logger.info("Starting capture on %s with filter '%s'", iface, bpf_filter)
        self.logger.info(
            "Threshold=%d bytes, inactivity timeout=%.1fs",
            self._threshold_bytes,
            self._inactivity_timeout_s,
        )

        if os.geteuid() != 0:
            self.logger.warning(
                "Running without root privileges—capture may be incomplete"
            )

        try:
            sniff(
                iface=iface,
                filter=bpf_filter,
                prn=self._handle_packet,
                store=False,
            )
        except KeyboardInterrupt:
            self.logger.info("Sniffing stopped by user")
        except Exception as e:
            self.logger.error("Capture error: %s", e, exc_info=True)
        finally:
            # Ensure final cleanup and stop callback if needed
            self._clean()
