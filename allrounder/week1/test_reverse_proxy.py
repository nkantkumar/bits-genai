"""
test_reverse_proxy.py - Entry point delegating to tests/test_reverse_proxy.py.
"""

import sys
from pathlib import Path

WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

from tests.test_reverse_proxy import check_nginx_health, test_completion_through_nginx

if __name__ == "__main__":
    if check_nginx_health():
        test_completion_through_nginx()
