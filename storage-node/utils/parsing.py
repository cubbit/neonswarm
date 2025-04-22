import argparse


def parse_size(size_str):
    """Parse size strings like '1K', '2M', etc."""
    if not isinstance(size_str, str):
        return size_str

    size_str = size_str.upper()
    multipliers = {"K": 1024, "M": 1024 * 1024, "G": 1024 * 1024 * 1024}

    for suffix, multiplier in multipliers.items():
        if size_str.endswith(suffix):
            try:
                return int(float(size_str[:-1]) * multiplier)
            except ValueError:
                raise argparse.ArgumentTypeError(f"Invalid size format: {size_str}")

    # If no suffix, try to convert directly to int
    try:
        return int(size_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid size format: {size_str}")
