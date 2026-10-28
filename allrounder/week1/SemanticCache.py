"""
SemanticCache.py - Backward Compatibility Shim.
All implementations have been reorganized into the `caching/` package following
the Cache-Aside and Strategy Design Patterns.
"""

import sys
from pathlib import Path

WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

from caching import BaseCache, CacheEntry, SemanticCache

__all__ = ["BaseCache", "CacheEntry", "SemanticCache"]

if __name__ == "__main__":
    cache = SemanticCache()
    print("SemanticCache initialized. Stats:", cache.stats())
