#!/usr/bin/env python3

"""
Continuously display disk usage on a 16×2 I2C LCD with optional logging.
"""

import argparse
import logging
import shutil
import sys
import time

from RPLCD.i2c import CharLCD
from utils.parsing import sizeof


# Default configuration constants
DEFAULT_I2C_ADDRESS = 0x27
DEFAULT_INTERVAL = 10.0
LCD_COLS = 16
LCD_ROWS = 2


class LCDDiskMonitor:
    """Monitor disk usage and display it on an I2C LCD."""

    def __init__(self, path, i2c_addr=DEFAULT_I2C_ADDRESS, interval=DEFAULT_INTERVAL):
        self._path = path
        self._interval = interval

        logging.debug(
            "Initializing LCDDiskMonitor: path=%s, address=0x%X, " "interval=%.1fs",
            path,
            i2c_addr,
            interval,
        )

        self.lcd = CharLCD(
            i2c_expander="PCF8574", address=i2c_addr, cols=LCD_COLS, rows=LCD_ROWS
        )

    def _get_disk_usage(self):
        """Return (used_bytes, total_bytes) for the filesystem path."""
        try:
            usage = shutil.disk_usage(self._path)
        except (FileNotFoundError, PermissionError) as ex:
            logging.error("Cannot access path %s: %s", self._path, ex)
            sys.stderr.write(f"Error: {ex}\n")
            sys.exit(1)

        logging.debug(
            "Disk usage for %s: total=%d, used=%d, free=%d",
            self._path,
            usage.total,
            usage.used,
            usage.free,
        )

        return usage.used, usage.total

    def _lcd_write(self, used, total):
        """Write the formatted usage to the LCD."""
        used_str = sizeof(used)
        total_str = sizeof(total)

        logging.info("Updating LCD display to '%s/%s'", used_str, total_str)

        time.sleep(0.05)

        self.lcd.clear()
        self.lcd.write_string("Storage")
        self.lcd.crlf()
        self.lcd.write_string(f"{used_str}/{total_str}")

    def start(self):
        """Begin polling and updating the LCD until interrupted."""
        logging.info(
            "Starting disk monitor on %s every %.1fs", self._path, self._interval
        )
        try:
            while True:
                used, total = self._get_disk_usage()
                self._lcd_write(used, total)
                time.sleep(self._interval)
        except KeyboardInterrupt:
            logging.info("Interrupted; clearing LCD and exiting")
            self.lcd.clear()
            sys.exit(0)


def main():
    """Parse arguments and run the monitor."""
    parser = argparse.ArgumentParser(
        description=("Display used/total storage on a 16×2 I2C LCD" " with logging.")
    )
    parser.add_argument(
        "path", help=("Mount point or path to check (e.g. /, /mnt/data, C:\\).")
    )
    parser.add_argument(
        "-a",
        "--address",
        type=lambda x: int(x, 0),
        default=DEFAULT_I2C_ADDRESS,
        help="I2C address of the LCD (default: 0x27).",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL,
        help="Seconds between updates (default: 10.0).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging to the console.",
    )
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    monitor = LCDDiskMonitor(
        path=args.path, i2c_addr=args.address, interval=args.interval
    )
    monitor.start()


if __name__ == "__main__":
    main()
