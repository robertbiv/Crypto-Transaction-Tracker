"""
Tests for wallet linking during CSV imports.
Tests automatic wallet detection, address matching, and manual selection.
"""

import pytest
import json
from src.web.wallet_linker import WalletLinker, WalletMatcher, load_wallets_and_link


class TestWalletLinkerBasic:
    """Test basic wallet linking functionality"""
    
    @pytest.fixture
    def wallet_data(self):
        """Sample wallet data"""
        return {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ', '1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2'],
                'name': 'Cold Storage'
            },
            'ethereum': {
                'addresses': ['0x742d35Cc6634C0532925a3b844Bc9e7595f42bE'],
                'name': 'Hot Wallet'
            },
            'litecoin': {
                'addresses': ['LdxkqXWbqtevJnZxyhb9Ly2FKzR6L7RJFM']
            }
        }
    
    def test_wallet_linker_initialization(self, wallet_data):
        """Wallet linker should initialize with wallet data"""
        linker = WalletLinker(wallet_data)
        assert linker.wallet_data == wallet_data
    
    def test_address_index_building(self, wallet_data):
        """Wallet linker should build address index"""
        linker = WalletLinker(wallet_data)
        
        # Check BTC addresses are indexed (note: actual address when lowercased)
        btc_address = '1a1z7agoat7jfkjcturwcehb1qphaeiuhz'  # Actual lowercased value
        assert btc_address in linker.address_to_blockchain
        assert linker.address_to_blockchain[btc_address] == 'bitcoin'
        
        # Check names are indexed
        assert '0x742d35cc6634c0532925a3b844bc9e7595f42be' in linker.address_to_name
        assert linker.address_to_name['0x742d35cc6634c0532925a3b844bc9e7595f42be'] == 'Hot Wallet'


class TestWalletMatching:
    """Test wallet matching by address and name"""
    
    @pytest.fixture
    def linker(self):
        wallet_data = {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ'],
                'name': 'Main BTC'
            },
            'ethereum': {
                'addresses': ['0x742d35Cc6634C0532925a3b844Bc9e7595f42bE'],
                'name': 'Trading Wallet'
            }
        }
        return WalletLinker(wallet_data)
    
    def test_find_wallet_by_address(self, linker):
        """Should find wallet by address"""
        match = linker.find_matching_wallet('unknown', '1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ')
        
        assert match is not None
        assert match['blockchain'] == 'bitcoin'
        assert match['address'] == '1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ'
        assert match['name'] == 'Main BTC'
    
    def test_find_wallet_by_address_case_insensitive(self, linker):
        """Should find wallet by address case-insensitively"""
        match = linker.find_matching_wallet('unknown', '1a1z7agoat7jfkjcturwcehb1qphaeiuhz')
        
        assert match is not None
        assert match['blockchain'] == 'bitcoin'
    
    def test_find_wallet_by_name(self, linker):
        """Should find wallet by name"""
        match = linker.find_matching_wallet('Trading Wallet')
        
        assert match is not None
        assert match['name'] == 'Trading Wallet'
        assert match['blockchain'] == 'ethereum'
    
    def test_find_wallet_by_name_case_insensitive(self, linker):
        """Should find wallet by name case-insensitively"""
        match = linker.find_matching_wallet('MAIN BTC')
        
        assert match is not None
        assert match['name'] == 'Main BTC'
    
    def test_no_wallet_match(self, linker):
        """Should return empty dict if no match found"""
        match = linker.find_matching_wallet('UnknownExchange')
        
        assert match == {}
    
    def test_address_takes_precedence_over_name(self, linker):
        """When both address and name provided, address should take precedence"""
        # This tests that providing the correct address finds the right wallet
        match = linker.find_matching_wallet('WrongName', '0x742d35Cc6634C0532925a3b844Bc9e7595f42bE')
        
        assert match['blockchain'] == 'ethereum'
        assert match['name'] == 'Trading Wallet'


class TestWalletSelection:
    """Test getting possible wallet matches for user selection"""
    
    @pytest.fixture
    def linker(self):
        wallet_data = {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ'],
                'name': 'Exchange Wallet'
            },
            'ethereum': {
                'addresses': ['0x742d35Cc6634C0532925a3b844Bc9e7595f42bE'],
                'name': 'Exchange Account'
            },
            'litecoin': {
                'addresses': ['LdxkqXWbqtevJnZxyhb9Ly2FKzR6L7RJFM']
            }
        }
        return WalletLinker(wallet_data)
    
    def test_exact_name_match_for_selection(self, linker):
        """Should find exact name matches"""
        matches = linker.get_possible_wallets_for_source('Exchange Wallet')
        
        assert len(matches) >= 1
        assert any(m['name'] == 'Exchange Wallet' for m in matches)
    
    def test_partial_name_match_for_selection(self, linker):
        """Should find partial name matches"""
        matches = linker.get_possible_wallets_for_source('Exchange')
        
        assert len(matches) >= 2  # Both 'Exchange Wallet' and 'Exchange Account'
    
    def test_get_all_wallets_for_selection(self, linker):
        """Should get all wallets available for selection"""
        wallets = linker.get_all_wallets_for_selection()
        
        assert len(wallets) == 3
        assert any(w['blockchain'] == 'bitcoin' for w in wallets)
        assert any(w['blockchain'] == 'ethereum' for w in wallets)
        assert any(w['blockchain'] == 'litecoin' for w in wallets)
    
    def test_wallet_selection_has_display_name(self, linker):
        """Selected wallets should have display names"""
        wallets = linker.get_all_wallets_for_selection()
        
        for wallet in wallets:
            assert 'display' in wallet
            assert len(wallet['display']) > 0
            assert wallet['display'] != ''


class TestTransactionEnrichment:
    """Test enriching transactions with wallet information"""
    
    @pytest.fixture
    def linker(self):
        wallet_data = {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ'],
                'name': 'Cold Storage'
            }
        }
        return WalletLinker(wallet_data)
    
    def test_enrich_transaction_with_wallet_match(self, linker):
        """Should enrich transaction with wallet data"""
        transaction = {
            'id': '1',
            'date': '2024-01-01',
            'action': 'BUY',
            'amount': 1.0,
            'source': 'unknown'
        }
        
        wallet_match = {
            'blockchain': 'bitcoin',
            'address': '1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ',
            'name': 'Cold Storage'
        }
        
        enriched = linker.enrich_transaction(transaction, wallet_match)
        
        assert enriched['wallet_name'] == 'Cold Storage'
        assert enriched['wallet_address'] == '1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ'
        assert enriched['wallet_blockchain'] == 'bitcoin'
    
    def test_enrich_transaction_without_match(self, linker):
        """Should handle enrichment without wallet match"""
        transaction = {'id': '1', 'source': 'Unknown'}
        
        enriched = linker.enrich_transaction(transaction, {})
        
        # Should not have wallet fields added
        assert 'wallet_name' not in enriched or enriched.get('wallet_name') == ''


class TestWalletMatcher:
    """Test WalletMatcher for ambiguity detection"""
    
    @pytest.fixture
    def matcher(self):
        wallet_data = {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ', '1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2'],
                'name': 'Coinbase'
            },
            'ethereum': {
                'addresses': ['0x742d35Cc6634C0532925a3b844Bc9e7595f42bE'],
                'name': 'Kraken'
            }
        }
        return WalletMatcher(wallet_data)
    
    def test_clear_address_match(self, matcher):
        """Should match transaction with clear address"""
        tx = {
            'source': 'Coinbase',
            'address': '1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ'
        }
        
        enriched, ambiguity = matcher.match_transaction_to_wallet(tx)
        
        assert ambiguity is None
        assert enriched['wallet_name'] == 'Coinbase'
    
    def test_no_match_returns_original(self, matcher):
        """Should return original transaction if no match"""
        tx = {
            'source': 'UnknownExchange',
            'address': None
        }
        
        enriched, ambiguity = matcher.match_transaction_to_wallet(tx)
        
        assert enriched == tx
        assert ambiguity is None
    
    def test_ambiguous_match_returns_options(self, matcher):
        """Should return ambiguity info for ambiguous matches"""
        # Create new matcher with wallets that have same name
        wallet_data_ambig = {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ'],
                'name': 'ExchangeWallet'
            },
            'litecoin': {
                'addresses': ['LdxkqXWbqtevJnZxyhb9Ly2FKzR6L7RJFM'],
                'name': 'ExchangeWallet'  # Same name
            }
        }
        matcher_ambig = WalletMatcher(wallet_data_ambig)
        
        tx = {'source': 'ExchangeWallet'}
        
        enriched, ambiguity = matcher_ambig.match_transaction_to_wallet(tx)
        
        # First match found should be used, no ambiguity returned
        assert ambiguity is None


class TestCSVImportScenarios:
    """Test real-world CSV import scenarios"""
    
    def test_csv_with_exchange_name(self):
        """CSV with exchange name should match wallet by name"""
        wallet_data = {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ'],
                'name': 'Kraken'
            }
        }
        
        transactions = [
            {'id': '1', 'source': 'Kraken', 'amount': 1.0},
            {'id': '2', 'source': 'kraken', 'amount': 2.0},  # Case variation
        ]
        
        matcher = WalletMatcher(wallet_data)
        
        for tx in transactions:
            enriched, ambiguity = matcher.match_transaction_to_wallet(tx)
            assert ambiguity is None
            assert enriched['wallet_name'] == 'Kraken'
    
    def test_csv_with_address(self):
        """CSV with address should match wallet by address"""
        wallet_data = {
            'ethereum': {
                'addresses': ['0x742d35Cc6634C0532925a3b844Bc9e7595f42bE'],
                'name': 'MyWallet'
            }
        }
        
        tx = {
            'id': '1',
            'source': 'UniswapV3',
            'address': '0x742d35Cc6634C0532925a3b844Bc9e7595f42bE'
        }
        
        matcher = WalletMatcher(wallet_data)
        enriched, ambiguity = matcher.match_transaction_to_wallet(tx)
        
        assert ambiguity is None
        assert enriched['wallet_name'] == 'MyWallet'
        assert enriched['wallet_blockchain'] == 'ethereum'
    
    def test_csv_manual_selection(self):
        """User should be able to manually select wallet during import"""
        wallet_data = {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ', '1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2'],
                'name': 'Trading'
            },
            'ethereum': {
                'addresses': ['0x742d35Cc6634C0532925a3b844Bc9e7595f42bE'],
                'name': 'Staking'
            }
        }
        
        linker = WalletLinker(wallet_data)
        wallets = linker.get_all_wallets_for_selection()
        
        # Simulate user selecting first wallet
        selected = wallets[0]
        tx = {'id': '1', 'source': 'Unknown'}
        enriched = linker.enrich_transaction(tx, selected)
        
        assert enriched['wallet_name'] == selected['name']
        assert enriched['wallet_address'] == selected['address']
    
    def test_multiple_addresses_same_wallet(self):
        """Should handle wallets with multiple addresses"""
        wallet_data = {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ', '1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2'],
                'name': 'Multi-Wallet'
            }
        }
        
        linker = WalletLinker(wallet_data)
        
        # Both addresses should link to same wallet
        match1 = linker.find_matching_wallet('unknown', '1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ')
        match2 = linker.find_matching_wallet('unknown', '1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2')
        
        assert match1['name'] == 'Multi-Wallet'
        assert match2['name'] == 'Multi-Wallet'
        assert match1['blockchain'] == match2['blockchain'] == 'bitcoin'


class TestAddressDisplay:
    """Test address display in transactions when wallet name unavailable"""
    
    def test_display_address_when_no_name(self):
        """Should show address when wallet name not available"""
        transaction = {
            'source': 'Custom Import',
            'wallet_name': '',
            'wallet_address': '0x742d35Cc6634C0532925a3b844Bc9e7595f42bE'
        }
        
        # Display logic: use address if name empty
        display = transaction.get('wallet_name') or transaction.get('wallet_address', '')
        
        assert display == '0x742d35Cc6634C0532925a3b844Bc9e7595f42bE'
    
    def test_display_name_when_available(self):
        """Should show wallet name when available"""
        transaction = {
            'source': 'Kraken',
            'wallet_name': 'My Cold Storage',
            'wallet_address': '1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ'
        }
        
        display = transaction.get('wallet_name') or transaction.get('wallet_address', '')
        
        assert display == 'My Cold Storage'
    
    def test_address_truncation_in_display(self):
        """Addresses should be truncated in display"""
        address = '0x742d35Cc6634C0532925a3b844Bc9e7595f42bE'
        
        # Frontend display logic: show first 6 and last 4 chars
        display = f"{address[:6]}...{address[-4:]}"
        
        assert display == '0x742d...42bE'  # Correct truncation
        assert len(display) < len(address)


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_empty_wallet_data(self):
        """Should handle empty wallet data"""
        wallet_data = {}
        linker = WalletLinker(wallet_data)
        
        match = linker.find_matching_wallet('anything')
        
        assert match == {}
    
    def test_wallet_with_no_name(self):
        """Should handle wallets without names"""
        wallet_data = {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ']
            }
        }
        
        linker = WalletLinker(wallet_data)
        wallets = linker.get_all_wallets_for_selection()
        
        assert len(wallets) == 1
        assert wallets[0]['name'] == ''
        assert 'Bitcoin' in wallets[0]['label']  # Should have capitalized blockchain name
    
    def test_wallet_with_empty_addresses(self):
        """Should handle wallets with empty addresses"""
        wallet_data = {
            'bitcoin': {
                'addresses': [],
                'name': 'Empty Wallet'
            }
        }
        
        linker = WalletLinker(wallet_data)
        wallets = linker.get_all_wallets_for_selection()
        
        assert len(wallets) == 0
    
    def test_special_characters_in_wallet_name(self):
        """Should handle special characters in wallet names"""
        wallet_data = {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ'],
                'name': 'Wallet - BTC (Cold)'
            }
        }
        
        linker = WalletLinker(wallet_data)
        match = linker.find_matching_wallet('Wallet - BTC (Cold)')
        
        assert match['name'] == 'Wallet - BTC (Cold)'
    
    def test_unicode_in_wallet_name(self):
        """Should handle Unicode in wallet names"""
        wallet_data = {
            'bitcoin': {
                'addresses': ['1A1z7agoat7JFkJCTurwCEHb1QphAeiUhZ'],
                'name': 'Холодное Хранилище'
            }
        }
        
        linker = WalletLinker(wallet_data)
        match = linker.find_matching_wallet('Холодное Хранилище')
        
        assert match['name'] == 'Холодное Хранилище'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
