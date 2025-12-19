# Quick Test Reference Guide

## 🚀 Quick Commands

### Run Everything (Full Test Suite)
```bash
.venv\Scripts\python.exe -m pytest tests/ -v
```

### Run Only New Tier 1 & Tier 2 Tests (39 tests, ~4 seconds)
```bash
.venv\Scripts\python.exe -m pytest \
  tests/test_database_error_recovery.py \
  tests/test_backup_consistency.py \
  tests/test_input_validation.py \
  tests/test_schema_and_encryption.py \
  tests/test_performance_and_wallets.py \
  -v
```

### Run Concurrency Tests Only
```bash
.venv\Scripts\python.exe -m pytest -m concurrency -v
```

---

## 📋 Test Bundles by Use Case

### 🔍 **For Security Review**
Tests for input validation and injection prevention:
```bash
.venv\Scripts\python.exe -m pytest tests/test_input_validation.py -v
```
**Includes**: SQL injection, Unicode handling, boundary values, null handling

---

### 💾 **For Backup/Recovery Testing**
Tests for backup reliability and disaster recovery:
```bash
.venv\Scripts\python.exe -m pytest tests/test_backup_consistency.py -v
```
**Includes**: Concurrent backup safety, restore integrity, backup chains

---

### ⚡ **For Performance Verification**
Tests for query performance and scaling:
```bash
.venv\Scripts\python.exe -m pytest tests/test_performance_and_wallets.py -v
```
**Includes**: Performance baseline, degradation detection, latency percentiles

---

### 🔗 **For Concurrency & Data Integrity**
Tests for multi-threaded safety:
```bash
.venv\Scripts\python.exe -m pytest -m concurrency -v
```
**Includes**: CLI/Web interaction, concurrent writes, isolation levels

---

### 🛡️ **For Error Recovery & Resilience**
Tests for fault tolerance:
```bash
.venv\Scripts\python.exe -m pytest tests/test_database_error_recovery.py -v
```
**Includes**: Rollback on errors, connection leaks, corruption detection

---

### 🗂️ **For Schema & Audit Safety**
Tests for data durability and audit trails:
```bash
.venv\Scripts\python.exe -m pytest tests/test_schema_and_encryption.py -v
```
**Includes**: Schema migrations, audit logging, encryption transparency

---

## 📊 Test Statistics

| File | Tests | Duration | Category |
|------|-------|----------|----------|
| test_database_error_recovery.py | 8 | ~0.5s | Error Recovery |
| test_backup_consistency.py | 7 | ~0.8s | Backup Safety |
| test_input_validation.py | 13 | ~0.3s | Input Security |
| test_schema_and_encryption.py | 8 | ~0.8s | Schema & Audit |
| test_performance_and_wallets.py | 6 | ~1.6s | Performance |
| **TOTAL** | **39** | **~4.0s** | **All Categories** |

---

## ✅ Coverage by Scenario

### Scenario 1: Pre-Commit (Fast)
```bash
# Run just security and error recovery (~1 second)
.venv\Scripts\python.exe -m pytest \
  tests/test_input_validation.py \
  tests/test_database_error_recovery.py \
  -v --tb=short
```

### Scenario 2: Pre-Release (Complete)
```bash
# Run all tests with coverage
.venv\Scripts\python.exe -m pytest tests/ -v \
  --cov=src --cov-report=html --cov-report=term-missing
```

### Scenario 3: Production Monitoring (Critical Only)
```bash
# Run only production-critical tests
.venv\Scripts\python.exe -m pytest \
  tests/test_backup_consistency.py \
  tests/test_database_error_recovery.py \
  -v
```

### Scenario 4: Security Audit
```bash
# Run all security-related tests
.venv\Scripts\python.exe -m pytest \
  tests/test_input_validation.py \
  tests/test_schema_and_encryption.py \
  -v -k "injection or validation or encryption or audit"
```

---

## 🐛 Debugging Specific Tests

### Run single test with full output
```bash
.venv\Scripts\python.exe -m pytest tests/test_input_validation.py::test_sql_injection_in_id -vv
```

### Run with full traceback
```bash
.venv\Scripts\python.exe -m pytest tests/test_database_error_recovery.py --tb=long
```

### Stop on first failure
```bash
.venv\Scripts\python.exe -m pytest tests/ -x -v
```

### Show print statements
```bash
.venv\Scripts\python.exe -m pytest tests/ -s -v
```

---

## 📈 Performance Benchmarking

Run performance tests and save baseline:
```bash
# Save baseline
.venv\Scripts\python.exe -m pytest tests/test_performance_and_wallets.py -v > baseline.txt

# Compare against baseline later
.venv\Scripts\python.exe -m pytest tests/test_performance_and_wallets.py -v > current.txt
diff baseline.txt current.txt
```

---

## 🔄 Continuous Monitoring

### Watch mode (requires pytest-watch)
```bash
pip install pytest-watch
ptw -- tests/ -v
```

### Parallel execution (requires pytest-xdist)
```bash
pip install pytest-xdist
.venv\Scripts\python.exe -m pytest tests/ -n auto -v
```

---

## 🎯 Test Markers

Tests are marked by category:

- `@pytest.mark.concurrency` - Multi-threaded tests
- `@pytest.mark.slow` - Tests taking >1s
- `@pytest.mark.security` - Security-related tests

Run by marker:
```bash
.venv\Scripts\python.exe -m pytest -m concurrency -v
.venv\Scripts\python.exe -m pytest -m "not slow" -v
```

---

## 💡 Tips & Tricks

### Run tests matching keyword
```bash
.venv\Scripts\python.exe -m pytest -k "backup" -v
.venv\Scripts\python.exe -m pytest -k "injection or unicode" -v
```

### Generate HTML report
```bash
pip install pytest-html
.venv\Scripts\python.exe -m pytest tests/ --html=report.html
```

### Generate JSON report for CI
```bash
.venv\Scripts\python.exe -m pytest tests/ --json-report --json-report-file=report.json
```

---

## ⚠️ Common Issues

**Issue**: Tests timeout on Windows
```bash
# Solution: Increase timeout
.venv\Scripts\python.exe -m pytest tests/ --timeout=30
```

**Issue**: Thread-related flakiness
```bash
# Solution: Run sequential instead of parallel
.venv\Scripts\python.exe -m pytest tests/ -n0
```

**Issue**: Database locked errors
```bash
# Solution: Ensure no other pytest processes are running
taskkill /IM python.exe /F  # Use with caution!
```

---

## 📞 For Questions

Refer to:
- [docs/COMPREHENSIVE_TEST_SUITE.md](COMPREHENSIVE_TEST_SUITE.md) - Full test documentation
- [docs/TESTING.md](TESTING.md) - Original test guide
- [pytest.ini](../pytest.ini) - pytest configuration
