import time
import threading
from typing import Tuple

import adafruit_pixelbuf
from adafruit_raspberry_pi5_neopixel_write import neopixel_write
from led.animations.ReverseChase import ReverseChase


class Pi5Pixelbuf(adafruit_pixelbuf.PixelBuf):
    """PixelBuf subclass that knows how to drive the Pi 5’s NeoPixels."""

    def __init__(
        self,
        pin: int,
        size: int,
        **kwargs,
    ) -> None:
        """
        :param pin: GPIO pin number
        :param size: number of LEDs in the strip
        :param kwargs: other PixelBuf kwargs (e.g. byteorder, auto_write)
        """
        self._pin = pin
        super().__init__(size=size, **kwargs)

    def _transmit(self, buf: bytearray) -> None:
        """Transmit raw buffer out the data pin."""
        neopixel_write(self._pin, buf)


class LEDStrip:
    """
    Controls a NeoPixel LED strip on the Pi 5.

    Provides static on/off control and a wave animation.
    """

    def __init__(
        self,
        pin: int,
        led_count: int,
    ) -> None:
        """
        :param pin: GPIO pin connected to the strip
        :param led_count: number of LEDs
        """
        self._strip = Pi5Pixelbuf(pin, led_count, auto_write=True, byteorder="RGB")
        self._running = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._animation = None  # type: ReverseChase | None
        self._status = "off"

    def _run(self) -> None:
        """Background thread that steps the current animation."""
        while True:
            if self._running.is_set() and self._animation:
                self._animation.animate()
            else:
                time.sleep(0.02)

    def on(
        self,
        color: Tuple[int, int, int] = (255, 255, 255),
    ) -> None:
        """
        Light the entire strip in a solid color.

        :param color: RGB tuple, defaults to white
        """
        if not self._thread.is_alive():
            self._thread.start()

        # Stop any animation and show solid color
        self._running.clear()
        self._strip.fill(color)
        self._strip.show()
        self._status = "on"

    def off(self) -> None:
        """Turn off all LEDs immediately."""
        self._running.clear()
        self._strip.fill((0, 0, 0))
        self._strip.show()
        self._status = "off"

    def wave(
        self,
        speed: float = 0.09,
        color: Tuple[int, int, int] = (0, 101, 255),
        spacing: int = 3,
        reverse: bool = True,
    ) -> None:
        """
        Start the wave (ReverseChase) animation.

        :param speed: delay between steps, in seconds
        :param color: RGB tuple for the wave color
        :param spacing: spacing between lit pixels
        :param reverse: whether to reverse the chase direction
        """
        if not self._thread.is_alive():
            self._thread.start()

        # Configure and start animation
        self._animation = ReverseChase(
            self._strip,
            speed=speed,
            color=color,
            spacing=spacing,
            reverse=reverse,
        )
        self._running.set()
        self._status = "wave"

    @property
    def status(self) -> str:
        """
        Current strip status.

        One of: 'off', 'on', 'wave'
        """
        return self._status
