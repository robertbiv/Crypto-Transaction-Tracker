#!/usr/bin/env python3
"""Run audit enhancement integration tests"""

import subprocess
import sys

result = subprocess.run(
    [sys.executable, '-m', 'pytest', 'tests/test_audit_enhancements_integration.py', '-v', '--tb=short'],
    cwd='.'
)

sys.exit(result.returncode)
