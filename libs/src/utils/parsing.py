import argparse
import re
from typing import Union

# Pre-compile regex and define multipliers for units (supports '', 'B', 'K', 'KB', 'M', 'MB', etc.)
_SIZE_RE = re.compile(r"^\s*(?P<number>\d+(?:\.\d*)?)\s*(?P<unit>[KMGTPEZY]?B?|B)?\s*$")
_SIZE_UNITS: dict[str, int] = {
    "": 1,
    "B": 1,
    "K": 1024,
    "KB": 1024,
    "M": 1024**2,
    "MB": 1024**2,
    "G": 1024**3,
    "GB": 1024**3,
    "T": 1024**4,
    "TB": 1024**4,
    "P": 1024**5,
    "PB": 1024**5,
    "E": 1024**6,
    "EB": 1024**6,
    "Z": 1024**7,
    "ZB": 1024**7,
    "Y": 1024**8,
    "YB": 1024**8,
}


def parse_size(size_str: Union[str, int, float]) -> int:
    """
    Parse a human-readable size (e.g. "1K", "2MB", "50B") into an integer byte count.

    :param size_str: A string with optional unit suffix, or a numeric type.
    :return: Number of bytes as an integer.
    :raises argparse.ArgumentTypeError: If the format is invalid.
    """
    if isinstance(size_str, (int, float)):
        return int(size_str)

    s = size_str.strip().upper()
    m = _SIZE_RE.match(s)
    if not m:
        raise argparse.ArgumentTypeError(f"Invalid size format: '{size_str}'")

    number = float(m.group("number"))
    unit = (m.group("unit") or "").upper()

    if unit not in _SIZE_UNITS:
        raise argparse.ArgumentTypeError(f"Unknown size unit '{unit}' in '{size_str}'")

    return int(number * _SIZE_UNITS[unit])


def sizeof(num: Union[int, float], suffix: str = "B") -> str:
    """
    Convert a byte count into a human-readable string (e.g. 1536 -> "1.5KB").

    :param num: Number of bytes.
    :param suffix: Optional suffix to append (default "B").
    :return: Human-readable size string.
    """
    abs_num = abs(num)
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs_num < 1024.0:
            return f"{num:.1f}{unit}{suffix}"
        num /= 1024.0
        abs_num /= 1024.0
    return f"{num:.1f}Y{suffix}"
