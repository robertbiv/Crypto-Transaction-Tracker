"""
CRYPTO TAX ENGINE - UNIFIED TEST RUNNER
This file orchestrates all test suites, running them sequentially.
Individual test files can also be run independently.
"""
import unittest
import sys
import os
from pathlib import Path

# Set TEST_MODE for faster rate limit retries during testing (5s instead of 60s)
os.environ['TEST_MODE'] = '1'

# Print test suite information
print("\n" + "="*70)
print("CRYPTO TAX ENGINE - COMPREHENSIVE TEST SUITE")
print("="*70)
print("Test Organization:")
print("  • Core Compliance: US tax rules, losses, wash sales")
print("  • Data Processing: CSV parsing, ingestion, validation")
print("  • Integrations: APIs, blockchains, external services")
print("  • DeFi Features: DeFi transactions, LP tokens")
print("  • Fees & Precision: Multi-coin fees, rounding")
print("  • Migration & Multi-Year: 2025 migration, inventory")
print("  • Reporting & Export: Forms, FBAR, exports")
print("  • Reviewer & Fixer: Tax reviewer, interactive fixer")
print("  • Config & Setup: Configuration, setup wizards")
print("  • System Stability: Architecture, interruptions")
print("  • Edge Cases: Extreme values, malformed data")
print("  • Chaos Testing: Monte Carlo, random scenarios")
print("  • Wallet Compatibility: Wallet format tests")
print("  • Price Fetcher: Price fetching integration")
print("")
print("NOTE: Large-scale tests (100k iterations) are reduced to 1k for CI.")
print("      Set STRESS_TEST=1 environment variable to run full tests.")
print("      TEST_MODE is enabled: Rate limit retries capped at 1 second.")
print("="*70 + "\n")

def run_test_suite(module_name, description):
    """Run a single test module and return results"""
    print(f"\n{'='*70}")
    print(f"Running: {description}")
    print(f"Module: {module_name}")
    print('='*70)
    
    try:
        # Import the test module
        module = __import__(module_name)
        
        # Create test suite
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(module)
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=1)
        result = runner.run(suite)
        
        return result
    except Exception as e:
        print(f"ERROR loading {module_name}: {e}")
        return None


def main():
    """Run all test suites sequentially"""
    
    # Test suite definitions (in order of execution)
    test_suites = [
        ('test_core_compliance', 'Core US Tax Compliance'),
        ('test_data_processing', 'Data Ingestion and Processing'),
        ('test_integrations', 'External Integrations'),
        ('test_defi_features', 'DeFi and Advanced Transactions'),
        ('test_fees_and_precision', 'Fee Handling and Precision'),
        ('test_migration_and_multi_year', 'Migration and Multi-Year Processing'),
        ('test_reporting_and_export', 'Report Generation and Export'),
        ('test_reviewer_and_fixer', 'Tax Reviewer and Interactive Fixer'),
        ('test_config_and_setup', 'Configuration and Setup'),
        ('test_system_stability', 'System Stability and Architecture'),
        ('test_edge_cases', 'Edge Cases and Stress Tests'),
        ('test_chaos_and_monte_carlo', 'Chaos Testing and Monte Carlo'),
        ('test_wallet_compatibility', 'Wallet Format Compatibility'),
        ('test_price_fetcher', 'Price Fetcher Integration'),
    ]
    
    # Track results
    all_results = []
    total_tests = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0
    
    # Run each suite
    for module_name, description in test_suites:
        result = run_test_suite(module_name, description)
        
        if result:
            all_results.append((module_name, result))
            total_tests += result.testsRun
            total_failures += len(result.failures)
            total_errors += len(result.errors)
            total_skipped += len(result.skipped)
    
    # Print summary
    print("\n" + "="*70)
    print("FINAL TEST SUMMARY")
    print("="*70)
    print(f"Total Test Suites: {len(test_suites)}")
    print(f"Total Tests Run: {total_tests}")
    print(f"Passed: {total_tests - total_failures - total_errors - total_skipped}")
    print(f"Failed: {total_failures}")
    print(f"Errors: {total_errors}")
    print(f"Skipped: {total_skipped}")
    print("="*70)
    
    # Per-suite summary
    if all_results:
        print("\nPer-Suite Results:")
        for module_name, result in all_results:
            status = "✓ PASS" if (len(result.failures) == 0 and len(result.errors) == 0) else "✗ FAIL"
            print(f"  {status} {module_name}: {result.testsRun} tests")
    
    # Exit code
    if total_failures > 0 or total_errors > 0:
        print("\n⚠️  Some tests failed. See details above.")
        sys.exit(1)
    else:
        print("\n✅ All tests passed!")
        sys.exit(0)


if __name__ == '__main__':
    main()
