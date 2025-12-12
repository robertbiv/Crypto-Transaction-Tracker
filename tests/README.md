# Crypto Tax Engine - Test Suite

This directory contains the comprehensive test suite for the Crypto Tax Engine. The tests have been split into multiple modules for better maintainability and organization.

## Running Tests

### 1. Run All Tests (Recommended)
To run the full test suite, execute the unified runner from the project root:

```bash
# Windows (PowerShell)
& ".venv\Scripts\python.exe" tests/unit_test.py

# Linux/Mac
python3 tests/unit_test.py
```

This runner:
- Sets `TEST_MODE=1` automatically (reduces API rate limit waits to 1 second).
- Runs all test modules sequentially.
- Provides a summary of results.

### 2. Run Individual Test Modules
You can run specific test modules using `unittest`:

```bash
# Example: Run only integration tests
python -m unittest tests/test_integrations.py

# Example: Run core compliance tests
python -m unittest tests/test_core_compliance.py
```

### 3. Run with Pytest
If you prefer `pytest`:

```bash
pytest tests/
```

## Test Structure

The massive `unit_test.py` has been split into the following modules:

| Module | Description |
|--------|-------------|
| `unit_test.py` | **Main Runner**. Orchestrates all other tests. |
| `test_common.py` | Shared utilities, imports, and mock setups. |
| `test_core_compliance.py` | US tax rules, wash sales, loss limits. |
| `test_data_processing.py` | CSV parsing, validation, and ingestion. |
| `test_integrations.py` | API calls, blockchain explorers, rate limiting. |
| `test_defi_features.py` | Liquidity pools, swaps, advanced DeFi logic. |
| `test_fees_and_precision.py` | Multi-coin fees, decimal precision handling. |
| `test_migration_and_multi_year.py` | Year-over-year carryovers, migration logic. |
| `test_reporting_and_export.py` | FBAR, Form 8949 generation, CSV exports. |
| `test_reviewer_and_fixer.py` | Interactive fixer and tax reviewer logic. |
| `test_config_and_setup.py` | Configuration loading, setup wizards. |
| `test_system_stability.py` | Architecture checks, import order, stability. |
| `test_edge_cases.py` | Stress tests, large datasets, malformed data. |
| `test_chaos_and_monte_carlo.py` | Random simulations and chaos testing. |
| `test_wallet_compatibility.py` | Wallet export format compatibility. |
| `test_price_fetcher.py` | Price fetching integration tests. |

## Environment Variables

- `TEST_MODE=1`: Reduces API rate limit wait times from 60s to 1s. (Automatically set by `unit_test.py`).
- `STRESS_TEST=1`: Enables full-scale stress tests (100k+ iterations). Default is reduced scale for CI speed.

## Troubleshooting

- **Import Errors**: Ensure you run tests from the **project root directory**, not inside the `tests/` folder.
- **API Rate Limits**: Integration tests mock API calls where possible, but some may hit live endpoints. `TEST_MODE=1` handles rate limits gracefully.
