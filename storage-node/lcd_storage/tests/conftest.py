"""
Test configuration.

Stubs out hardware modules (RPLCD, gpiozero, kubernetes) so the test suite can
run on any machine without Raspberry Pi specific dependencies installed. The
stubs live only in ``sys.modules`` during test collection and do not affect
the actual runtime.

Also puts the ``libs/`` and ``storage-node/lcd_storage/src/`` directories on
``sys.path`` so tests can import ``render``, ``lcd.lcd``, ``utils.parsing``, etc.
without requiring an editable install.
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


# Stub out hardware-only modules. Any attribute access on these returns a
# MagicMock, which is enough for the unit tests to exercise LCDController's
# diffing logic and the pure render module.
for mod in (
    "RPLCD",
    "RPLCD.i2c",
    "gpiozero",
    "gpiozero.pins",
    "gpiozero.pins.lgpio",
    "kubernetes",
    "kubernetes.client",
    "kubernetes.client.exceptions",
    "kubernetes.config",
):
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()
