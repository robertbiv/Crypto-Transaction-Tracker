"""Price Fetcher Integration Tests"""
from test_common import *

class TestPriceFetcherIntegration(unittest.TestCase):
    """Tests for PriceFetcher integration to catch method name and datetime errors"""
    
    def setUp(self):
        print(f"\n[Running: {self._testMethodName}]", flush=True)
    
    def test_price_fetcher_has_get_price_method(self):
        """Test: PriceFetcher has get_price method (not fetch)"""
        fetcher = app.PriceFetcher()
        
        # Verify method exists
        self.assertTrue(hasattr(fetcher, 'get_price'))
        self.assertTrue(callable(getattr(fetcher, 'get_price')))
        
        # Verify 'fetch' method does NOT exist (common typo)
        self.assertFalse(hasattr(fetcher, 'fetch'))
    
    def test_price_fetcher_signature(self):
        """Test: PriceFetcher.get_price() signature check"""
        import inspect
        fetcher = app.PriceFetcher()
        
        # Get the signature of get_price method
        sig = inspect.signature(fetcher.get_price)
        params = list(sig.parameters.keys())
        
        # Should have parameters for symbol and date
        self.assertEqual(len(params), 2, "get_price should accept 2 parameters (symbol, date)")




if __name__ == '__main__':
    unittest.main()


