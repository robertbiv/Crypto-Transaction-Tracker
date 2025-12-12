import unittest
from unittest.mock import patch, MagicMock
import requests
import ccxt
import pandas as pd
from datetime import datetime
from decimal import Decimal

# Import your application modules
import Crypto_Tax_Engine as app
from Interactive_Review_Fixer import InteractiveReviewFixer

class TestCCXTErrors(unittest.TestCase):
    """Simulate Cryptocurrency Exchange (CCXT) Errors"""

    @patch('ccxt.binance')
    def test_ccxt_network_error_during_sync(self, mock_binance_cls):
        """
        Test: CCXT NetworkError (e.g., DNS failure) during trade sync.
        The system should catch the error, stop syncing that exchange, but NOT crash.
        """
        # Setup mock exchange
        mock_ex = MagicMock()
        # Simulate NetworkError on first call
        mock_ex.fetch_my_trades.side_effect = ccxt.NetworkError("Connection timed out")
        mock_binance_cls.return_value = mock_ex
        
        # Setup DB and Ingestor
        db = app.DatabaseManager()
        ingestor = app.Ingestor(db)
        
        # Mock keys file to trigger the loop
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', unittest.mock.mock_open(read_data='{"binance": {"apiKey": "test", "secret": "test"}}')):
            
            # This should NOT raise an exception. It should log the error and return.
            try:
                ingestor.run_api_sync()
            except Exception as e:
                self.fail(f"Ingestor crashed on NetworkError: {e}")
                
        # Verify no trades were saved (since it failed immediately)
        df = db.get_all()
        self.assertEqual(len(df), 0)

    @patch('ccxt.coinbase')
    def test_ccxt_auth_error(self, mock_coinbase_cls):
        """
        Test: CCXT AuthenticationError (Invalid API Keys).
        The system should skip this exchange and continue.
        """
        mock_ex = MagicMock()
        mock_ex.fetch_my_trades.side_effect = ccxt.AuthenticationError("Invalid API Key")
        mock_coinbase_cls.return_value = mock_ex
        
        db = app.DatabaseManager()
        ingestor = app.Ingestor(db)
        
        with patch('pathlib.Path.exists', return_value=True), \
             patch('builtins.open', unittest.mock.mock_open(read_data='{"coinbase": {"apiKey": "wrong", "secret": "wrong"}}')):
            
            # Should run without crashing
            ingestor.run_api_sync()
            
        # Verify safe exit
        self.assertTrue(True)


class TestYFinanceErrors(unittest.TestCase):
    """Simulate Yahoo Finance API Errors"""

    @patch('yfinance.download')
    def test_yfinance_empty_response_delisted_coin(self, mock_download):
        """
        Test: YFinance returns empty data (e.g., delisted or unknown coin).
        PriceFetcher should return None, not crash.
        """
        # Simulate empty DataFrame (what yf returns for bad tickers)
        mock_download.return_value = pd.DataFrame()
        
        fetcher = app.PriceFetcher()
        
        # Try to fetch price for a made-up coin
        price = fetcher.get_price('NONEXISTENTCOIN', datetime(2023, 1, 1))
        
        # Should return None (handled gracefully)
        self.assertIsNone(price)

    @patch('yfinance.download')
    def test_yfinance_api_exception(self, mock_download):
        """
        Test: YFinance library raises an Exception (e.g., JSON decode error).
        PriceFetcher should catch it and return None.
        """
        mock_download.side_effect = Exception("YFinance internal error")
        
        fetcher = app.PriceFetcher()
        price = fetcher.get_price('BTC', datetime(2023, 1, 1))
        
        self.assertIsNone(price)


class TestCoinGeckoErrors(unittest.TestCase):
    """Simulate CoinGecko API Failures"""

    @patch('requests.get')
    def test_coingecko_500_server_error(self, mock_get):
        """
        Test: CoinGecko returns 500 Internal Server Error.
        The interactive fixer should retry (exponential backoff) and eventually fail gracefully.
        """
        # Simulate persistent 500 errors
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        db = app.DatabaseManager()
        fixer = InteractiveReviewFixer(db, 2024)
        
        # Run fetcher (mocking sleep to speed up test)
        with patch('time.sleep'):
            token_map = fixer._fetch_token_addresses_from_api()
        
        # Should return empty dict after retries fail
        self.assertEqual(token_map, {})
        
        # Verify it retried multiple times (default is 5 retries)
        self.assertGreaterEqual(mock_get.call_count, 5)


class TestBlockchairErrors(unittest.TestCase):
    """Simulate Blockchair (Bitcoin) API Errors"""

    @patch('requests.get')
    def test_blockchair_403_forbidden_invalid_key(self, mock_get):
        """
        Test: Blockchair returns 403 Forbidden (Invalid API Key).
        Auditor/Fixer should handle this without crashing.
        """
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        
        db = app.DatabaseManager()
        fixer = InteractiveReviewFixer(db, 2024)
        
        # Try to check transaction with invalid key
        found, price, details = fixer._check_bitcoin_transaction(
            ['bc1q...'], '2024-01-01', 1.0, 'invalid_key'
        )
        
        # Should return False (not found) gracefully
        self.assertFalse(found)
        self.assertIsNone(price)
        # Note: Your code might return specific error text, or just generic "not found"
        # We verify it didn't crash and returned a False result


class TestEtherscanErrors(unittest.TestCase):
    """Simulate Etherscan/EVM API Errors"""

    @patch('requests.get')
    def test_etherscan_timeout(self, mock_get):
        """
        Test: Etherscan request times out.
        System should catch requests.exceptions.Timeout.
        """
        mock_get.side_effect = requests.exceptions.Timeout("Read timed out")
        
        db = app.DatabaseManager()
        fixer = InteractiveReviewFixer(db, 2024)
        
        # Try checking EVM transaction
        found, price, details = fixer._check_evm_transaction(
            ['0x123...'], 'ETH', '2024-01-01', 1.0
        )
        
        # Should return False (not found) gracefully
        self.assertFalse(found)
        self.assertIn("lookup error", str(details).lower() if details else "")

if __name__ == '__main__':
    unittest.main()