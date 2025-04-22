import os
import logging
from datetime import datetime
from scapy.all import sniff, TCP, IP, conf

# Prepare for LED strip when uncommented
# import board
# from led.strip import ledstrip


class LedSniffer:
    """TCP sniffer that triggers LED strips when traffic is detected."""

    DEFAULT_LED_COUNT = 30
    DEFAULT_LED_STRIP_CONTROL_PIN = 18  # board.d18

    def __init__(
        self,
        port,
        led_count=DEFAULT_LED_COUNT,
        led_strip_control_pin=DEFAULT_LED_STRIP_CONTROL_PIN,
        log_level=logging.INFO,
    ):
        """Initialize the LED sniffer with the specified parameters.

        Args:
            port: TCP port to monitor
            led_count: Number of LEDs in the strip
            led_strip_control_pin: GPIO pin for controlling the LED strip
            log_level: Logging level
        """
        self.port = int(port)
        self.led_count = led_count
        self.led_strip_control_pin = led_strip_control_pin

        # Setup logging
        self.logger = self._setup_logging(log_level)

        # Initialize LED strip (commented out until hardware is connected)
        # self.led_strip = ledstrip(
        #     self.led_strip_control_pin,
        #     led_count=self.led_count
        # )

        # Track statistics
        self.packets_seen = 0
        self.start_time = datetime.now()

    def _setup_logging(self, log_level):
        """Configure logging with consistent formatting."""
        logger = logging.getLogger("LedSniffer")
        logger.setLevel(log_level)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _handle_packet(self, pkt):
        """Process captured TCP packets and trigger LED if needed."""
        if IP in pkt and TCP in pkt:
            try:
                src = pkt[IP].src
                dst = pkt[IP].dst
                sport = pkt[TCP].sport
                dport = pkt[TCP].dport
                flags = pkt[TCP].flags
                payload_len = len(pkt[TCP].payload)

                self.packets_seen += 1

                # Log packet details
                self.logger.info(
                    f"{src}:{sport} → {dst}:{dport} | "
                    f"Flags={flags} | Payload={payload_len} bytes"
                )

                # Here you would activate LED strip
                # self.led_strip.flash(color=(255, 0, 0), duration_ms=100)

                # Print statistics every 100 packets
                if self.packets_seen % 100 == 0:
                    self._print_statistics()

            except Exception as e:
                self.logger.error(f"Error processing packet: {e}")
        else:
            self.logger.debug("Received non-TCP/IP packet")

    def _print_statistics(self):
        """Display running statistics about captured packets."""
        runtime = datetime.now() - self.start_time
        seconds = runtime.total_seconds()
        rate = self.packets_seen / seconds if seconds > 0 else 0

        self.logger.info(
            f"Statistics: {self.packets_seen} packets captured in {runtime} "
            f"({rate:.2f} packets/sec)"
        )

    def sniff(self, iface=None, timeout=None):
        """
        Start sniffing TCP traffic to/from the specified port.

        Args:
            iface: Network interface to capture on (None for default)
            timeout: Capture timeout in seconds (None for no timeout)
        """
        # Filter packets that carry actual data (PSH bit set)
        bpf_filter = f"tcp port {self.port} and tcp[13] & 0x08 != 0"

        selected_iface = iface or conf.iface
        self.logger.info(f"Capturing on iface={selected_iface} filter='{bpf_filter}'")
        self.logger.info(f"Monitoring port {self.port} for TCP traffic with PUSH flag")

        if os.geteuid() != 0:
            self.logger.warning("Not running as root. Packet capture may fail!")

        try:
            self.start_time = datetime.now()
            self.logger.info(f"Capture started at {self.start_time}")

            # Start the capture
            sniff(
                iface=selected_iface,
                filter=bpf_filter,
                prn=self._handle_packet,
                store=False,
                timeout=timeout,
            )
        except KeyboardInterrupt:
            self.logger.info("Capture stopped by user")
        except Exception as e:
            self.logger.error(f"Capture error: {e}")
        finally:
            self._print_statistics()


def main():
    """Entry point for the application."""
    import argparse

    parser = argparse.ArgumentParser(
        description="TCP packet sniffer with LED notification"
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=int(os.environ.get("PORT", 4000)),
        help="TCP port to monitor",
    )
    parser.add_argument("-i", "--interface", help="Network interface to capture on")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO

    print(
        f"Starting LedSniffer on port {args.port}. "
        f"Use external netcat to generate traffic."
    )

    led_sniffer = LedSniffer(port=args.port, log_level=log_level)
    led_sniffer.sniff(iface=args.interface)


if __name__ == "__main__":
    main()
