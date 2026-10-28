"""
test_enterprise_architecture.py - Entry point delegating to tests/test_enterprise_architecture.py.
"""

import sys
import unittest
from pathlib import Path

WEEK1_DIR = Path(__file__).resolve().parent
if str(WEEK1_DIR) not in sys.path:
    sys.path.insert(0, str(WEEK1_DIR))

from tests.test_enterprise_architecture import (
    TestGuardrailsChainOfResponsibility,
    TestOrchestrator,
    TestRoutingStrategyPattern,
    TestStorageAbstraction,
    TestToolAndMCPRegistry,
)

if __name__ == "__main__":
    unittest.main()
