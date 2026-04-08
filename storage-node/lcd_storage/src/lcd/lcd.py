import logging
import time
from typing import List, Union

from RPLCD.i2c import CharLCD

from utils.loggable import Loggable


class LCDController(Loggable):
    """
    Controller for a 16x2 I2C LCD display with frame diffing and
    in-place updates to avoid flicker.
    """

    COLS: int = 16
    ROWS: int = 2

    def __init__(
        self,
        i2c_addr: int,
        log_level: int = logging.INFO,
    ) -> None:
        """
        Initialize the LCD controller with a fixed 16x2 display.

        Args:
            i2c_addr: I2C address of the LCD expander (e.g., 0x27).
            log_level: Logging level for display operations.
        """
        super().__init__(log_level)
        self._i2c_addr = i2c_addr
        self._lcd: CharLCD = self._open()
        self._last_frame: List[str] = []
        self.logger.debug("Initialized 16x2 LCD at I2C address 0x%X", i2c_addr)

    def _open(self) -> CharLCD:
        """Construct a fresh CharLCD instance. Used for init and reinit."""
        return CharLCD(
            i2c_expander="PCF8574",
            address=self._i2c_addr,
            cols=self.COLS,
            rows=self.ROWS,
        )

    def reinit(self) -> None:
        """
        Rebuild the underlying CharLCD instance.

        Called by the supervisor loop after repeated write failures to
        attempt recovery from an I2C glitch without restarting the pod.
        """
        self.logger.warning("Reinitializing LCD at 0x%X", self._i2c_addr)
        try:
            self._lcd.close(clear=False)
        except Exception:
            pass
        self._lcd = self._open()
        self._last_frame = []

    def clear(self) -> None:
        """Clear the LCD display and reset the frame cache."""
        self.logger.debug("Clearing LCD display")
        self._lcd.clear()
        self._last_frame = []

    def write(
        self,
        lines: Union[str, List[str]],
        *,
        force: bool = False,
    ) -> None:
        """
        Write one or two lines of text to the LCD with frame diffing.

        If the incoming frame matches the last one written, this is a no-op
        (no I2C traffic, no flicker). Otherwise only changed rows are
        rewritten in place, padded to the full column width to overwrite
        leftover characters. When the row count changes or ``force`` is
        set, a full clear-and-redraw is performed.

        Args:
            lines: A single string (one row) or list of up to ROWS strings.
            force: Force a full clear-and-redraw even if the frame is unchanged.

        Raises:
            ValueError: If more than ROWS lines are provided.
        """
        normalized = self._normalize(lines)

        if not force and normalized == self._last_frame:
            return  # no-op: frame unchanged

        same_shape = (
            not force
            and self._last_frame
            and len(normalized) == len(self._last_frame)
        )

        if same_shape:
            for row, (new_line, old_line) in enumerate(zip(normalized, self._last_frame)):
                if new_line != old_line:
                    self._lcd.cursor_pos = (row, 0)
                    self._lcd.write_string(new_line.ljust(self.COLS))
        else:
            self._lcd.clear()
            time.sleep(0.01)
            for row, text in enumerate(normalized):
                self._lcd.cursor_pos = (row, 0)
                self._lcd.write_string(text.ljust(self.COLS))

        self._last_frame = normalized
        self.logger.info("Updated LCD with %d line(s): %r", len(normalized), normalized)

    def _normalize(self, lines: Union[str, List[str]]) -> List[str]:
        """Validate, coerce, and trim input lines to at most ROWS × COLS."""
        if isinstance(lines, str):
            lines_list: List[str] = [lines]
        else:
            lines_list = list(lines)

        if len(lines_list) > self.ROWS:
            raise ValueError(
                f"Cannot write {len(lines_list)} lines: max {self.ROWS} rows"
            )

        normalized: List[str] = []
        for idx, text in enumerate(lines_list):
            if len(text) > self.COLS:
                self.logger.warning(
                    "Line %d too long (%d chars): trimming to %d chars",
                    idx + 1,
                    len(text),
                    self.COLS,
                )
                text = text[: self.COLS]
            normalized.append(text)
        return normalized
