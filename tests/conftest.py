"""
================================================================================
PYTEST CONFIGURATION
================================================================================

Pytest configuration and shared fixtures for the entire test suite.

Global Fixtures:
    - set_test_mode: Automatically sets TEST_MODE=1 for faster API retries
                     during testing (reduces timeout delays)
    - cleanup_global_database: Removes crypto_master.db before test session
                               to prevent test pollution and ensure clean state

Path Configuration:
    - Adds project root to sys.path for legacy module imports
    - Ensures all tests can import from src/ without relative imports

Scope:
    Session-scoped fixtures run once per entire pytest invocation,
    shared across all test modules for efficiency.

Author: robertbiv
================================================================================
"""
import os
import sys
import pytest
from pathlib import Path

# Ensure project root is on sys.path for legacy module imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

@pytest.fixture(scope="session", autouse=True)
def set_test_mode():
    """Automatically set TEST_MODE=1 for all pytest runs to speed up API retries."""
    os.environ['TEST_MODE'] = '1'
    yield
    # Clean up is optional since the process ends, but good practice
    if 'TEST_MODE' in os.environ:
        del os.environ['TEST_MODE']

@pytest.fixture(scope="session", autouse=True)
def cleanup_global_database():
    """Remove global database before test session starts to prevent test pollution."""
    global_db = PROJECT_ROOT / 'crypto_master.db'
    if global_db.exists():
        global_db.unlink()
    yield
    # Optionally clean up after tests too
    if global_db.exists():
        global_db.unlink()


