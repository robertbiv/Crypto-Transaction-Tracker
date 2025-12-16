"""
================================================================================
TEST UTILITY: Test File Splitter
================================================================================

Utility script to organize and split monolithic test files into logical modules.

Original monolithic test file (unit_test.py) was split into organized categories:
    - test_core_compliance.py: US tax law compliance tests
    - test_data_processing.py: CSV ingestion and normalization
    - test_integrations.py: External API and blockchain integration
    - test_defi_features.py: DeFi protocol support
    - test_comprehensive_scenarios.py: Complex multi-step workflows
    - test_web_ui.py: Web interface and API endpoints
    - test_api_errors.py: Error handling and edge cases
    - test_encryption_security.py: Security and encryption
    - test_edge_cases.py: Boundary conditions and stress tests
    - test_reporting_and_export.py: Output formats and reports

Features:
    - Automatically groups test classes by functionality
    - Preserves imports and fixtures
    - Generates proper file headers
    - Maintains test isolation

Usage:
    python tests/split_tests.py

Author: robertbiv
================================================================================
"""
import re

# Read the original file
with open('unit_test.py', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# Test class groupings
test_groups = {
    'test_core_compliance.py': {
        'description': 'Core US Tax Compliance Tests',
        'classes': [
            'TestAdvancedUSCompliance',
            'TestUSLosses',
            'TestUSComprehensiveCompliance',
            'TestLendingLoss',
            'TestHoldingPeriodCalculations',
            'TestPartialSales',
            'TestWashSalePreBuyWindow',
            'TestRiskyOptionWarnings',
        ]
    },
    'test_data_processing.py': {
        'description': 'Data Ingestion and Processing Tests',
        'classes': [
            'TestCSVParsingAndIngestion',
            'TestSmartIngestor',
            'TestIngestorSmartProcessing',
            'TestLargeScaleDataIngestion',
            'TestUserErrors',
        ]
    },
    'test_integrations.py': {
        'description': 'External Integration Tests',
        'classes': [
            'TestStakeTaxCSVIntegration',
            'TestWalletFormatCompatibility',
            'TestPriceFetchingAndFallback',
            'TestPriceCacheAndFetcher',
            'TestAPIKeyHandling',
            'TestAPIErrorHandling',
            'TestAPIRateLimiting',
            'TestNetworkRetryLogic',
            'TestBlockchainIntegration',
            'TestTokenAddressCaching',
        ]
    },
    'test_defi_features.py': {
        'description': 'DeFi and Advanced Transaction Tests',
        'classes': [
            'TestDeFiInteractions',
            'TestComplexDeFiScenarios',
            'TestDepositWithdrawalScenarios',
            'TestReturnRefundTransactions',
            'TestDeFiLPConservativeMode',
        ]
    },
    'test_fees_and_precision.py': {
        'description': 'Fee Handling and Precision Tests',
        'classes': [
            'TestFeeHandling',
            'TestMultiCoinFeeHandling',
            'TestExtremePrecisionAndRounding',
        ]
    },
    'test_migration_and_multi_year.py': {
        'description': 'Migration and Multi-Year Processing Tests',
        'classes': [
            'TestMigration2025',
            'TestMultiYearTaxProcessing',
            'TestMultiYearMigrations',
            'TestMigrationInventoryLoading',
            'TestPriorYearDataLoading',
            'TestDestinationColumnMigration',
            'TestTimezoneHandling',
        ]
    },
    'test_reporting_and_export.py': {
        'description': 'Report Generation and Export Tests',
        'classes': [
            'TestReportVerification',
            'TestReportGenerationAndExport',
            'TestExportInternals',
            'TestExportFormatEdgeCases',
            'TestAuditorFBARAndReporting',
            'TestAuditWalletValidation',
            'TestFBARCompliance2025',
        ]
    },
    'test_reviewer_and_fixer.py': {
        'description': 'Tax Reviewer and Interactive Fixer Tests',
        'classes': [
            'TestTaxReviewerHeuristics',
            'TestTaxReviewerAdvanced',
            'TestInteractiveReviewFixer',
            'TestInteractiveFixerTransactions',
            'TestInteractiveReviewFixerComprehensive',
            'TestInteractiveFixerUIFlow',
            'TestInteractiveFixerImports',
        ]
    },
    'test_config_and_setup.py': {
        'description': 'Configuration and Setup Tests',
        'classes': [
            'TestConfigHandling',
            'TestConfigFileHandling',
            'TestSetupScript',
            'TestSetupConfigCompliance',
            'TestAutoRunner',
            'TestConfigMerging',
        ]
    },
    'test_system_stability.py': {
        'description': 'System Stability and Architecture Tests',
        'classes': [
            'TestArchitectureStability',
            'TestSystemInterruptions',
            'TestDatabaseIntegrity',
            'TestConcurrentExecutionSafety',
            'TestSafety',
        ]
    },
    'test_edge_cases.py': {
        'description': 'Edge Cases and Stress Tests',
        'classes': [
            'TestEdgeCasesExtremeValues',
            'TestEdgeCasesMalformedData',
            'TestUnlikelyButValidTransactions',
            'TestExtremeErrorScenariosGracefulDegradation',
            'TestLargePortfolios',
            'TestExtremeMarketConditions',
        ]
    },
    'test_chaos_and_monte_carlo.py': {
        'description': 'Chaos Testing and Monte Carlo Simulations',
        'classes': [
            'TestChaosEngine',
            'TestRandomScenarioMonteCarloSimulation',
            'TestComplexCombinationScenarios',
        ]
    },
    'test_wallet_compatibility.py': {
        'description': 'Wallet Format Compatibility Tests',
        'classes': [
            'TestWalletCompatibility',
        ]
    },
    'test_price_fetcher.py': {
        'description': 'Price Fetcher Integration Tests',
        'classes': [
            'TestPriceFetcherIntegration',
        ]
    },
}

# Extract test class definitions
class_ranges = {}
for i, line in enumerate(lines):
    if line.startswith('class Test'):
        class_name = line.split('(')[0].replace('class ', '').strip()
        class_ranges[class_name] = {'start': i}

# Find end lines
class_names = list(class_ranges.keys())
for i, class_name in enumerate(class_names):
    if i < len(class_names) - 1:
        class_ranges[class_name]['end'] = class_ranges[class_names[i + 1]]['start'] - 1
    else:
        # Find the last line before if __name__
        for j in range(len(lines) - 1, -1, -1):
            if lines[j].startswith("if __name__ == '__main__':"):
                class_ranges[class_name]['end'] = j - 2
                break

# Generate files
header = '''"""{}"""
from test_common import *

'''

for filename, group_info in test_groups.items():
    print(f"Creating {filename}...")
    file_content = header.format(group_info['description'])
    
    for class_name in group_info['classes']:
        if class_name in class_ranges:
            start = class_ranges[class_name]['start']
            end = class_ranges[class_name]['end']
            class_content = '\n'.join(lines[start:end+1])
            file_content += class_content + '\n\n\n'
    
    file_content += '''if __name__ == '__main__':
    unittest.main()
'''
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(file_content)
    print(f"  Added {len(group_info['classes'])} test classes")

print("\\nDone! Created all test files.")


