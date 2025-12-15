"""Tests for API key and wallet validation endpoints"""
import unittest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import sys

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

import web_server as ws


class TestAPIWalletValidation(unittest.TestCase):
    """Test validation endpoints for API keys and wallets"""
    
    def setUp(self):
        """Set up test client"""
        self.tmpdir = Path(tempfile.mkdtemp())
        ws.USERS_FILE = self.tmpdir / 'web_users.json'
        ws.API_KEYS_FILE = self.tmpdir / 'api_keys.json'
        ws.WALLETS_FILE = self.tmpdir / 'wallets.json'
        ws.CONFIG_FILE = self.tmpdir / 'config.json'
        ws.DB_FILE = self.tmpdir / 'crypto_master.db'
        
        # Create test user
        users = {
            'testuser': {
                'password_hash': ws.bcrypt.hashpw('password123'.encode('utf-8'), ws.bcrypt.gensalt()).decode('utf-8'),
                'is_admin': True
            }
        }
        with open(ws.USERS_FILE, 'w') as f:
            json.dump(users, f)
        
        ws.app.config['TESTING'] = True
        self.client = ws.app.test_client()
        
        # Login
        with self.client.session_transaction() as sess:
            sess['username'] = 'testuser'
            sess['csrf_token'] = 'test-token'
    
    @patch('ccxt.binance')
    def test_valid_api_key(self, mock_binance):
        """Test endpoint with valid API key"""
        mock_exchange = MagicMock()
        mock_exchange.fetch_balance.return_value = {'BTC': {'free': 1.0}}
        mock_binance.return_value = mock_exchange
        
        response = self.client.post(
            '/api/api-keys/test',
            json={
                'exchange': 'binance',
                'apiKey': 'test_key',
                'secret': 'test_secret'
            },
            headers={'X-CSRF-Token': 'test-token'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('valid', data['message'].lower())
    
    @patch('ccxt.binance')
    def test_invalid_api_key(self, mock_binance):
        """Test endpoint with invalid API key"""
        mock_exchange = MagicMock()
        import ccxt
        mock_exchange.fetch_balance.side_effect = ccxt.AuthenticationError('Invalid API key')
        mock_binance.return_value = mock_exchange
        
        response = self.client.post(
            '/api/api-keys/test',
            json={
                'exchange': 'binance',
                'apiKey': 'bad_key',
                'secret': 'bad_secret'
            },
            headers={'X-CSRF-Token': 'test-token'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertIn('authentication', data['error'].lower())
    
    def test_valid_bitcoin_address(self):
        """Test valid Bitcoin address"""
        response = self.client.post(
            '/api/wallets/test',
            json={
                'blockchain': 'BTC',
                'address': '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'
            },
            headers={'X-CSRF-Token': 'test-token'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('valid', data['message'].lower())
    
    def test_valid_ethereum_address(self):
        """Test valid Ethereum address"""
        response = self.client.post(
            '/api/wallets/test',
            json={
                'blockchain': 'ETH',
                'address': '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEbA'
            },
            headers={'X-CSRF-Token': 'test-token'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])
        self.assertIn('valid', data['message'].lower())
    
    def test_invalid_bitcoin_address(self):
        """Test invalid Bitcoin address"""
        response = self.client.post(
            '/api/wallets/test',
            json={
                'blockchain': 'BTC',
                'address': 'invalid_address_123'
            },
            headers={'X-CSRF-Token': 'test-token'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertIn('invalid', data['error'].lower())
    
    def test_missing_fields(self):
        """Test with missing required fields"""
        response = self.client.post(
            '/api/api-keys/test',
            json={'exchange': 'binance'},
            headers={'X-CSRF-Token': 'test-token'}
        )
        
        self.assertEqual(response.status_code, 400)
    
    def tearDown(self):
        """Clean up"""
        import shutil
        shutil.rmtree(self.tmpdir)


if __name__ == '__main__':
    unittest.main()
