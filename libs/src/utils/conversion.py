#!/usr/bin/env python3
"""
Utility for converting hex color strings to RGB tuples.
"""

import re
from typing import Tuple


class ConversionException(ValueError):
    """
    Raised when a string cannot be converted to an RGB tuple.
    """

    def __init__(self, hex_string: str) -> None:
        super().__init__(f"Invalid hex color string: {hex_string!r}")


def hex_to_rgb(hex_string: str) -> Tuple[int, int, int]:
    """
    Convert a hex color code into an (R, G, B) tuple.

    Supports both 6-digit (e.g. 'FFA07A' or '#FFA07A') and 3-digit
    shorthand (e.g. 'FA7' or '#FA7') formats.

    :param hex_string: The hex color string to convert.
    :returns: A tuple of three ints in the range 0–255.
    :raises ConversionException: If the input is not a valid hex color.
    """
    s = hex_string.strip().lstrip("#")
    # Expand 3-digit shorthand to 6-digit form, e.g. 'FA7' → 'FFAA77'
    if re.fullmatch(r"[0-9A-Fa-f]{3}", s):
        s = "".join(ch * 2 for ch in s)

    if not re.fullmatch(r"[0-9A-Fa-f]{6}", s):
        raise ConversionException(hex_string)

    return tuple(int(s[i : i + 2], 16) for i in (0, 2, 4))
