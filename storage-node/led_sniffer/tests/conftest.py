"""
Test configuration.

Stubs out hardware modules (scapy, board, adafruit_*) so the test suite
can run on any machine without Raspberry Pi specific dependencies. The
stubs live only in ``sys.modules`` during test collection.

Also puts ``libs/`` and ``storage-node/led_sniffer/src/`` on ``sys.path``
so tests can import modules without an editable install.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock


_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent / "src"
_LIBS_SRC = _HERE.parents[2] / "libs" / "src"

for p in (_SRC, _LIBS_SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


# Hardware / capture modules stubbed for unit tests.
for mod in (
    "scapy",
    "scapy.all",
    "board",
    "adafruit_pixelbuf",
    "adafruit_raspberry_pi5_neopixel_write",
    "adafruit_led_animation",
    "adafruit_led_animation.animation",
):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
