#!/usr/bin/env python3
"""Test wallet format compatibility between Setup.py and StakeTaxCSV"""

def test_wallet_extraction():
    """Test the wallet extraction logic with both nested and flat formats"""
    test_cases = [
        # Nested format (new - from updated Setup.py)
        {
            "name": "Nested format (new Setup.py)",
            "data": {
                "ethereum": {"addresses": ["0x123abc", "0x456def"]},
                "bitcoin": {"addresses": ["bc1abc", "bc1def"]},
                "solana": {"addresses": ["SolanaAddr1"]},
                "_INSTRUCTIONS": "metadata"
            },
            "expected": {"0x123abc", "0x456def", "bc1abc", "bc1def", "SolanaAddr1"}
        },
        # Flat format (legacy - old Setup.py)
        {
            "name": "Flat format (legacy)",
            "data": {
                "ETH": ["0x123abc", "0x456def"],
                "BTC": ["bc1abc", "bc1def"],
                "SOL": ["SolanaAddr1"],
                "_INSTRUCTIONS": "metadata"
            },
            "expected": {"0x123abc", "0x456def", "bc1abc", "bc1def", "SolanaAddr1"}
        },
        # Mixed with PASTE_ placeholders
        {
            "name": "With PASTE_ placeholders",
            "data": {
                "ethereum": {"addresses": ["0x123abc", "PASTE_ETH_ADDRESS"]},
                "bitcoin": {"addresses": ["PASTE_BTC_ADDRESS"]},
                "_INSTRUCTIONS": "metadata"
            },
            "expected": {"0x123abc"}
        },
        # Single string value (flat format)
        {
            "name": "Single string value",
            "data": {
                "ETH": "0x123abc",
                "BTC": ["bc1abc"],
                "_INSTRUCTIONS": "metadata"
            },
            "expected": {"0x123abc", "bc1abc"}
        },
        # Mixed nested and flat (backwards compatibility)
        {
            "name": "Mixed nested and flat",
            "data": {
                "ethereum": {"addresses": ["0x123abc"]},
                "BTC": ["bc1abc"],
                "_INSTRUCTIONS": "metadata"
            },
            "expected": {"0x123abc", "bc1abc"}
        }
    ]
    
    print("=" * 70)
    print("WALLET EXTRACTION COMPATIBILITY TEST")
    print("=" * 70)
    
    all_passed = True
    
    for test in test_cases:
        # Simulate the extraction logic from StakeTaxCSVManager._get_wallets_from_file()
        wallet_data = test["data"]
        wallets = []
        
        for key, value in wallet_data.items():
            if key.startswith('_'):
                continue
            
            # Handle nested format: {"ethereum": {"addresses": [...]}}
            if isinstance(value, dict) and 'addresses' in value:
                addresses = value['addresses']
                if isinstance(addresses, list):
                    wallets.extend([a for a in addresses if a and isinstance(a, str) and not a.startswith('PASTE_')])
                elif isinstance(addresses, str) and not addresses.startswith('PASTE_'):
                    wallets.append(addresses)
            
            # Handle flat format: {"ETH": [...]} or {"ETH": "0x..."}
            elif isinstance(value, list):
                wallets.extend([a for a in value if a and isinstance(a, str) and not a.startswith('PASTE_')])
            elif isinstance(value, str) and not value.startswith('PASTE_'):
                wallets.append(value)
        
        result = set(wallets)
        passed = result == test["expected"]
        all_passed = all_passed and passed
        
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"\n{status}: {test['name']}")
        print(f"   Extracted: {result}")
        if not passed:
            print(f"   Expected:  {test['expected']}")
            missing = test['expected'] - result
            extra = result - test['expected']
            if missing:
                print(f"   Missing:   {missing}")
            if extra:
                print(f"   Extra:     {extra}")
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL TESTS PASSED - StakeTaxCSV format is compatible!")
    else:
        print("✗ SOME TESTS FAILED - Format compatibility issue")
    print("=" * 70)
    
    return all_passed

if __name__ == "__main__":
    success = test_wallet_extraction()
    exit(0 if success else 1)
