from math import ceil
from adafruit_led_animation.animation import Animation


class ReverseChase(Animation):
    """
    Theatre chase animation with direction control, implemented from scratch.

    :param pixel_object: The initialized LED object.
    :param float speed: Animation speed in seconds, e.g. 0.1.
    :param color: Animation color as an (r, g, b) tuple or 0xRRGGBB hex.
    :param size: Number of pixels lit in each bar (default 2).
    :param spacing: Number of pixels off between bars (default 3).
    :param reverse: If True, chase moves in reverse direction (default False).
    :param name: Optional name for debugging.
    """

    def __init__(
        self,
        pixel_object,
        speed,
        color,
        size=2,
        spacing=3,
        reverse=False,
        name=None,
    ):
        # Bar and spacing configuration
        self._size = size
        self._spacing = spacing
        self._repeat_width = size + spacing
        self._num_repeats = ceil(len(pixel_object) / self._repeat_width)
        self._overflow = len(pixel_object) % self._repeat_width

        # Direction control
        self._reverse = reverse
        self._direction = -1 if reverse else 1
        self._offset = 0

        super().__init__(pixel_object, speed, color, name=name)

    @property
    def reverse(self):
        """Get or set the reverse flag."""
        return self._reverse

    @reverse.setter
    def reverse(self, value):
        self._reverse = bool(value)
        self._direction = -1 if self._reverse else 1

    def draw(self):
        """Render one frame of the chase animation."""

        def bar_colors():
            bar_no = 0
            # Handle initial offset phase
            for i in range(self._offset, 0, -1):
                if i > self._spacing:
                    yield self.bar_color(bar_no, i)
                else:
                    yield self.space_color(bar_no, i)
                    bar_no += 1
            # Repeat bars and spaces across the strip
            while True:
                for _ in range(self._size):
                    yield self.bar_color(bar_no)
                for _ in range(self._spacing):
                    yield self.space_color(bar_no)
                bar_no += 1

        colorgen = bar_colors()
        # Fill the pixel buffer
        self.pixel_object[:] = [next(colorgen) for _ in range(len(self.pixel_object))]

        # Mark cycle completion
        if self.draw_count % len(self.pixel_object) == 0:
            self.cycle_complete = True

        # Advance offset in the chosen direction
        self._offset = (self._offset + self._direction) % self._repeat_width

    def bar_color(self, n, pixel_no=0):  # pylint: disable=unused-argument
        """Color for the lit pixels."""
        return self.color

    @staticmethod
    def space_color(n, pixel_no=0):  # pylint: disable=unused-argument
        """Color for the off pixels (always 0)."""
        return 0

    def reset(self):
        """Reset the animation to the initial state."""
        self._offset = 0
        self._direction = -1 if self._reverse else 1
