import adafruit_pixelbuf
import time
import threading

from adafruit_raspberry_pi5_neopixel_write import neopixel_write
from led.animations.ReverseChase import ReverseChase


class Pi5Pixelbuf(adafruit_pixelbuf.PixelBuf):
    def __init__(self, pin, size, **kwargs):
        self._pin = pin
        super().__init__(size=size, **kwargs)

    def _transmit(self, buf):
        neopixel_write(self._pin, buf)


class LEDStrip:
    def __init__(self, pin, led_count):
        self._pin = pin
        self._led_count = led_count
        self._running = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._strip = Pi5Pixelbuf(
            self._pin, self._led_count, auto_write=True, byteorder="RGB"
        )
        self._animation = ReverseChase(
            self._strip,
            speed=0.09,
            color=(0, 101, 255),
            spacing=3,
            reverse=True,
        )

    def upload(self):
        try:
            while True:
                self._animation.animate()
        finally:
            time.sleep(0.02)
            self._strip.fill(0)
            self._strip.show()

    def _run(self):
        while True:
            if self._running.is_set():
                self._animation.animate()
            else:
                time.sleep(0.02)

    def on(self):
        if not self._thread.is_alive():
            self._thread.start()

        self._running.set()

    def off(self):
        self._running.clear()
        self._strip.fill(0)
        self._strip.show()
