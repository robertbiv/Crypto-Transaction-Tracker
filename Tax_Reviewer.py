"""Legacy module shim for Tax_Reviewer.

Points to the src.tools.review_fixer module or a reviewer module for backward
compatibility with tests that import Tax_Reviewer directly.
"""

import sys
import importlib

# Try to import the actual module (could be src.tools.review_fixer or similar)
try:
    _reviewer = importlib.import_module("src.tools.review_fixer")
except ImportError:
    # Fallback to trying just the module name
    _reviewer = importlib.import_module("review_fixer")

# Replace this module in sys.modules so that monkeypatching and re-imports work
sys.modules[__name__] = _reviewer
