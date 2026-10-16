"""Pytest configuration for the TSS pricing lab.

Makes ``tss/lab`` (the directory containing ``pricing.py``) importable for the
test modules, so ``import pricing`` works regardless of the directory pytest
was invoked from.
"""

import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent

if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))
