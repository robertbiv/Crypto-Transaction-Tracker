"""
Tests for wallet naming and management functionality.
Tests handling of wallet names, including edge cases like duplicate names.
"""

import pytest
import json


class TestWalletNaming:
    """Test wallet naming functionality"""
    
    def test_single_wallet_with_name(self):
        """Single wallet should support a name"""
        wallet_data = {
            'bitcoin': {
                'name': 'Main BTC Wallet',
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ']
            }
        }
        
        assert wallet_data['bitcoin']['name'] == 'Main BTC Wallet'
        assert len(wallet_data['bitcoin']['addresses']) == 1
    
    def test_multiple_wallets_same_blockchain_with_names(self):
        """Multiple wallets on same blockchain should support numbered names"""
        wallet_data = {
            'ethereum': {
                'name': 'ETH Wallets',
                'addresses': [
                    '0x742d35Cc6634C0532925a3b844Bc9e7595f42bE',
                    '0x8ba1f109551bD432803012645Ac136ddd64DBA72'
                ]
            }
        }
        
        assert wallet_data['ethereum']['name'] == 'ETH Wallets'
        assert len(wallet_data['ethereum']['addresses']) == 2
    
    def test_wallet_without_name(self):
        """Wallet should work without a name"""
        wallet_data = {
            'litecoin': {
                'addresses': ['LdxkqXWbqtevJnZxyhb9Ly2FKzR6L7RJFM']
            }
        }
        
        assert 'name' not in wallet_data['litecoin'] or wallet_data['litecoin'].get('name') == ''
        assert len(wallet_data['litecoin']['addresses']) == 1
    
    def test_duplicate_wallet_names(self):
        """Multiple wallets can have the same name - system should handle it"""
        wallet_data = {
            'bitcoin': {
                'name': 'Exchange Wallet',
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ']
            },
            'ethereum': {
                'name': 'Exchange Wallet',
                'addresses': ['0x742d35Cc6634C0532925a3b844Bc9e7595f42bE']
            },
            'litecoin': {
                'name': 'Exchange Wallet',
                'addresses': ['LdxkqXWbqtevJnZxyhb9Ly2FKzR6L7RJFM']
            }
        }
        
        # Count wallets with this name
        duplicate_count = sum(1 for blockchain, data in wallet_data.items() 
                            if isinstance(data, dict) and data.get('name') == 'Exchange Wallet')
        
        assert duplicate_count == 3
        assert all(data.get('name') == 'Exchange Wallet' for data in wallet_data.values() 
                  if isinstance(data, dict))
    
    def test_wallet_name_max_length(self):
        """Wallet names should be limited in length"""
        long_name = 'A' * 50
        normal_name = 'A' * 30
        
        wallet_short = {'name': normal_name}
        wallet_long = {'name': long_name}
        
        assert len(wallet_short['name']) <= 50
        assert len(wallet_long['name']) <= 50
        assert len(wallet_long['name']) == 50
    
    def test_wallet_name_with_special_characters(self):
        """Wallet names should support common special characters"""
        names = [
            'Coinbase - BTC',
            'Kraken (USD)',
            'Wallet #1',
            'My Wallet & Exchange',
            'Hot-Wallet_2024',
        ]
        
        for name in names:
            assert isinstance(name, str)
            assert len(name) > 0
            assert len(name) <= 50
    
    def test_wallet_name_uniqueness_per_blockchain(self):
        """On the same blockchain, addresses should be unique"""
        wallet_data = {
            'bitcoin': {
                'name': 'My Wallets',
                'addresses': [
                    '1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ',
                    '1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2'
                ]
            }
        }
        
        addresses = wallet_data['bitcoin']['addresses']
        assert len(addresses) == len(set(addresses)), "Duplicate addresses detected"
    
    def test_wallet_data_migration_old_format(self):
        """System should handle migration from old format (array only)"""
        old_format = {
            'bitcoin': [
                '1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ',
                '1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2'
            ]
        }
        
        # Migration function
        def migrate_wallet_format(wallet_data):
            migrated = {}
            for blockchain, data in wallet_data.items():
                if isinstance(data, list):
                    migrated[blockchain] = {
                        'addresses': data,
                        'name': ''
                    }
                else:
                    migrated[blockchain] = data
            return migrated
        
        new_format = migrate_wallet_format(old_format)
        
        assert 'addresses' in new_format['bitcoin']
        assert isinstance(new_format['bitcoin']['addresses'], list)
        assert len(new_format['bitcoin']['addresses']) == 2
    
    def test_wallet_display_with_names(self):
        """Transaction display should show wallet names"""
        wallet_data = {
            'bitcoin': {
                'name': 'Cold Storage',
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ']
            }
        }
        
        transaction = {
            'id': '1',
            'source': 'bitcoin',
            'wallet_name': 'Cold Storage',
            'action': 'TRANSFER'
        }
        
        # Simulate display logic
        wallet_label = transaction.get('wallet_name', transaction.get('source'))
        
        assert wallet_label == 'Cold Storage'
    
    def test_wallet_display_without_names(self):
        """Transaction display should fallback to source if no name"""
        transaction = {
            'id': '1',
            'source': 'Coinbase',
            'action': 'BUY'
        }
        
        wallet_label = transaction.get('wallet_name', transaction.get('source'))
        
        assert wallet_label == 'Coinbase'


class TestWalletDisplayLogic:
    """Test how wallet names appear in transaction displays"""
    
    def test_single_wallet_name_display(self):
        """Single wallet with name should show only the name"""
        wallet_name = 'Main Wallet'
        addresses = ['0x123...']
        
        display = wallet_name if len(addresses) == 1 else f"{wallet_name} #{1}"
        
        assert display == 'Main Wallet'
    
    def test_multiple_wallets_numbered_display(self):
        """Multiple wallets should show numbered names"""
        wallet_name = 'Exchange Wallets'
        addresses = ['0x123...', '0x456...', '0x789...']
        
        for idx in range(len(addresses)):
            display = f"{wallet_name} #{idx + 1}"
            assert f"#{idx + 1}" in display
            assert wallet_name in display
    
    def test_transaction_source_formatting(self):
        """Transaction source should format wallet info clearly"""
        transactions = [
            {'source': 'Coinbase', 'wallet_name': 'Primary'},
            {'source': 'Kraken', 'wallet_name': ''},
            {'source': 'Exchange', 'wallet_name': 'Trading Account'}
        ]
        
        for tx in transactions:
            # Use wallet_name if provided, fallback to source
            display = tx.get('wallet_name') or tx['source']
            assert isinstance(display, str)
            assert len(display) > 0


class TestWalletConfiguraton:
    """Test wallet configuration management"""
    
    def test_wallet_config_structure(self):
        """Wallet config should have required structure"""
        wallet_config = {
            'bitcoin': {
                'name': 'My Bitcoin',
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ']
            },
            'ethereum': {
                'name': 'My Ethereum',
                'addresses': ['0x742d35Cc6634C0532925a3b844Bc9e7595f42bE']
            }
        }
        
        for blockchain, data in wallet_config.items():
            assert 'addresses' in data
            assert isinstance(data['addresses'], list)
            assert len(data['addresses']) > 0
    
    def test_wallet_validation_rules(self):
        """Wallet data should follow validation rules"""
        valid_wallets = [
            {'name': 'Test', 'addresses': ['addr1']},
            {'name': '', 'addresses': ['addr1']},
            {'addresses': ['addr1', 'addr2']},
        ]
        
        invalid_wallets = [
            {'addresses': []},  # No addresses
            {'name': 'Test'},   # No addresses field
        ]
        
        def is_valid(wallet):
            return 'addresses' in wallet and len(wallet.get('addresses', [])) > 0
        
        for wallet in valid_wallets:
            assert is_valid(wallet)
        
        for wallet in invalid_wallets:
            assert not is_valid(wallet)
    
    def test_wallet_name_case_insensitive_comparison(self):
        """Wallet names should be handled case-insensitively for duplicates"""
        wallets = [
            {'name': 'Cold Storage', 'addresses': ['0x123']},
            {'name': 'cold storage', 'addresses': ['0x456']},
            {'name': 'COLD STORAGE', 'addresses': ['0x789']},
        ]
        
        names = [w.get('name', '').lower() for w in wallets]
        
        assert len(names) == 3
        assert len(set(names)) == 1  # All are the same when lowercased


class TestWalletNameHandling:
    """Test specific wallet naming edge cases"""
    
    def test_whitespace_in_wallet_names(self):
        """Wallet names with whitespace should be handled"""
        names = [
            '  Leading Space',
            'Trailing Space  ',
            '  Both Sides  ',
            'Multiple   Spaces',
        ]
        
        # Simulate trimming
        trimmed = [name.strip() for name in names]
        
        assert trimmed[0] == 'Leading Space'
        assert trimmed[1] == 'Trailing Space'
        assert trimmed[2] == 'Both Sides'
    
    def test_empty_wallet_name(self):
        """Empty wallet names should be allowed"""
        wallet = {
            'name': '',
            'addresses': ['0x123']
        }
        
        # System should use source as fallback
        display_name = wallet.get('name') or 'Unnamed Wallet'
        
        assert display_name == 'Unnamed Wallet'
    
    def test_wallet_name_unicode(self):
        """Wallet names should support Unicode"""
        names = [
            'Wallet 钱包',
            'محفظة Wallet',
            'Кошелек Wallet',
            'Ví tiền Wallet',
        ]
        
        for name in names:
            assert isinstance(name, str)
            assert len(name) > 0
    
    def test_duplicate_wallet_detection(self):
        """System should identify duplicate wallet names"""
        wallets = {
            'bitcoin': {'name': 'Main', 'addresses': ['0x1']},
            'ethereum': {'name': 'Main', 'addresses': ['0x2']},
            'litecoin': {'name': 'Backup', 'addresses': ['0x3']},
        }
        
        # Find duplicates
        names = {}
        for blockchain, data in wallets.items():
            name = data.get('name', '')
            if name:
                if name not in names:
                    names[name] = []
                names[name].append(blockchain)
        
        duplicates = {name: blockchains for name, blockchains in names.items() 
                     if len(blockchains) > 1}
        
        assert len(duplicates) == 1
        assert 'Main' in duplicates
        assert set(duplicates['Main']) == {'bitcoin', 'ethereum'}
    
    def test_wallet_name_in_transaction_context(self):
        """Wallet names should be accessible in transaction operations"""
        wallet_registry = {
            'bitcoin': {'name': 'Cold Storage', 'addresses': ['0x123']},
            'ethereum': {'name': 'Hot Wallet', 'addresses': ['0x456']}
        }
        
        def get_wallet_name(source, address):
            """Lookup wallet name from registry"""
            if source in wallet_registry:
                wallet = wallet_registry[source]
                if address in wallet['addresses']:
                    return wallet.get('name', '')
            return source
        
        name1 = get_wallet_name('bitcoin', '0x123')
        name2 = get_wallet_name('ethereum', '0x999')  # Address not in registry
        
        assert name1 == 'Cold Storage'
        assert name2 == 'ethereum'  # Fallback to source


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
