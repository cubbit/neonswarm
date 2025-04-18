import board
from led.strip import LEDStrip

strip = LEDStrip(board.D18, led_count=29)
strip.upload()
