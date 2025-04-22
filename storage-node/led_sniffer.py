import os
import logging
import argparse
from threading import Timer, Lock
from scapy.all import sniff, TCP, IP, conf

# Prepare for LED strip when uncommented
# import board
# from led.strip import ledstrip


class LedSniffer:
    """TCP sniffer that triggers LED strips when traffic volume exceeds threshold,
    with debounce functionality to prevent constant flickering."""

    DEFAULT_LED_COUNT = 30
    DEFAULT_LED_STRIP_CONTROL_PIN = 18  # board.d18
    DEFAULT_DATA_THRESHOLD = 1024  # Bytes of data to trigger LED (1KB)
    DEFAULT_INACTIVITY_TIMEOUT = 3.0  # Seconds of no packets before LEDs turn off

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
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    def _handle_packet(self, pkt):
        """Process captured TCP packets and trigger LED if data threshold is met."""
        if IP in pkt and TCP in pkt:
            try:
                src = pkt[IP].src
                dst = pkt[IP].dst
                sport = pkt[TCP].sport
                dport = pkt[TCP].dport
                flags = pkt[TCP].flags

                # Calculate actual payload size
                payload_len = len(pkt[TCP].payload)

                # Log packet info outside the lock to avoid holding lock during I/O
                self.logger.debug(
                    f"{src}:{sport} → {dst}:{dport} | "
                    f"Flags={flags} | Payload={payload_len} bytes"
                )

                # Minimize the critical section - only lock when updating shared state
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
        # Acquire lock to check and update LED state
        with self.lock:
            if not self.led_active:
                self.led_active = True
                current_data = self.data_volume  # Capture for logging

        # Log outside the lock
        self.logger.info(
            f"LEDS lighting up (data threshold {current_data}/{self.data_threshold} bytes reached)"
        )
        # When actual hardware is connected:
        # self.led_strip.on(color=(255, 0, 0))  # Red light

    def _turn_off_leds(self):
        """Turn off the LED strip and reset data volume counter."""
        # Acquire lock to check and update LED state
        data_seen = 0
        with self.lock:
            if self.led_active:
                self.led_active = False
                data_seen = self.data_volume
                self.data_volume = 0

        # Only log if LEDs were actually turned off
        if data_seen > 0:
            self.logger.info(
                f"LEDS turning off - inactivity timeout ({data_seen} bytes processed)"
            )
            # When actual hardware is connected:
            # self.led_strip.off()

    def sniff(self, iface=None, timeout=None):
        """Start sniffing TCP traffic to/from the specified port."""
        # Filter packets that carry actual data (PSH bit set)
        bpf_filter = f"tcp port {self.port} and tcp[13] & 0x08 != 0"

        selected_iface = iface or conf.iface
        self.logger.info(f"Capturing on iface={selected_iface} filter='{bpf_filter}'")
        self.logger.info(
            f"Monitoring port {self.port} - LED will activate after "
            f"{self.data_threshold} bytes and deactivate after "
            f"{self.inactivity_timeout}s of inactivity"
        )

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


# Helper function to parse sizes with suffixes
def parse_size(size_str):
    """Parse size strings like '1K', '2M', etc."""
    if not isinstance(size_str, str):
        return size_str

    size_str = size_str.upper()
    multipliers = {"K": 1024, "M": 1024 * 1024, "G": 1024 * 1024 * 1024}

    for suffix, multiplier in multipliers.items():
        if size_str.endswith(suffix):
            try:
                return int(float(size_str[:-1]) * multiplier)
            except ValueError:
                raise argparse.ArgumentTypeError(f"Invalid size format: {size_str}")

    # If no suffix, try to convert directly to int
    try:
        return int(size_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid size format: {size_str}")


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
        type=parse_size,  # Use our custom parser
        default=LedSniffer.DEFAULT_DATA_THRESHOLD,
        help="Bytes of data needed to trigger LED (can use K, M, G suffixes)",
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
