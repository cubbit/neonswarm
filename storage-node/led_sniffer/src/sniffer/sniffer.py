from scapy.all import sniff, TCP, IP, conf
import os
import logging
from threading import Timer, Lock


class ThresholdSniffer:
    DEFAULT_INACTIVIY_TIMEOUT_S = 3.0
    DEFAULT_THRESHOLD_BYTES = 1024

    def __init__(
        self,
        host,
        port,
        iface=None,
        threshold=DEFAULT_THRESHOLD_BYTES,
        inactivity_timeout_s=DEFAULT_INACTIVIY_TIMEOUT_S,
        log_level=logging.INFO,
    ):
        self._host = host
        self._port = port
        self._iface = iface
        self._threshold_bytes = threshold
        self._inactivity_timeout_s = inactivity_timeout_s

        # Initialize data counter
        self._data_volume = 0
        self._timer = None
        self._lock = Lock()

        # Trigger Callback (Public)
        self.on_sniff = None

        self._logger = self._setup_logging(log_level)

    def _setup_logging(self, log_level):
        """Configure logging with consistent formatting."""
        logger = logging.getLogger("ThresholdSniffer")
        logger.setLevel(log_level)

        if not logger.handlers:
            handler = logging.StreamHandler()
            fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            formatter = logging.Formatter(fmt)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _handle_packet(self, pkt):
        if IP not in pkt or TCP not in pkt:
            return

        try:
            src = pkt[IP].src
            dst = pkt[IP].dst
            sport = pkt[TCP].sport
            dport = pkt[TCP].dport
            flags = pkt[TCP].flags

            payload_len = len(pkt[TCP].payload)

            log_msg = (
                f"{src}:{sport} → {dst}:{dport} | "
                f"Flags={flags} | Payload={payload_len} bytes"
            )
            self._logger.debug(log_msg)

            with self._lock:
                self._data_volume += payload_len

            if callable(self.on_sniff) and self._should_trigger():
                self.on_sniff()

            self._reset_timer()

        except Exception as e:
            self._logger.error(f"Error processing packet: {e}")

    def _should_trigger(self):
        with self._lock:
            return self.on_sniff and self._data_volume >= self._threshold_bytes

    def _reset_timer(self):
        old_timer = None

        with self._lock:
            old_timer = self._timer

        if old_timer:
            old_timer.cancel()

        new_timer = Timer(self._inactivity_timeout_s, self._clean)
        new_timer.daemon = True

        with self._lock:
            self._timer = new_timer

        self._timer.start()

    def _clean(self):
        with self._lock:
            self._data_volume = 0

            if self._timer:
                self._timer.cancel()

            self._timer = None

    def sniff(self):
        """Start sniffing TCP traffic to/from the specified port."""
        # Filter packets that carry actual data (PSH bit set)
        bpf_filter = f"tcp src port {self._port} and tcp[13] & 0x08 != 0"

        # Optionally restrict the host
        if self._host:
            bpf_filter += f" and src host {self._host}"

        # If not specified, iface is selected automatically
        selected_iface = self._iface or conf.iface
        self._logger.info(
            "Capturing on iface=%s filter='%s'",
            selected_iface,
            bpf_filter,
        )

        status_msg = (
            f"Monitoring port {self._port} - LED will activate after "
            f"{self._threshold_bytes} bytes and deactivate after "
            f"{self._inactivity_timeout_s}s of inactivity"
        )
        self._logger.info(status_msg)

        if os.geteuid() != 0:
            self._logger.warning("Not running as root. Packet capture may fail!")

        try:
            # Start the capture (blocking)
            sniff(
                iface=selected_iface,
                filter=bpf_filter,
                prn=self._handle_packet,
                store=False,
            )
        except KeyboardInterrupt:
            self._logger.info("Capture stopped by user")
        except Exception as e:
            self._logger.error(f"Capture error: {e}")
        finally:
            self._clean()
