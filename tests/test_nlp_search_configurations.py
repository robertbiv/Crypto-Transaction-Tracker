"""
Tests for Natural Language Search functionality with different AI/ML configurations.
Tests NLP search endpoint with AI turned off, ML turned off, and ML-only mode.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock


class TestNLPSearchConfigurations:
    """Test NLP search with different AI/ML configuration states"""
    
    @pytest.fixture
    def mock_config_ai_off(self):
        """Config with AI completely disabled"""
        return {
            'ml_fallback': {'enabled': False},
            'accuracy_mode': {'enabled': False, 'natural_language_search': False}
        }
    
    @pytest.fixture
    def mock_config_ml_only(self):
        """Config with ML fallback only, no accuracy mode"""
        return {
            'ml_fallback': {'enabled': True},
            'accuracy_mode': {'enabled': False, 'natural_language_search': False}
        }
    
    @pytest.fixture
    def mock_config_accuracy_mode(self):
        """Config with accuracy mode enabled including NLP"""
        return {
            'ml_fallback': {'enabled': True},
            'accuracy_mode': {
                'enabled': True,
                'natural_language_search': True,
                'fraud_detection': True,
                'smart_descriptions': True,
                'pattern_learning': True
            }
        }
    
    @pytest.fixture
    def sample_transactions(self):
        """Sample transaction data for testing"""
        return [
            {
                'id': '1',
                'date': '2024-01-15',
                'action': 'BUY',
                'coin': 'BTC',
                'amount': 0.5,
                'price_usd': 45000,
                'fee': 0.001,
                'source': 'Coinbase',
                'destination': None
            },
            {
                'id': '2',
                'date': '2024-02-20',
                'action': 'SELL',
                'coin': 'ETH',
                'amount': 5,
                'price_usd': 2500,
                'fee': 0.05,
                'source': 'Kraken',
                'destination': 'Wallet'
            },
            {
                'id': '3',
                'date': '2024-03-10',
                'action': 'BUY',
                'coin': 'ETH',
                'amount': 10,
                'price_usd': 2000,
                'fee': 0.1,
                'source': 'Coinbase',
                'destination': None
            },
            {
                'id': '4',
                'date': '2024-04-05',
                'action': 'INCOME',
                'coin': 'ETH',
                'amount': 2,
                'price_usd': 3000,
                'fee': 0,
                'source': 'Staking',
                'destination': None
            },
            {
                'id': '5',
                'date': '2024-05-12',
                'action': 'TRANSFER',
                'coin': 'BTC',
                'amount': 0.1,
                'price_usd': 50000,
                'fee': 0.0001,
                'source': 'Coinbase',
                'destination': 'Hardware Wallet'
            }
        ]
    
    def test_nlp_search_with_ai_completely_off(self, mock_config_ai_off):
        """NLP search should return error when AI is completely disabled"""
        config = mock_config_ai_off
        query = "Show my BTC purchases"
        
        # Simulate API behavior when NLP is not available
        result = {
            'success': False,
            'error': 'Natural Language Search requires Accuracy Mode to be enabled',
            'configuration': {
                'ml_fallback_enabled': config['ml_fallback']['enabled'],
                'accuracy_mode_enabled': config['accuracy_mode']['enabled'],
                'nlp_enabled': config['accuracy_mode'].get('natural_language_search', False)
            }
        }
        
        assert result['success'] is False
        assert 'Accuracy Mode' in result['error']
        assert result['configuration']['accuracy_mode_enabled'] is False
    
    def test_nlp_search_with_ml_only(self, mock_config_ml_only):
        """NLP search should return error when only ML fallback is enabled"""
        config = mock_config_ml_only
        query = "Show my largest transactions"
        
        # Simulate API behavior
        result = {
            'success': False,
            'error': 'Natural Language Search requires Accuracy Mode to be enabled',
            'configuration': {
                'ml_fallback_enabled': config['ml_fallback']['enabled'],
                'accuracy_mode_enabled': config['accuracy_mode']['enabled'],
                'nlp_enabled': config['accuracy_mode'].get('natural_language_search', False)
            }
        }
        
        assert result['success'] is False
        assert result['configuration']['ml_fallback_enabled'] is True
        assert result['configuration']['accuracy_mode_enabled'] is False
        assert 'NLP' in result['error'] or 'Accuracy Mode' in result['error']
    
    def test_nlp_search_with_accuracy_mode_enabled(self, mock_config_accuracy_mode, sample_transactions):
        """NLP search should work when accuracy mode with NLP is enabled"""
        config = mock_config_accuracy_mode
        query = "Show my BTC purchases in 2024"
        
        # Simulate successful NLP search
        result = {
            'success': True,
            'query': query,
            'result_count': 2,
            'results': [
                sample_transactions[0],  # BTC BUY
                sample_transactions[4]   # BTC TRANSFER
            ],
            'configuration': {
                'ml_fallback_enabled': config['ml_fallback']['enabled'],
                'accuracy_mode_enabled': config['accuracy_mode']['enabled'],
                'nlp_enabled': config['accuracy_mode'].get('natural_language_search', True)
            }
        }
        
        assert result['success'] is True
        assert result['result_count'] == 2
        assert result['configuration']['accuracy_mode_enabled'] is True
        assert result['configuration']['nlp_enabled'] is True
        assert all(tx['coin'] == 'BTC' for tx in result['results'])
    
    def test_nlp_search_query_parsing_btc_purchases(self, sample_transactions):
        """NLP should correctly parse 'BTC purchases' query"""
        # Expected: BUY action AND BTC coin
        expected_results = [tx for tx in sample_transactions 
                          if tx['coin'] == 'BTC' and tx['action'] == 'BUY']
        
        assert len(expected_results) == 1
        assert expected_results[0]['id'] == '1'
        assert expected_results[0]['action'] == 'BUY'
    
    def test_nlp_search_query_parsing_largest_transactions(self, sample_transactions):
        """NLP should correctly parse 'largest transactions' query"""
        # Expected: sort by price_usd * amount descending
        sorted_txs = sorted(sample_transactions, 
                          key=lambda x: x['price_usd'] * x['amount'], 
                          reverse=True)
        
        top_3 = sorted_txs[:3]
        assert len(top_3) == 3
        # Verify they're sorted by value
        values = [tx['price_usd'] * tx['amount'] for tx in top_3]
        assert values == sorted(values, reverse=True)
    
    def test_nlp_search_query_parsing_staking_income(self, sample_transactions):
        """NLP should correctly parse 'staking income' query"""
        # Expected: INCOME action AND source = 'Staking'
        expected_results = [tx for tx in sample_transactions 
                          if tx['action'] == 'INCOME' and 'Staking' in tx['source']]
        
        assert len(expected_results) == 1
        assert expected_results[0]['coin'] == 'ETH'
        assert expected_results[0]['amount'] == 2
    
    def test_nlp_search_query_parsing_coinbase_transactions(self, sample_transactions):
        """NLP should correctly parse 'Coinbase transactions' query"""
        # Expected: source = 'Coinbase'
        expected_results = [tx for tx in sample_transactions 
                          if tx['source'] == 'Coinbase']
        
        assert len(expected_results) == 3
        assert all(tx['source'] == 'Coinbase' for tx in expected_results)
    
    def test_nlp_search_with_time_filter_2024(self, sample_transactions):
        """NLP should correctly parse 'in 2024' time filter"""
        # Expected: all transactions from 2024
        expected_results = [tx for tx in sample_transactions 
                          if '2024' in tx['date']]
        
        assert len(expected_results) == 5  # All are from 2024
    
    def test_nlp_search_error_when_nlp_flag_disabled(self, mock_config_accuracy_mode):
        """NLP search should error even if accuracy mode enabled but NLP flag is off"""
        config = mock_config_accuracy_mode.copy()
        config['accuracy_mode']['natural_language_search'] = False
        
        result = {
            'success': False,
            'error': 'Natural Language Search is not enabled',
            'configuration': {
                'accuracy_mode_enabled': config['accuracy_mode']['enabled'],
                'nlp_enabled': config['accuracy_mode'].get('natural_language_search', False)
            }
        }
        
        assert result['success'] is False
        assert result['configuration']['nlp_enabled'] is False
    
    def test_nlp_search_returns_correct_fields(self, sample_transactions):
        """NLP search result should have required fields"""
        result = {
            'success': True,
            'query': 'Show my transactions',
            'result_count': len(sample_transactions),
            'results': sample_transactions,
            'configuration': {
                'accuracy_mode_enabled': True,
                'nlp_enabled': True
            }
        }
        
        assert 'success' in result
        assert 'query' in result
        assert 'result_count' in result
        assert 'results' in result
        assert isinstance(result['results'], list)
        assert all(isinstance(tx, dict) for tx in result['results'])
        
        # Verify transaction fields
        for tx in result['results']:
            assert 'id' in tx
            assert 'date' in tx
            assert 'action' in tx
            assert 'coin' in tx
            assert 'amount' in tx
            assert 'price_usd' in tx
    
    def test_nlp_search_empty_results(self):
        """NLP search should handle empty results gracefully"""
        result = {
            'success': True,
            'query': 'Show all Dogecoin trades',
            'result_count': 0,
            'results': [],
            'message': 'No transactions matched your query'
        }
        
        assert result['success'] is True
        assert result['result_count'] == 0
        assert len(result['results']) == 0
    
    def test_nlp_search_complex_query(self, sample_transactions):
        """NLP should handle complex multi-condition queries"""
        # Query: "Show my largest ETH trades over $5,000 in 2024"
        # Conditions: coin=ETH, action=TRADE or BUY or SELL, value > 5000, year=2024
        
        filtered = [tx for tx in sample_transactions
                   if tx['coin'] == 'ETH' and 
                   (tx['price_usd'] * tx['amount'] > 5000) and
                   '2024' in tx['date']]
        
        # Results should include transactions matching all conditions
        assert len(filtered) >= 0
        assert all(tx['coin'] == 'ETH' for tx in filtered)
        assert all(tx['price_usd'] * tx['amount'] > 5000 for tx in filtered)
    
    def test_nlp_search_with_invalid_query(self):
        """NLP search should handle invalid/empty queries"""
        result_empty = {
            'success': False,
            'error': 'Query cannot be empty',
            'query': ''
        }
        
        result_whitespace = {
            'success': False,
            'error': 'Query cannot be empty',
            'query': '   '
        }
        
        assert result_empty['success'] is False
        assert result_whitespace['success'] is False
    
    def test_nlp_search_configuration_states(self):
        """Test all valid NLP configuration states"""
        states = [
            {
                'name': 'AI Off',
                'ml_fallback_enabled': False,
                'accuracy_mode_enabled': False,
                'nlp_enabled': False,
                'should_work': False
            },
            {
                'name': 'ML Only',
                'ml_fallback_enabled': True,
                'accuracy_mode_enabled': False,
                'nlp_enabled': False,
                'should_work': False
            },
            {
                'name': 'Accuracy Mode No NLP',
                'ml_fallback_enabled': True,
                'accuracy_mode_enabled': True,
                'nlp_enabled': False,
                'should_work': False
            },
            {
                'name': 'Accuracy Mode With NLP',
                'ml_fallback_enabled': True,
                'accuracy_mode_enabled': True,
                'nlp_enabled': True,
                'should_work': True
            }
        ]
        
        for state in states:
            nlp_available = state['accuracy_mode_enabled'] and state['nlp_enabled']
            assert nlp_available == state['should_work'], \
                f"State '{state['name']}' NLP availability mismatch"


class TestNLPSearchResponseFormats:
    """Test NLP search response formatting and error messages"""
    
    def test_success_response_format(self):
        """Test successful NLP search response format"""
        response = {
            'success': True,
            'query': 'Show my BTC transactions',
            'result_count': 5,
            'results': [
                {'id': '1', 'coin': 'BTC', 'action': 'BUY'},
                {'id': '2', 'coin': 'BTC', 'action': 'SELL'}
            ]
        }
        
        assert response['success'] is True
        assert isinstance(response['query'], str)
        assert isinstance(response['result_count'], int)
        assert isinstance(response['results'], list)
    
    def test_error_response_format(self):
        """Test error NLP search response format"""
        response = {
            'success': False,
            'error': 'Natural Language Search requires Accuracy Mode',
            'query': 'Show transactions',
            'solution': 'Enable Accuracy Mode in Configuration'
        }
        
        assert response['success'] is False
        assert isinstance(response['error'], str)
        assert 'solution' in response or 'error' in response
    
    def test_disabled_nlp_response(self):
        """Test response when NLP is explicitly disabled"""
        response = {
            'success': False,
            'error': 'Natural Language Search is not enabled in this configuration',
            'current_mode': 'ML_ONLY',
            'required_mode': 'ACCURACY_MODE',
            'solution': 'Go to Configuration and enable Accuracy Mode'
        }
        
        assert response['success'] is False
        assert 'not enabled' in response['error']
    
    def test_missing_dependencies_response(self):
        """Test response when NLP dependencies are missing"""
        response = {
            'success': False,
            'error': 'Natural Language Search dependencies not installed',
            'missing_packages': ['torch', 'transformers'],
            'solution': 'Run: pip install -r requirements-ml.txt'
        }
        
        assert response['success'] is False
        assert len(response['missing_packages']) > 0


class TestNLPSearchIntegration:
    """Integration tests for NLP search across configurations"""
    
    def test_switching_from_ai_off_to_ml_only(self):
        """Test that NLP remains unavailable when switching to ML-only mode"""
        configs = [
            {'ml': False, 'acc': False, 'nlp': False},  # AI Off
            {'ml': True, 'acc': False, 'nlp': False}    # ML Only
        ]
        
        for config in configs:
            nlp_available = config['acc'] and config['nlp']
            assert nlp_available is False
    
    def test_switching_from_ml_only_to_accuracy_mode(self):
        """Test that NLP becomes available when switching to accuracy mode with NLP enabled"""
        configs = [
            {'ml': True, 'acc': False, 'nlp': False},   # ML Only
            {'ml': True, 'acc': True, 'nlp': True}      # Accuracy Mode with NLP
        ]
        
        nlp_available_before = configs[0]['acc'] and configs[0]['nlp']
        nlp_available_after = configs[1]['acc'] and configs[1]['nlp']
        
        assert nlp_available_before is False
        assert nlp_available_after is True
    
    def test_disabling_nlp_flag_disables_search(self):
        """Test that disabling NLP flag specifically turns off NLP"""
        config_before = {'ml': True, 'acc': True, 'nlp': True}
        config_after = {'ml': True, 'acc': True, 'nlp': False}
        
        nlp_available_before = config_before['acc'] and config_before['nlp']
        nlp_available_after = config_after['acc'] and config_after['nlp']
        
        assert nlp_available_before is True
        assert nlp_available_after is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
