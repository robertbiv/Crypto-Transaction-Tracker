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


