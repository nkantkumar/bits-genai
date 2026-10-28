"""
test_caching.py - Entry point delegating to tests/test_caching.py.
"""

import sys
from pathlib import Path

WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

from tests.test_caching import run_caching_tests

if __name__ == "__main__":
    run_caching_tests()
