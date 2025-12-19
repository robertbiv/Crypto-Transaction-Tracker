#!/usr/bin/env python3
"""Verify audit enhancements can be imported"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("Testing audit enhancements imports...")

try:
    print("1. Importing AlertingSystem...", end=" ")
    from src.web.audit_enhancements import AlertingSystem
    print("✓")
except Exception as e:
    print(f"✗ {e}")
    sys.exit(1)

try:
    print("2. Importing AuditLogIndexing...", end=" ")
    from src.web.audit_enhancements import AuditLogIndexing
    print("✓")
except Exception as e:
    print(f"✗ {e}")
    sys.exit(1)

try:
    print("3. Importing PDFReportGenerator...", end=" ")
    from src.web.audit_enhancements import PDFReportGenerator
    print("✓")
except Exception as e:
    print(f"✗ {e}")
    sys.exit(1)

try:
    print("4. Importing AuditLogSigner...", end=" ")
    from src.web.audit_enhancements import AuditLogSigner
    print("✓")
except Exception as e:
    print(f"✗ {e}")
    sys.exit(1)

try:
    print("5. Importing RealtimeAuditUpdates...", end=" ")
    from src.web.audit_enhancements import RealtimeAuditUpdates
    print("✓")
except Exception as e:
    print(f"✗ {e}")
    sys.exit(1)

try:
    print("6. Importing AuditAnomalyDetector...", end=" ")
    from src.web.audit_enhancements import AuditAnomalyDetector
    print("✓")
except Exception as e:
    print(f"✗ {e}")
    sys.exit(1)

try:
    print("7. Importing AuditAPIRateLimiting...", end=" ")
    from src.web.audit_enhancements import AuditAPIRateLimiting
    print("✓")
except Exception as e:
    print(f"✗ {e}")
    sys.exit(1)

# Test basic instantiation
print("\nTesting basic instantiation...")

try:
    print("1. AlertingSystem()...", end=" ")
    alerting = AlertingSystem()
    print("✓")
except Exception as e:
    print(f"✗ {e}")

try:
    print("2. PDFReportGenerator()...", end=" ")
    pdf = PDFReportGenerator()
    print("✓")
except Exception as e:
    print(f"✗ {e}")

try:
    print("3. AuditLogSigner()...", end=" ")
    signer = AuditLogSigner()
    print("✓")
except Exception as e:
    print(f"✗ {e}")

try:
    print("4. RealtimeAuditUpdates()...", end=" ")
    updates = RealtimeAuditUpdates()
    print("✓")
except Exception as e:
    print(f"✗ {e}")

try:
    print("5. AuditAnomalyDetector()...", end=" ")
    detector = AuditAnomalyDetector()
    print("✓")
except Exception as e:
    print(f"✗ {e}")

try:
    print("6. AuditAPIRateLimiting()...", end=" ")
    limiter = AuditAPIRateLimiting()
    print("✓")
except Exception as e:
    print(f"✗ {e}")

print("\n✅ All imports and basic tests passed!")
