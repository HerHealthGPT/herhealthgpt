"""Make ``scripts/`` and this directory importable for the script tests."""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
for path in (_HERE, _HERE.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
