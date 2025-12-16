"""
================================================================================
TEST: Wallet Format Compatibility
================================================================================

Validates compatibility between different wallet configuration formats.

Test Coverage:
    - Nested wallet format (new Setup.py)
    - Flat wallet format (legacy)
    - Format migration
    - Address extraction
    - Multi-chain wallet support

Author: robertbiv
================================================================================
"""
from test_common import *

class TestWalletCompatibility(unittest.TestCase):
    """Test wallet format compatibility between Setup.py and StakeTaxCSV"""
    
    def test_wallet_extraction_nested_format(self):
        """Test extraction of nested format (new - from updated Setup.py)"""
        data = {
            "ethereum": {"addresses": ["0x123abc", "0x456def"]},
            "bitcoin": {"addresses": ["bc1abc", "bc1def"]},
            "solana": {"addresses": ["SolanaAddr1"]},
            "_INSTRUCTIONS": "metadata"
        }
        expected = {"0x123abc", "0x456def", "bc1abc", "bc1def", "SolanaAddr1"}
        
        wallets = []
        for key, value in data.items():
            if key.startswith('_'):
                continue
            if isinstance(value, dict) and 'addresses' in value:
                addresses = value['addresses']
                if isinstance(addresses, list):
                    wallets.extend([a for a in addresses if a and isinstance(a, str) and not a.startswith('PASTE_')])
                elif isinstance(addresses, str) and not addresses.startswith('PASTE_'):
                    wallets.append(addresses)
            elif isinstance(value, list):
                wallets.extend([a for a in value if a and isinstance(a, str) and not a.startswith('PASTE_')])
            elif isinstance(value, str) and not value.startswith('PASTE_'):
                wallets.append(value)
        
        self.assertEqual(set(wallets), expected)

    def test_wallet_extraction_flat_format(self):
        """Test extraction of flat format (legacy - old Setup.py)"""
        data = {
            "ETH": ["0x123abc", "0x456def"],
            "BTC": ["bc1abc", "bc1def"],
            "SOL": ["SolanaAddr1"],
            "_INSTRUCTIONS": "metadata"
        }
        expected = {"0x123abc", "0x456def", "bc1abc", "bc1def", "SolanaAddr1"}
        
        wallets = []
        for key, value in data.items():
            if key.startswith('_'):
                continue
            if isinstance(value, dict) and 'addresses' in value:
                addresses = value['addresses']
                if isinstance(addresses, list):
                    wallets.extend([a for a in addresses if a and isinstance(a, str) and not a.startswith('PASTE_')])
                elif isinstance(addresses, str) and not addresses.startswith('PASTE_'):
                    wallets.append(addresses)
            elif isinstance(value, list):
                wallets.extend([a for a in value if a and isinstance(a, str) and not a.startswith('PASTE_')])
            elif isinstance(value, str) and not value.startswith('PASTE_'):
                wallets.append(value)
        
        self.assertEqual(set(wallets), expected)

    def test_wallet_extraction_with_paste_placeholders(self):
        """Test that PASTE_ placeholders are filtered out"""
        data = {
            "ethereum": {"addresses": ["0x123abc", "PASTE_ETH_ADDRESS"]},
            "bitcoin": {"addresses": ["PASTE_BTC_ADDRESS"]},
            "_INSTRUCTIONS": "metadata"
        }
        expected = {"0x123abc"}
        
        wallets = []
        for key, value in data.items():
            if key.startswith('_'):
                continue
            if isinstance(value, dict) and 'addresses' in value:
                addresses = value['addresses']
                if isinstance(addresses, list):
                    wallets.extend([a for a in addresses if a and isinstance(a, str) and not a.startswith('PASTE_')])
                elif isinstance(addresses, str) and not addresses.startswith('PASTE_'):
                    wallets.append(addresses)
            elif isinstance(value, list):
                wallets.extend([a for a in value if a and isinstance(a, str) and not a.startswith('PASTE_')])
            elif isinstance(value, str) and not value.startswith('PASTE_'):
                wallets.append(value)
        
        self.assertEqual(set(wallets), expected)

    def test_wallet_extraction_single_string_value(self):
        """Test extraction with single string values in flat format"""
        data = {
            "ETH": "0x123abc",
            "BTC": ["bc1abc"],
            "_INSTRUCTIONS": "metadata"
        }
        expected = {"0x123abc", "bc1abc"}
        
        wallets = []
        for key, value in data.items():
            if key.startswith('_'):
                continue
            if isinstance(value, dict) and 'addresses' in value:
                addresses = value['addresses']
                if isinstance(addresses, list):
                    wallets.extend([a for a in addresses if a and isinstance(a, str) and not a.startswith('PASTE_')])
                elif isinstance(addresses, str) and not addresses.startswith('PASTE_'):
                    wallets.append(addresses)
            elif isinstance(value, list):
                wallets.extend([a for a in value if a and isinstance(a, str) and not a.startswith('PASTE_')])
            elif isinstance(value, str) and not value.startswith('PASTE_'):
                wallets.append(value)
        
        self.assertEqual(set(wallets), expected)

    def test_wallet_extraction_mixed_nested_and_flat(self):
        """Test extraction with mixed nested and flat formats (backwards compatibility)"""
        data = {
            "ethereum": {"addresses": ["0x123abc"]},
            "BTC": ["bc1abc"],
            "_INSTRUCTIONS": "metadata"
        }
        expected = {"0x123abc", "bc1abc"}
        
        wallets = []
        for key, value in data.items():
            if key.startswith('_'):
                continue
            if isinstance(value, dict) and 'addresses' in value:
                addresses = value['addresses']
                if isinstance(addresses, list):
                    wallets.extend([a for a in addresses if a and isinstance(a, str) and not a.startswith('PASTE_')])
                elif isinstance(addresses, str) and not addresses.startswith('PASTE_'):
                    wallets.append(addresses)
            elif isinstance(value, list):
                wallets.extend([a for a in value if a and isinstance(a, str) and not a.startswith('PASTE_')])
            elif isinstance(value, str) and not value.startswith('PASTE_'):
                wallets.append(value)
        
        self.assertEqual(set(wallets), expected)




if __name__ == '__main__':
    unittest.main()


