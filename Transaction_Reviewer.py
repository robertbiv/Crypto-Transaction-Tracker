"""Legacy module shim for Transaction_Reviewer.

Points to the src.core.reviewer module for backward compatibility 
with tests that import Transaction_Reviewer directly.
"""

import sys
import importlib

# Import the actual module from its new location
try:
    _reviewer = importlib.import_module("src.core.reviewer")
except ImportError:
    # Fallback to trying src.tools.review_fixer
    try:
        _reviewer = importlib.import_module("src.tools.review_fixer")
    except ImportError:
        # Last resort: try just the module name
        _reviewer = importlib.import_module("review_fixer")

# Replace this module in sys.modules so that monkeypatching and re-imports work
sys.modules[__name__] = _reviewer
