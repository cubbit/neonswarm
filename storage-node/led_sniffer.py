import os
import logging
import argparse
from threading import Timer, Lock
from scapy.all import sniff, TCP, IP, conf
from utils.parsing import parse_size

# Prepare for LED strip when uncommented
# import board
# from led.strip import ledstrip


class LedSniffer:
    """TCP sniffer that triggers LED strips when traffic volume exceeds threshold,
    with debounce functionality to prevent constant flickering."""

    DEFAULT_LED_COUNT = 30
    DEFAULT_LED_STRIP_CONTROL_PIN = 18  # board.d18
    DEFAULT_DATA_THRESHOLD = 1024  # Bytes of data to trigger LED (1KB)
    DEFAULT_INACTIVITY_TIMEOUT = 3.0  # Seconds before LEDs turn off

    def __init__(
        self,
        port,
        led_count=DEFAULT_LED_COUNT,
        led_strip_control_pin=DEFAULT_LED_STRIP_CONTROL_PIN,
        data_threshold=DEFAULT_DATA_THRESHOLD,
        inactivity_timeout=DEFAULT_INACTIVITY_TIMEOUT,
        log_level=logging.INFO,
    ):
        """Initialize the LED sniffer with the specified parameters."""
        self.port = int(port)
        self.led_count = led_count
        self.led_strip_control_pin = led_strip_control_pin
        self.data_threshold = data_threshold
        self.inactivity_timeout = inactivity_timeout

        # Setup logging
        self.logger = self._setup_logging(log_level)

        # Initialize LED strip (commented out until hardware is connected)
        # self.led_strip = ledstrip(
        #     self.led_strip_control_pin,
        #     led_count=self.led_count
        # )

        # Debounce state variables
        self.data_volume = 0
        self.led_active = False
        self.timer = None
        self.lock = Lock()  # To prevent race conditions

    def _setup_logging(self, log_level):
        """Configure logging with consistent formatting."""
        logger = logging.getLogger("LedSniffer")
        logger.setLevel(log_level)

        if not logger.handlers:
            handler = logging.StreamHandler()
            fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            formatter = logging.Formatter(fmt)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _handle_packet(self, pkt):
        """Process captured TCP packets and trigger LED if threshold is met."""
        if IP not in pkt or TCP not in pkt:
            return

        try:
            src = pkt[IP].src
            dst = pkt[IP].dst
            sport = pkt[TCP].sport
            dport = pkt[TCP].dport
            flags = pkt[TCP].flags

            # Calculate actual payload size
            payload_len = len(pkt[TCP].payload)

            # Log packet info outside the lock
            log_msg = (
                f"{src}:{sport} → {dst}:{dport} | "
                f"Flags={flags} | Payload={payload_len} bytes"
            )
            self.logger.debug(log_msg)

            old_timer = None

            with self.lock:
                # Store reference to old timer
                old_timer = self.timer
                self.timer = None

                # Add data size
                self.data_volume += payload_len
                should_turn_on = (
                    not self.led_active and self.data_volume >= self.data_threshold
                )

            # Cancel any existing timer outside the lock
            if old_timer:
                old_timer.cancel()

            # Create new timer outside the lock
            new_timer = Timer(self.inactivity_timeout, self._turn_off_leds)
            new_timer.daemon = True

            # Update timer reference with lock
            with self.lock:
                self.timer = new_timer

            # Start timer outside lock
            self.timer.start()

            # Turn on LEDs if needed
            if should_turn_on:
                self._turn_on_leds()

        except Exception as e:
            self.logger.error(f"Error processing packet: {e}")

    def _turn_on_leds(self):
        """Turn on the LED strip."""
        with self.lock:
            if not self.led_active:
                self.led_active = True
                current_data = self.data_volume  # Capture for logging

        log_msg = (
            f"LEDS lighting up (data threshold "
            f"{current_data}/{self.data_threshold} bytes reached)"
        )
        self.logger.info(log_msg)

    def _turn_off_leds(self):
        """Turn off the LED strip and reset data volume counter."""
        data_seen = 0

        with self.lock:
            if self.led_active:
                self.led_active = False
                data_seen = self.data_volume
                self.data_volume = 0

        if data_seen > 0:
            log_msg = f"LEDS turning off - ({data_seen} bytes processed)"
            self.logger.info(log_msg)

    def sniff(self, iface=None, timeout=None):
        """Start sniffing TCP traffic to/from the specified port."""
        # Filter packets that carry actual data (PSH bit set)
        bpf_filter = f"tcp port {self.port} and tcp[13] & 0x08 != 0"

        selected_iface = iface or conf.iface
        self.logger.info(f"Capturing on iface={selected_iface} filter='{bpf_filter}'")

        status_msg = (
            f"Monitoring port {self.port} - LED will activate after "
            f"{self.data_threshold} bytes and deactivate after "
            f"{self.inactivity_timeout}s of inactivity"
        )
        self.logger.info(status_msg)

        if os.geteuid() != 0:
            self.logger.warning("Not running as root. Packet capture may fail!")

        try:
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
            # Clean up timer on exit
            timer = None
            with self.lock:
                timer = self.timer
                self.timer = None

            if timer:
                timer.cancel()


def main():
    """Entry point for the application."""
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
        "-t",
        "--threshold",
        type=parse_size,
        default=LedSniffer.DEFAULT_DATA_THRESHOLD,
        help="Bytes needed to trigger LED (can use K, M, G suffixes)",
    )
    parser.add_argument(
        "-d",
        "--delay",
        type=float,
        default=LedSniffer.DEFAULT_INACTIVITY_TIMEOUT,
        help="Seconds of inactivity before LEDs turn off",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO

    sniffer = LedSniffer(
        port=args.port,
        data_threshold=args.threshold,
        inactivity_timeout=args.delay,
        log_level=log_level,
    )
    sniffer.sniff(iface=args.interface)


if __name__ == "__main__":
    main()
