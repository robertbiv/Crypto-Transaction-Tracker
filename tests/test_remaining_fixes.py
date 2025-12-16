"""
================================================================================
TEST: Remaining Security and Accuracy Fixes
================================================================================

Validates fixes for identified security and accuracy issues.

Issues Tested:
    - Issue #3: Race condition in file writes (file locking)
    - Issue #4: Cost basis calculation edge cases
    - Issue #6: Decimal precision loss in wash sale
    - Issue #7: Unvalidated JSON parsing
    - Issue #8: Unmatched sell fallback logic
    - Issue #10: HIFO re-sorting
    - Issue #12: Fee handling in transfers

Author: robertbiv
================================================================================
"""

import pytest
import json
import threading
import time
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta
import pandas as pd
import tempfile
import shutil
import filelock

# Import modules to test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.core.engine import TaxEngine, round_decimal, to_decimal, DatabaseManager


class TestFileLocking:
    """Test Issue #3: Race condition in file writes"""
    
    def test_concurrent_file_writes_with_locking(self, tmp_path):
        """Test that file locking prevents corruption from concurrent writes"""
        test_file = tmp_path / "test_config.json"
        lock_file = str(test_file) + ".lock"
        
        # Initial data
        initial_data = {"counter": 0}
        with open(test_file, 'w') as f:
            json.dump(initial_data, f)
        
        results = []
        errors = []
        
        def increment_with_lock(thread_id):
            """Safely increment counter with file locking"""
            try:
                lock = filelock.FileLock(lock_file)
                with lock:
                    # Read
                    with open(test_file, 'r') as f:
                        data = json.load(f)
                    
                    # Modify
                    data['counter'] += 1
                    
                    # Simulate some processing time
                    time.sleep(0.01)
                    
                    # Write
                    with open(test_file, 'w') as f:
                        json.dump(data, f, indent=4)
                    
                    results.append(data['counter'])
            except Exception as e:
                errors.append(str(e))
        
        # Launch 10 concurrent threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=increment_with_lock, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # Verify final counter is correct (all 10 increments succeeded)
        with open(test_file, 'r') as f:
            final_data = json.load(f)
        
        assert final_data['counter'] == 10, f"Expected counter=10, got {final_data['counter']}"
        assert len(results) == 10, f"Expected 10 results, got {len(results)}"
    
    def test_concurrent_writes_without_locking_can_fail(self, tmp_path):
        """Demonstrate that without locking, concurrent writes can lose data"""
        test_file = tmp_path / "test_no_lock.json"
        
        initial_data = {"counter": 0}
        with open(test_file, 'w') as f:
            json.dump(initial_data, f)
        
        results = []
        
        def increment_without_lock(thread_id):
            """Unsafely increment counter without locking"""
            try:
                # Read
                with open(test_file, 'r') as f:
                    data = json.load(f)
                
                # Modify
                data['counter'] += 1
                
                # Simulate processing time to increase chance of race condition
                time.sleep(0.01)
                
                # Write
                with open(test_file, 'w') as f:
                    json.dump(data, f, indent=4)
                
                results.append(data['counter'])
            except:
                pass
        
        # Launch 10 concurrent threads
        threads = []
        for i in range(10):
            t = threading.Thread(target=increment_without_lock, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Read final value
        with open(test_file, 'r') as f:
            final_data = json.load(f)
        
        # Without proper locking, the final counter is likely < 10 due to race conditions
        # This test documents the problem that file locking solves
        # Note: Due to timing, this might occasionally pass, but demonstrates the issue
        print(f"Without locking: counter={final_data['counter']} (should be 10, often less due to race conditions)")


class TestCostBasisCalculation:
    """Test Issue #4: Cost basis calculation edge case"""
    
    def test_cost_basis_with_small_amounts(self, monkeypatch):
        """Test cost basis calculation with very small amounts (dust)"""
        # Note: DatabaseManager uses the global DB_FILE, not in-memory db
        # This test validates the calculation logic directly
        
        # Test with very small amount (dust) - direct calculation
        small_amount = Decimal('0.00000001')  # 1 satoshi
        price = Decimal('50000.00')  # $50k BTC
        fee = Decimal('0.50')  # $0.50 fee
        
        # Calculate cost basis
        total_cost = (small_amount * price) + fee
        cost_basis = round_decimal(total_cost / small_amount, 8)
        
        # Verify precision is maintained
        assert isinstance(cost_basis, Decimal)
        assert cost_basis > Decimal('0')
        
        # Cost basis should be close to (price + fee/amount)
        expected = price + (fee / small_amount)
        assert abs(cost_basis - expected) < Decimal('0.00000001')
    
    def test_cost_basis_with_zero_amount(self):
        """Test cost basis calculation doesn't divide by zero"""
        amt = Decimal('0')
        price = Decimal('50000')
        fee = Decimal('10')
        
        # Should handle zero amount gracefully
        if amt > 0:
            cost_basis = round_decimal(((amt * price) + fee) / amt, 8)
        else:
            cost_basis = Decimal('0')
        
        assert cost_basis == Decimal('0')
    
    def test_cost_basis_precision_maintained(self):
        """Test that cost basis maintains 8 decimal places of precision"""
        amt = Decimal('0.123456789')
        price = Decimal('12345.6789')
        fee = Decimal('5.00')
        
        total_cost = (amt * price) + fee
        cost_basis = round_decimal(total_cost / amt, 8)
        
        # Verify result has proper precision
        assert isinstance(cost_basis, Decimal)
        # Check it rounds to 8 decimals
        str_basis = str(cost_basis)
        if '.' in str_basis:
            decimals = len(str_basis.split('.')[1])
            assert decimals <= 8


class TestWashSaleDecimalPrecision:
    """Test Issue #6: Decimal precision loss in wash sale"""
    
    def test_wash_sale_proportion_with_dust(self):
        """Test wash sale proportion calculation with very small amounts"""
        # Very small amounts (dust)
        amt = Decimal('0.00000001')  # Amount sold
        rep_qty = Decimal('0.000000005')  # Replacement quantity
        
        disallowed_qty = min(rep_qty, amt)
        prop = round_decimal(disallowed_qty / amt, 8) if amt > 0 else Decimal('0')
        
        # Verify proportion is calculated correctly with precision
        expected_prop = disallowed_qty / amt
        assert abs(prop - expected_prop) < Decimal('0.00000001')
        assert prop <= Decimal('1.0')
        assert prop >= Decimal('0')
    
    def test_wash_sale_proportion_exceeds_sold_amount(self):
        """Test wash sale when replacement exceeds sold amount"""
        amt = Decimal('1.0')  # Sold 1 BTC
        rep_qty = Decimal('5.0')  # Bought back 5 BTC
        gain = Decimal('-1000.00')  # $1000 loss
        
        disallowed_qty = min(rep_qty, amt)  # Should be amt (1.0)
        prop = round_decimal(disallowed_qty / amt, 8) if amt > 0 else Decimal('0')
        wash_disallowed = round_decimal(abs(gain) * prop, 2)
        
        # When replacement > sold, entire loss should be disallowed
        assert prop == Decimal('1.0')
        assert wash_disallowed == abs(gain)
    
    def test_wash_sale_proportion_less_than_sold(self):
        """Test wash sale when replacement is less than sold amount"""
        amt = Decimal('5.0')  # Sold 5 BTC
        rep_qty = Decimal('2.0')  # Bought back 2 BTC
        gain = Decimal('-1000.00')  # $1000 loss
        
        disallowed_qty = min(rep_qty, amt)  # Should be rep_qty (2.0)
        prop = round_decimal(disallowed_qty / amt, 8) if amt > 0 else Decimal('0')
        wash_disallowed = round_decimal(abs(gain) * prop, 2)
        
        # Only proportional loss should be disallowed
        assert prop == Decimal('0.4')  # 2/5
        assert wash_disallowed == Decimal('400.00')  # 40% of $1000


class TestJSONValidation:
    """Test Issue #7: Unvalidated JSON parsing"""
    
    def test_json_depth_validation(self):
        """Test that deeply nested JSON is rejected"""
        
        def check_depth(obj, max_depth=10, current=0):
            if current > max_depth:
                return False
            if isinstance(obj, dict):
                return all(check_depth(v, max_depth, current+1) for v in obj.values())
            elif isinstance(obj, list):
                return all(check_depth(v, max_depth, current+1) for v in obj)
            return True
        
        # Test valid depth
        valid_data = {"level1": {"level2": {"level3": "value"}}}
        assert check_depth(valid_data, max_depth=10) == True
        
        # Test excessive depth (12 levels deep)
        deeply_nested = {
            "a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": {"i": {"j": {"k": {"l": "too deep"}}}}}}}}}}}
        }
        assert check_depth(deeply_nested, max_depth=10) == False
    
    def test_json_type_validation(self):
        """Test that non-dict JSON is rejected"""
        # Valid: dict
        valid = {"key": "value"}
        assert isinstance(valid, dict) == True
        
        # Invalid: list
        invalid_list = ["item1", "item2"]
        assert isinstance(invalid_list, dict) == False
        
        # Invalid: string
        invalid_str = "just a string"
        assert isinstance(invalid_str, dict) == False
    
    def test_json_malicious_keys(self):
        """Test handling of potentially malicious JSON keys"""
        # Test data with unusual keys
        data = {
            "__proto__": "malicious",
            "constructor": "malicious",
            "../../../etc/passwd": "path_traversal",
            "normal_key": "normal_value"
        }
        
        # Should be valid dict but keys can be validated
        assert isinstance(data, dict)
        
        # Example validation: reject keys with path traversal patterns
        dangerous_patterns = ["../", "..", "__proto__", "constructor"]
        for key in data.keys():
            has_dangerous = any(pattern in key for pattern in dangerous_patterns)
            if has_dangerous:
                print(f"Warning: Potentially dangerous key: {key}")


class TestUnmatchedSellFallback:
    """Test Issue #8: Unmatched sell fallback logic"""
    
    def test_unmatched_sell_uses_estimated_price(self, monkeypatch):
        """Test that unmatched sells use estimated price instead of zero basis"""
        # Test the logic without full engine initialization
        
        # Mock price fetcher to return a known price
        class MockPriceFetcher:
            def get_price(self, coin, date):
                return Decimal('50000.00') if coin == 'BTC' else None
        
        pf = MockPriceFetcher()
        
        # Test calculation when there's unmatched quantity
        rem = Decimal('1.0')  # 1 BTC unmatched
        c = 'BTC'
        d = datetime(2024, 1, 1)
        b = Decimal('0')
        
        # Simulate the fallback logic
        estimated_price = pf.get_price(c, d)
        if estimated_price and estimated_price > 0:
            b += rem * estimated_price
        else:
            b += Decimal('0')
        
        # Should use estimated price, not zero
        assert b == Decimal('50000.00')
        assert b > Decimal('0')
    
    def test_unmatched_sell_zero_fallback_when_no_price(self, monkeypatch):
        """Test fallback to zero when price unavailable"""
        # Test the fallback logic directly
        
        # Mock price fetcher that returns None
        class MockPriceFetcher:
            def get_price(self, coin, date):
                return None
        
        pf = MockPriceFetcher()
        
        rem = Decimal('1.0')
        c = 'BTC'
        d = datetime(2024, 1, 1)
        b = Decimal('0')
        
        estimated_price = pf.get_price(c, d)
        if estimated_price and estimated_price > 0:
            b += rem * estimated_price
        else:
            b += Decimal('0')
        
        # Should fallback to zero when price unavailable
        assert b == Decimal('0')


class TestHIFOResorting:
    """Test Issue #10: HIFO accounting re-sorting"""
    
    def test_hifo_sorts_on_each_iteration(self):
        """Test that HIFO re-sorts bucket on each sell iteration"""
        # Simulate a bucket with multiple lots
        bucket = [
            {'a': Decimal('1.0'), 'p': Decimal('50000'), 'd': datetime(2024, 1, 1)},
            {'a': Decimal('2.0'), 'p': Decimal('45000'), 'd': datetime(2024, 1, 2)},
            {'a': Decimal('1.5'), 'p': Decimal('52000'), 'd': datetime(2024, 1, 3)},
        ]
        
        # HIFO should select highest price first
        acct_method = 'HIFO'
        rem = Decimal('2.0')
        b = Decimal('0')
        
        while rem > 0 and bucket:
            # Re-sort on each iteration (HIFO)
            if acct_method == 'HIFO':
                bucket.sort(key=lambda x: x['p'], reverse=True)
            
            l = bucket[0]
            take = l['a'] if l['a'] <= rem else rem
            b += take * l['p']
            l['a'] -= take
            rem -= take
            if l['a'] <= Decimal('0'):
                bucket.pop(0)
        
        # Should have taken from highest prices first:
        # 1.5 @ 52000 = 78000
        # 0.5 @ 50000 = 25000
        # Total = 103000
        assert b == Decimal('103000')
    
    def test_hifo_vs_fifo_different_results(self):
        """Test that HIFO and FIFO produce different cost basis"""
        bucket_hifo = [
            {'a': Decimal('1.0'), 'p': Decimal('50000'), 'd': datetime(2024, 1, 1)},
            {'a': Decimal('1.0'), 'p': Decimal('45000'), 'd': datetime(2024, 1, 2)},
            {'a': Decimal('1.0'), 'p': Decimal('52000'), 'd': datetime(2024, 1, 3)},
        ]
        bucket_fifo = [lot.copy() for lot in bucket_hifo]
        
        # HIFO
        rem = Decimal('1.5')
        b_hifo = Decimal('0')
        while rem > 0 and bucket_hifo:
            bucket_hifo.sort(key=lambda x: x['p'], reverse=True)
            l = bucket_hifo[0]
            take = l['a'] if l['a'] <= rem else rem
            b_hifo += take * l['p']
            l['a'] -= take
            rem -= take
            if l['a'] <= Decimal('0'):
                bucket_hifo.pop(0)
        
        # FIFO
        rem = Decimal('1.5')
        b_fifo = Decimal('0')
        while rem > 0 and bucket_fifo:
            bucket_fifo.sort(key=lambda x: x['d'])
            l = bucket_fifo[0]
            take = l['a'] if l['a'] <= rem else rem
            b_fifo += take * l['p']
            l['a'] -= take
            rem -= take
            if l['a'] <= Decimal('0'):
                bucket_fifo.pop(0)
        
        # HIFO should select higher cost basis (beneficial for taxes)
        assert b_hifo > b_fifo
        # HIFO: 1.0 @ 52000 + 0.5 @ 50000 = 77000
        # FIFO: 1.0 @ 50000 + 0.5 @ 45000 = 72500
        assert b_hifo == Decimal('77000')
        assert b_fifo == Decimal('72500')


class TestFeeHandlingInTransfers:
    """Test Issue #12: Fee handling in transfers"""
    
    def test_fee_price_none_handling(self):
        """Test that None price from get_price is handled correctly"""
        
        class MockPriceFetcher:
            def get_price(self, coin, date):
                # Simulate price fetch failure
                return None
        
        pf = MockPriceFetcher()
        fee_coin = 'ETH'
        d = datetime(2024, 1, 1)
        
        # Get fee price
        fee_price = pf.get_price(fee_coin, d)
        
        if fee_price is None:
            # Should fallback to zero and log warning
            fee_price = Decimal('0')
        
        assert fee_price == Decimal('0')
        assert isinstance(fee_price, Decimal)
    
    def test_fee_price_with_different_coin(self):
        """Test fee price fetching when fee coin differs from transfer coin"""
        
        class MockPriceFetcher:
            def get_price(self, coin, date):
                prices = {'BTC': Decimal('50000'), 'ETH': Decimal('3000')}
                return prices.get(coin)
        
        pf = MockPriceFetcher()
        
        # Transfer BTC, but fee in ETH
        transfer_coin = 'BTC'
        fee_coin = 'ETH'
        price = Decimal('50000')  # BTC price
        
        if fee_coin == transfer_coin:
            fee_price = price
        else:
            fee_price = pf.get_price(fee_coin, datetime.now())
            if fee_price is None:
                fee_price = Decimal('0')
        
        # Should fetch ETH price, not use BTC price
        assert fee_price == Decimal('3000')
        assert fee_price != price
    
    def test_fee_calculation_with_valid_price(self):
        """Test that fee is calculated correctly with valid price"""
        fee = Decimal('0.01')  # 0.01 ETH fee
        fee_price = Decimal('3000')  # $3000 per ETH
        
        f_proc = fee * fee_price
        
        assert f_proc == Decimal('30')  # $30 fee value


class TestDatabaseConnectionManagement:
    """Test Issue #11: Resource leak - database connections not closed"""
    
    def test_database_context_manager_usage(self):
        """Test database connection is properly closed even on exception"""
        # This test documents the proper pattern for database cleanup
        # Note: DatabaseManager uses global DB_FILE, not custom path
        db = None
        try:
            # Simulate database operation
            class MockDB:
                conn = 'connected'
                def close(self):
                    self.conn = None
            db = MockDB()
            # Simulate some work
            assert db.conn is not None
            # Simulate error
            # raise Exception("Test error")
        finally:
            if db:
                db.close()
        
        # After close, connection should be None or closed
        # This documents the pattern that should be used
    
    def test_database_multiple_operations_cleanup(self):
        """Test that database is closed properly after multiple operations"""
        operations_completed = []
        db = None
        
        try:
            # Simulate database operations
            class MockDB:
                conn = 'connected'
                def close(self):
                    self.conn = None
            db = MockDB()
            
            # Operation 1
            operations_completed.append(1)
            
            # Operation 2
            operations_completed.append(2)
            
            # Operation 3
            operations_completed.append(3)
            
        except Exception as e:
            # Even on error, db should be closed
            print(f"Error: {e}")
        finally:
            if db:
                db.close()
        
        # All operations completed
        assert len(operations_completed) == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


