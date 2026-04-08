"""
Pure rendering functions for the LCD display.

Kept free of hardware imports so it can be unit-tested on any machine.
"""

from typing import List, Optional

from utils.parsing import sizeof

COLS: int = 16


def render_frame(
    node_label: str,
    spec_replicas: Optional[int],
    disk_used: Optional[int],
    disk_total: Optional[int],
    deployment_name: str,
) -> List[str]:
    """
    Produce the two LCD lines for the normal operating state.

    Args:
        node_label: Short node identifier, e.g. "node-1".
        spec_replicas: Desired replica count from the Deployment spec.
            None means "unknown" (treated as OFF for display).
        disk_used: Used bytes, or None if unavailable.
        disk_total: Total bytes, or None if unavailable.
        deployment_name: Deployment name for the OFF message.

    Returns:
        A list of exactly two strings, each at most COLS characters.
    """
    if not spec_replicas:
        off_msg = f"{deployment_name} is OFF"
        return [_trim(off_msg), ""]

    if disk_used is None or disk_total is None:
        return [_trim(node_label), "disk: n/a"]

    line1 = _trim(node_label)
    line2 = _trim(f"{sizeof(disk_used)}/{sizeof(disk_total)}")
    return [line1, line2]


def render_error(short_label: str, detail: str = "") -> List[str]:
    """
    Produce the two LCD lines for an error state.

    Args:
        short_label: Short identifier, e.g. "K8S ERROR".
        detail: Optional second-line detail.

    Returns:
        A list of exactly two strings, each at most COLS characters.
    """
    return [_trim(short_label), _trim(detail)]


def _trim(text: str) -> str:
    """Trim a string to fit on one LCD row."""
    if len(text) <= COLS:
        return text
    return text[:COLS]
