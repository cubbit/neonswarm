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
            threshold_bytes: Number of bytes to accumulate before triggering callback.
            inactivity_timeout_s: Seconds of no packets before resetting the counter.
            log_level: Logging level for the internal logger.
        """
        super().__init__(log_level)

        self._host = host
        self._port = port
        self._iface = iface
        self._threshold_bytes = threshold_bytes
        self._inactivity_timeout_s = inactivity_timeout_s

        self._data_volume: int = 0
        self._timer: Optional[Timer] = None
        self._lock = Lock()

        # User can assign a callback: no‐op by default
        self.on_sniff: Optional[Callable[[], None]] = None

    def _handle_packet(self, packet) -> None:
        """
        Callback for each sniffed packet. Accumulates payload length and
        triggers callback if threshold is reached.

        Args:
            pkt: Packet object from scapy.
        """
        if IP not in packet or TCP not in packet:
            return

        try:
            payload_len = len(packet[TCP].payload)

            if payload_len < 20:
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

            if callable(self.on_sniff) and self._data_volume >= self._threshold_bytes:
                self.on_sniff()

            self._reset_timer()

        except Exception as e:
            self.logger.error("Error processing packet: %s", e, exc_info=True)

    def _reset_timer(self) -> None:
        """
        Cancel any existing inactivity timer and start a new one
        to reset the byte counter after inactivity_timeout_s.
        """
        with self._lock:
            if self._timer:
                self._timer.cancel()

            self._timer = Timer(self._inactivity_timeout_s, self._clean)
            self._timer.daemon = True
            self._timer.start()

    def _clean(self) -> None:
        """
        Reset the accumulated byte counter and cancel the timer.
        Called after inactivity.
        """
        with self._lock:
            self._data_volume = 0
            if self._timer:
                self._timer.cancel()
            self._timer = None
            self.logger.debug("Data volume reset after inactivity")

    def sniff(self) -> None:
        """
        Start sniffing TCP traffic on the specified interface and port.
        Blocks until interrupted (Ctrl-C) or an error occurs.
        """
        # Capture packets in both directions with PSH flag set
        bpf_filter = f"tcp port {self._port} and tcp[13] & 0x08 != 0"
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
            self._clean()
