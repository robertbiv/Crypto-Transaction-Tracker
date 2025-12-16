
import pytest
import sys

def run_tests():
    """Run test suite"""
    print("Running full test suite in-process...")
    try:
        # pytest.main returns an exit code. 0 for success.
        exit_code = pytest.main(['tests/', '-v'])
        return exit_code == 0
    except Exception as e:
        print(f"An error occurred while running tests: {e}")
        return False

if __name__ == '__main__':
    if run_tests():
        print("All tests passed.")
        sys.exit(0)
    else:
        print("One or more tests failed.")
        sys.exit(1)
