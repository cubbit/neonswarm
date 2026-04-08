#!/usr/bin/env python3
"""
LED sniffer — light a NeoPixel strip when real cluster data traffic flows.

A demo that visualises Cubbit swarm data replication. On each Raspberry Pi
storage node a DaemonSet pod runs this script, sniffs pod-to-pod TCP
traffic on the local ``cni0`` bridge, and drives a NeoPixel strip via the
adafruit-blinka stack.

Design notes
------------
* The heavy lifting lives in :class:`ThresholdSniffer` and
  :class:`ByteAccumulator`. This module only wires CLI args into the
  sniffer and brokers its callbacks into LED strip calls.
* A signal handler installs SIGTERM / SIGINT → ``sniffer.request_stop()``
  so Helm upgrades and Ctrl-C both exit cleanly. The previous design only
  caught ``KeyboardInterrupt``.
* The LED strip is turned off on shutdown so the panel does not keep an
  old animation running after the pod dies.
* Unlike lcd-storage we deliberately do not show an error frame — this
  module has no display — but capture errors are still logged and the
  supervisor loop restarts scapy with exponential backoff.
"""

import argparse
import logging
import os
import signal
import sys

import board

from led.strip import LEDStrip
from threshold_sniffer.threshold_sniffer import ThresholdSniffer, DEFAULT_POD_CIDR, DEFAULT_INTERFACE
from utils.conversion import ConversionException, hex_to_rgb
from utils.loggable import Loggable
from utils.parsing import parse_size


# Capture defaults
DEFAULT_SNIFF_PORT = None                 # None = any TCP port inside the pod CIDR
DEFAULT_SNIFF_HOST = None
DEFAULT_SNIFF_INACTIVITY_TIMEOUT_S = 3.0
DEFAULT_SNIFF_THRESHOLD_BYTES = 30 * 1024           # 30 KB: triggers on real uploads, not health checks
DEFAULT_SNIFF_SIZE_FILTER_BYTES = 200               # drop ACKs, keepalives, small control segments

# LED defaults
DEFAULT_LED_COUNT = 30
DEFAULT_LED_PIN = "D18"
DEFAULT_ANIMATION_COLOR = "#0065FF"
DEFAULT_ANIMATION_SPEED = 0.09
DEFAULT_ANIMATION_SPACING = 3


class LedSniffer(Loggable):
    """
    Glue between :class:`ThresholdSniffer` and :class:`LEDStrip`.

    Start / stop animation callbacks are wired into the sniffer at
    construction time; the main loop runs inside ``sniffer.run_forever``.
    """

    def __init__(
        self,
        sniff_port,
        sniff_threshold: int,
        sniff_timeout: float,
        sniff_host,
        sniff_iface: str,
        sniff_size_filter_bytes: int,
        pod_cidr: str,
        led_count: int,
        led_pin,
        animation_color: tuple[int, int, int],
        animation_speed: float,
        animation_spacing: int,
        log_level: int,
    ) -> None:
        super().__init__(log_level)

        self._animation_color = animation_color
        self._animation_speed = animation_speed
        self._animation_spacing = animation_spacing

        self._sniffer = ThresholdSniffer(
            port=sniff_port,
            threshold_bytes=sniff_threshold,
            inactivity_timeout_s=sniff_timeout,
            size_filter_bytes=sniff_size_filter_bytes,
            host=sniff_host,
            iface=sniff_iface,
            pod_cidr=pod_cidr,
            log_level=log_level,
        )
        self._sniffer.on_start_sniffing = self._start_animation
        self._sniffer.on_stop_sniffing = self._stop_animation

        # Install signal handlers **before** touching hardware. If SIGTERM
        # arrives during the potentially-slow LEDStrip constructor (SPI /
        # /dev/gpiomem open) we still want a clean shutdown — the handler
        # only calls ``_sniffer.request_stop()`` which was initialized
        # above.
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        self._led_strip = LEDStrip(pin=led_pin, led_count=led_count)
        self._led_strip.off()

    def _start_animation(self) -> None:
        self.logger.info("starting wave animation")
        self._led_strip.wave(
            speed=self._animation_speed,
            color=self._animation_color,
            spacing=self._animation_spacing,
            reverse=True,
        )

    def _stop_animation(self) -> None:
        self.logger.info("stopping wave animation")
        self._led_strip.off()

    def _handle_signal(self, signum: int, _frame) -> None:
        self.logger.info("received signal %d, shutting down", signum)
        self._sniffer.request_stop()

    def run(self) -> None:
        """Boot the strip, then run the sniffer until stop is requested."""
        self._sniffer.run_forever()
        self._led_strip.off()


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser. Kept separate from main() to keep wiring tidy."""
    parser = argparse.ArgumentParser(
        description="TCP packet sniffer with NeoPixel LED notifications."
    )

    # Logging
    parser.add_argument("-v", "--verbose", action="store_true", help="DEBUG logging")

    # Capture
    env_port = int(os.environ["PORT"]) if os.environ.get("PORT") else DEFAULT_SNIFF_PORT
    parser.add_argument(
        "-s", "--source", dest="host", type=str, default=DEFAULT_SNIFF_HOST,
        help="Optional source host filter (BPF 'host <ip>')",
    )
    parser.add_argument(
        "-p", "--port", dest="port", type=int, default=env_port,
        help="Optional TCP port restriction (omit for any pod-to-pod TCP)",
    )
    parser.add_argument(
        "-i", "--interface", dest="iface", type=str, default=DEFAULT_INTERFACE,
        help=f"Interface to sniff (default: {DEFAULT_INTERFACE})",
    )
    parser.add_argument(
        "--pod-cidr", dest="pod_cidr", type=str, default=DEFAULT_POD_CIDR,
        help=f"Flannel pod CIDR (default: {DEFAULT_POD_CIDR})",
    )
    parser.add_argument(
        "-t", "--threshold", dest="threshold", type=parse_size,
        default=DEFAULT_SNIFF_THRESHOLD_BYTES,
        help="Byte threshold before triggering (e.g. 30K, 1M)",
    )
    parser.add_argument(
        "-d", "--delay", dest="timeout", type=float,
        default=DEFAULT_SNIFF_INACTIVITY_TIMEOUT_S,
        help="Seconds of inactivity before stopping animation",
    )
    parser.add_argument(
        "-f", "--filter_size", dest="size_filter", type=parse_size,
        default=DEFAULT_SNIFF_SIZE_FILTER_BYTES,
        help="Minimum TCP payload size to count (e.g. 200B, 1K)",
    )

    # LED / animation
    parser.add_argument("--led-count", type=int, default=DEFAULT_LED_COUNT)
    parser.add_argument("--led-pin", type=str, default=DEFAULT_LED_PIN)
    parser.add_argument("--animation-color", type=str, default=DEFAULT_ANIMATION_COLOR)
    parser.add_argument("--animation-speed", type=float, default=DEFAULT_ANIMATION_SPEED)
    parser.add_argument("--animation-spacing", type=int, default=DEFAULT_ANIMATION_SPACING)

    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    try:
        rgb_color = hex_to_rgb(args.animation_color)
    except ConversionException:
        parser.error(
            "--animation-color must be a 6-digit hex color, e.g. '#FF0000' or '00FF00'"
        )

    try:
        pin = getattr(board, args.led_pin)
    except AttributeError:
        parser.error(f"unknown board pin {args.led_pin!r}; use e.g. 'D18', 'D17'")

    logging.debug(
        "config: host=%s port=%s iface=%s pod_cidr=%s threshold=%d timeout=%.1fs size_filter=%d led_count=%d led_pin=%s color=%s",
        args.host or "any",
        args.port if args.port is not None else "any",
        args.iface,
        args.pod_cidr,
        args.threshold,
        args.timeout,
        args.size_filter,
        args.led_count,
        args.led_pin,
        args.animation_color,
    )

    sniffer = LedSniffer(
        sniff_port=args.port,
        sniff_threshold=args.threshold,
        sniff_timeout=args.timeout,
        sniff_host=args.host,
        sniff_iface=args.iface,
        sniff_size_filter_bytes=args.size_filter,
        pod_cidr=args.pod_cidr,
        led_count=args.led_count,
        led_pin=pin,
        animation_color=rgb_color,
        animation_speed=args.animation_speed,
        animation_spacing=args.animation_spacing,
        log_level=log_level,
    )
    sniffer.run()
    sys.exit(0)


if __name__ == "__main__":
    main()
