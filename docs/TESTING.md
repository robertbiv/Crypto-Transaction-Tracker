# Testing Guide

## Quick Start

Run all tests:
```bash
python -m pytest -q
```

## Test Categories

### CLI & Web UI Concurrency Tests
**Purpose**: Ensure simultaneous CLI and Web UI usage doesn't corrupt data

**File**: `tests/test_cli_web_ui_concurrency.py`

**Run**:
```bash
# All concurrency tests
python -m pytest tests/test_cli_web_ui_concurrency.py -v

# Specific test
python -m pytest tests/test_cli_web_ui_concurrency.py::test_cli_web_ui_concurrent_writes -v

# By marker
python -m pytest -m concurrency -v
```

**What It Tests**:
- ✅ CLI writes while Web UI writes (concurrent inserts)
- ✅ CLI reads while Web UI reads (consistent reads)
- ✅ CLI updates while Web UI updates (no corruption)
- ✅ Multiple concurrent batch writes
- ✅ No dirty data reads (partial transactions never visible)
- ✅ WAL mode enabled for robustness

### CLI Expanded Tests
**Purpose**: Comprehensive coverage of all CLI commands with parity to Web UI

**File**: `tests/test_cli_expanded.py`

**Status**: Ready to integrate (import issues resolved separately)

**Included Test Groups**:
- Transaction CRUD operations (add, update, delete, list)
- File uploads, templates, reprocessing
- Reports, warnings, statistics
- Configuration and wallet management
- API key management and testing
- Backup and restore operations
- Log management (downloads, redaction)
- Diagnostics and health checks
- Scheduler configuration and testing
- Accuracy mode and ML features

### Running Specific Test Files

```bash
# Concurrency tests (fully integrated)
python -m pytest tests/test_cli_web_ui_concurrency.py -v

# Original CLI tests
python -m pytest tests/test_cli.py -v

# Core compliance tests
python -m pytest tests/test_core_compliance.py -v

# Web UI tests
python -m pytest tests/test_web_ui.py -v
```

## Markers

Available pytest markers:
```bash
# All concurrency tests
python -m pytest -m concurrency -v

# All slow tests
python -m pytest -m slow -v

# Skip slow tests
python -m pytest -m "not slow" -q
```

## Common Issues & Solutions

### ImportError for cli.py
Some test files may fail importing cli due to dependencies. Use concurrency tests which are self-contained:
```bash
python -m pytest tests/test_cli_web_ui_concurrency.py -v
```

### Database Locks
Tests use isolated temp directories and WAL mode. If you see lock errors:
1. Close any open database connections
2. Delete `.pytest_cache/` directory
3. Re-run tests

### Timeout Issues
Tests use 10-second database connection timeouts. On slow systems, increase:
```python
sqlite3.connect(str(path), timeout=15)
```

## CI/CD Integration

For continuous integration, run:
```bash
# Quick validation
python -m pytest tests/test_cli_web_ui_concurrency.py -v --tb=short

# Full suite
python -m pytest -q --tb=line
```

## Adding New Tests

1. Place test file in `tests/` directory with `test_` prefix
2. Use pytest conventions (`test_*` functions, `cli_env` fixtures)
3. Add appropriate markers (@pytest.mark.concurrency, @pytest.mark.slow)
4. Run: `python -m pytest tests/test_yourfile.py -v`

## Performance Notes

- **Concurrency tests**: ~0.4 seconds total
- **Full CLI tests**: ~5-10 seconds (with actual CLI imports)
- **WAL mode**: Enables safe concurrent access without slowdown
- **Timeout settings**: 10 seconds per database operation (adjust as needed)
