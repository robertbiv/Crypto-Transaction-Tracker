import os
import pytest

@pytest.fixture(scope="session", autouse=True)
def set_test_mode():
    """Automatically set TEST_MODE=1 for all pytest runs to speed up API retries."""
    os.environ['TEST_MODE'] = '1'
    yield
    # Clean up is optional since the process ends, but good practice
    if 'TEST_MODE' in os.environ:
        del os.environ['TEST_MODE']
