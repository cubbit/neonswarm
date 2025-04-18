import time

import adafruit_pixelbuf
import board
from adafruit_led_animation.animation.chase import Chase
from adafruit_raspberry_pi5_neopixel_write import neopixel_write

NEOPIXEL = board.D18
num_pixels = 29


class Pi5Pixelbuf(adafruit_pixelbuf.PixelBuf):
    def __init__(self, pin, size, **kwargs):
        self._pin = pin
        super().__init__(size=size, **kwargs)

    def _transmit(self, buf):
        neopixel_write(self._pin, buf)


pixels = Pi5Pixelbuf(NEOPIXEL, num_pixels, auto_write=True, byteorder="BGR")

chase = Chase(pixels, speed=0.06, color=0x0065FF, spacing=3)

try:
    while True:
        chase.animate()
finally:
    time.sleep(0.02)
    pixels.fill(0)
    pixels.show()
