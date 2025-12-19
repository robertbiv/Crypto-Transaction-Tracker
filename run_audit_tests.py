#!/usr/bin/env python3
"""Run audit enhancement tests"""

import subprocess
import sys

print("=" * 60)
print("Running Audit Enhancement Tests")
print("=" * 60)

result = subprocess.run(
    [sys.executable, '-m', 'pytest', 'tests/test_audit_enhancements.py', '-v', '--tb=short'],
    cwd='.'
)

if result.returncode == 0:
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
else:
    print("\n" + "=" * 60)
    print("❌ Some tests failed. Review output above.")
    print("=" * 60)

sys.exit(result.returncode)
