import logging
import time
from typing import List, Union
from RPLCD.i2c import CharLCD
from utils.loggable import Loggable


class LCDController(Loggable):
    """
    Controller for a 16x2 I2C LCD display.

    Provides methods to write one or two lines of text, with automatic
    trimming and warnings for overlong strings, as well as clearing the display.
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
        self._lcd = CharLCD(
            i2c_expander="PCF8574",
            address=i2c_addr,
            cols=self.COLS,
            rows=self.ROWS,
        )
        self.logger.debug("Initialized 16x2 LCD at I2C address 0x%X", i2c_addr)

    def clear(self) -> None:
        """
        Clear the LCD display.
        """
        self.logger.info("Clearing LCD display")
        self._lcd.clear()

    def write(
        self,
        lines: Union[str, List[str]],
    ) -> None:
        """
        Write one or two lines of text to the LCD.

        If a single string is provided, it will be written on the first row.
        If a list of strings is provided, each entry corresponds to a row.
        Strings longer than 16 characters will be trimmed with a warning.

        Args:
            lines: A single string or list of up to two strings to display.

        Raises:
            ValueError: If more than two lines are provided.
        """
        # Normalize input
        if isinstance(lines, str):
            lines_list: List[str] = [lines]
        else:
            lines_list = lines

        if len(lines_list) > self.ROWS:
            raise ValueError(
                f"Cannot write {len(lines_list)} lines: max {self.ROWS} rows"
            )

        # Trim and warn
        for idx, text in enumerate(lines_list):
            if len(text) > self.COLS:
                self.logger.warning(
                    "Line %d too long (%d chars): trimming to %d chars",
                    idx + 1,
                    len(text),
                    self.COLS,
                )
                lines_list[idx] = text[: self.COLS]

        # Clear and write
        self.clear()
        time.sleep(0.05)
        for row, text in enumerate(lines_list):
            self._lcd.cursor_pos = (row, 0)
            self._lcd.write_string(text)

        self.logger.info("Updated LCD with %d line(s): %r", len(lines_list), lines_list)
