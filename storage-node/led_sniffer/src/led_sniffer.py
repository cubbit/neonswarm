#!/usr/bin/env python3
"""
TCP packet sniffer with NeoPixel LED notifications.

Listens for TCP packets on a given port (and optional host/interface),
accumulates byte counts, and flashes a NeoPixel strip when a byte
threshold is reached.
"""

import os
import argparse
import logging
import board
from time import sleep
from typing import Optional, Tuple

from led.strip import LEDStrip
from threshold_sniffer.threshold_sniffer import ThresholdSniffer
from utils.parsing import parse_size
from utils.loggable import Loggable
from utils.conversion import hex_to_rgb, ConversionException


class LedSniffer(Loggable):
    """
    Combines ThresholdSniffer and LEDStrip to flash LEDs on network activity.

    Attributes:
        sniff_port: TCP port to monitor.
        sniff_threshold: Number of bytes before triggering LEDs.
        sniff_timeout: Seconds of inactivity before resetting the counter.
        sniff_host: Optional IP to filter on.
        sniff_iface: Optional network interface to capture on.
        led_count: Number of LEDs in the strip.
        led_pin: GPIO pin driving the strip.
        animation_color: RGB tuple for the wave effect.
        animation_speed: Delay between animation steps.
        animation_spacing: Pixel spacing in the chase effect.
        animation_duration: Seconds to run the wave after threshold hit.
    """

    DEFAULT_SNIFF_SOURCE = None
    DEFAULT_SNIFF_PORT = 4000
    DEFAULT_SNIFF_IFACE = None
    DEFAULT_SNIFF_INACTIVITY_TIMEOUT_S = 3.0
    DEFAULT_SNIFF_THRESHOLD_BYTES = 1024
    DEFAULT_SNIFF_SIZE_FILTER_BYTES = 50

    DEFAULT_LED_COUNT = 30
    DEFAULT_LED_PIN = "D18"

    DEFAULT_ANIMATION_COLOR = "#0065FF"
    DEFAULT_ANIMATION_SPEED = 0.09
    DEFAULT_ANIMATION_SPACING = 3
    DEFAULT_ANIMATION_DURATION_S = 2.0

    def __init__(
        self,
        sniff_port: int,
        sniff_threshold: int,
        sniff_timeout: float,
        sniff_host: Optional[str],
        sniff_iface: Optional[str],
        sniff_size_filter_bytes: Optional[int],
        led_count: int,
        led_pin,
        animation_color: Tuple[int, int, int],
        animation_speed: float,
        animation_spacing: int,
        animation_duration: float,
        log_level: int,
    ) -> None:
        """
        Initialize the LedSniffer.

        :param sniff_port: TCP port to monitor.
        :param sniff_threshold: Byte threshold to trigger callback.
        :param sniff_timeout: Inactivity timeout (seconds) to reset counter.
        :param sniff_host: Optional host IP to filter.
        :param sniff_iface: Optional interface to capture on.
        :param sniff_size_filter_bytes: The size of the minimum packet size to consider for the sniff.
        :param led_count: Number of LEDs in the NeoPixel strip.
        :param led_pin: GPIO pin for NeoPixel data.
        :param animation_color: RGB for wave animation.
        :param animation_speed: Delay per animation frame (s).
        :param animation_spacing: Spacing between lit pixels.
        :param animation_duration: Duration to run wave (s) after trigger.
        :param log_level: Python logging level.
        """
        super().__init__(log_level)

        self.animation_color = animation_color
        self.animation_speed = animation_speed
        self.animation_spacing = animation_spacing
        self.animation_duration = animation_duration

        # --- set up the network sniffer ---
        self._sniffer = ThresholdSniffer(
            port=sniff_port,
            threshold_bytes=sniff_threshold,
            inactivity_timeout_s=sniff_timeout,
            size_filter_bytes=sniff_size_filter_bytes,
            host=sniff_host,
            iface=sniff_iface,
            log_level=log_level,
        )
        self._sniffer.on_start_sniffing = self._start_animation
        self._sniffer.on_stop_sniffing = self._stop_animation

        # --- set up the LED strip ---
        self.led_strip = LEDStrip(pin=led_pin, led_count=led_count)
        self.led_strip.off()

    def boot(self) -> None:
        """
        Perform any startup routines. Lights the strip briefly
        in the configured animation_color to show readiness.
        """
        self.logger.info("Booting LedSniffer — lighting strip for readiness")
        self.led_strip.on(self.animation_color)
        sleep(1.0)
        self.led_strip.off()

    def _start_animation(self) -> None:
        """
        Internal callback: run a wave animation when byte threshold is reached.
        """
        self.logger.info("Running wave animation")
        self.led_strip.wave(
            speed=self.animation_speed,
            color=self.animation_color,
            spacing=self.animation_spacing,
            reverse=True,
        )

    def _stop_animation(self) -> None:
        """
        Internal callback: stop wave animation
        """
        self.logger.info("Stopping wave animation")
        self.led_strip.off()

    def start(self) -> None:
        """
        Start the sniffing loop.  Blocks until interrupted.
        """
        self._sniffer.sniff()


def main() -> None:
    """Parse CLI args and launch the LedSniffer."""
    parser = argparse.ArgumentParser(
        description="TCP packet sniffer with NeoPixel LED notification"
    )
    # logging args
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG logging",
    )

    # network/sniff args…
    parser.add_argument(
        "-s",
        "--source",
        dest="host",
        type=str,
        default=LedSniffer.DEFAULT_SNIFF_SOURCE,
        help="Source host IP to filter packets",
    )
    parser.add_argument(
        "-p",
        "--port",
        dest="port",
        type=int,
        default=int(os.environ.get("PORT", LedSniffer.DEFAULT_SNIFF_PORT)),
        help="TCP port to monitor",
    )
    parser.add_argument(
        "-i",
        "--interface",
        dest="iface",
        type=str,
        default=LedSniffer.DEFAULT_SNIFF_IFACE,
        help="Network interface to capture on",
    )
    parser.add_argument(
        "-t",
        "--threshold",
        dest="threshold",
        type=parse_size,
        default=LedSniffer.DEFAULT_SNIFF_THRESHOLD_BYTES,
        help="Byte threshold before LED trigger (e.g. 1K, 2M)",
    )
    parser.add_argument(
        "-d",
        "--delay",
        dest="timeout",
        type=float,
        default=LedSniffer.DEFAULT_SNIFF_INACTIVITY_TIMEOUT_S,
        help="Seconds of inactivity before resetting counter",
    )
    parser.add_argument(
        "-f",
        "--filter_size",
        dest="size_filter",
        type=parse_size,
        default=LedSniffer.DEFAULT_SNIFF_SIZE_FILTER_BYTES,
        help="Minimum size for TCP packet to be considered in the sniffing process (e.g. 1K, 2M)",
    )

    # LED / animation args
    parser.add_argument(
        "--led-count",
        dest="led_count",
        type=int,
        default=LedSniffer.DEFAULT_LED_COUNT,
        help="Number of LEDs in the strip",
    )
    parser.add_argument(
        "--led-pin",
        dest="led_pin",
        type=str,
        default=LedSniffer.DEFAULT_LED_PIN,
        help="GPIO pin name for NeoPixel data (e.g. D18)",
    )
    parser.add_argument(
        "--animation-color",
        dest="animation_color",
        type=str,
        default=LedSniffer.DEFAULT_ANIMATION_COLOR,
        help="Wave color as hex string, e.g. '#FF0000' or '00FF00'",
    )
    parser.add_argument(
        "--animation-speed",
        dest="animation_speed",
        type=float,
        default=LedSniffer.DEFAULT_ANIMATION_SPEED,
        help="Seconds per frame of the wave animation",
    )
    parser.add_argument(
        "--animation-spacing",
        dest="animation_spacing",
        type=int,
        default=LedSniffer.DEFAULT_ANIMATION_SPACING,
        help="Pixel spacing for the wave animation",
    )
    parser.add_argument(
        "--animation-duration",
        dest="animation_duration",
        type=float,
        default=LedSniffer.DEFAULT_ANIMATION_DURATION_S,
        help="Seconds to run the wave after threshold is hit",
    )

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s %(message)s")

    rgb_color = None

    try:
        rgb_color = hex_to_rgb(args.animation_color)
    except ConversionException:
        parser.error(
            "`--animation-color` must be a 6-digit hex color, e.g. '#FF0000' or '00FF00'"
        )

    # Resolve the board pin from its name
    try:
        pin = getattr(board, args.led_pin)
    except AttributeError:
        parser.error(f"Unknown board pin `{args.led_pin}`; use e.g. 'D18', 'D17', etc.")

        # Log runtime configuration
    logging.debug(
        f"Starting with configuration: host={args.host or 'any'}, port={args.port}, "
        f"iface={args.iface or 'default'}, threshold={args.threshold} bytes, "
        f"timeout={args.timeout} s, filter_size={args.size_filter} bytes, "
        f"led_count={args.led_count}, led_pin={args.led_pin}, "
        f"animation_color={args.animation_color}, animation_speed={args.animation_speed}, "
        f"animation_spacing={args.animation_spacing}, animation_duration={args.animation_duration}"
    )

    sniffer = LedSniffer(
        sniff_port=args.port,
        sniff_threshold=args.threshold,
        sniff_timeout=args.timeout,
        sniff_host=args.host,
        sniff_iface=args.iface,
        sniff_size_filter_bytes=args.size_filter,
        led_count=args.led_count,
        led_pin=pin,
        animation_color=rgb_color,
        animation_speed=args.animation_speed,
        animation_spacing=args.animation_spacing,
        animation_duration=args.animation_duration,
        log_level=log_level,
    )
    sniffer.boot()
    sniffer.start()


if __name__ == "__main__":
    main()
