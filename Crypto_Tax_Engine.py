"""Legacy module shim for Crypto_Tax_Engine.

Points to the refactored src.core.engine module for backward compatibility
with existing code and tests that import Crypto_Tax_Engine directly.
"""

import sys
import importlib

# Import the actual module
_engine = importlib.import_module("src.core.engine")

# Replace this module in sys.modules so that monkeypatching and re-imports work
sys.modules[__name__] = _engine
