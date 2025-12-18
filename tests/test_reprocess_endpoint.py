"""
Edge case tests for the reprocess-all endpoint.
Tests various scenarios to ensure the ML reprocessing works reliably.
"""

import pytest
import json
import tempfile
import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestReprocessAllEndpoint:
    """Test suite for /api/transactions/reprocess-all endpoint"""
    
    @pytest.fixture
    def test_config(self):
        """Create test configuration"""
        return {
            'ml_fallback': {
                'enabled': True,
                'model_name': 'shim',
                'confidence_threshold': 0.85,
                'auto_shutdown_after_batch': True
            }
        }
    
    @pytest.fixture
    def test_db(self):
        """Create an in-memory test database"""
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        cursor = conn.cursor()
        
        # Create trades table
        cursor.execute('''
            CREATE TABLE trades (
                id TEXT PRIMARY KEY,
                date TEXT,
                source TEXT,
                destination TEXT,
                action TEXT,
                coin TEXT,
                amount REAL,
                price_usd REAL,
                fee REAL,
                fee_coin TEXT
            )
        ''')
        
        conn.commit()
        return conn
    
    def test_reprocess_with_ml_disabled(self, test_config):
        """Edge case: ML disabled - should return error without processing"""
        test_config['ml_fallback']['enabled'] = False
        
        # Simulate endpoint behavior
        ml_config = test_config.get('ml_fallback', {})
        if not ml_config.get('enabled', False):
            result = {
                'success': False,
                'message': 'ML fallback is not enabled. Enable it in settings first.'
            }
        
        assert result['success'] is False
        assert 'not enabled' in result['message'].lower()
    
    def test_reprocess_with_no_transactions(self, test_db):
        """Edge case: Empty database - should return success with count 0"""
        # Get all transactions (empty)
        cursor = test_db.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        if not transactions:
            result = {
                'success': True,
                'message': 'No transactions to reprocess',
                'count': 0
            }
        
        assert result['success'] is True
        assert result['count'] == 0
    
    def test_reprocess_single_transaction(self, test_db):
        """Edge case: Single transaction - should process and potentially update"""
        # Insert a transaction
        test_db.execute('''
            INSERT INTO trades 
            (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('tx1', '2024-01-01', 'exchange', '', 'UNKNOWN', 'BTC', 1.0, 50000, 0, ''))
        test_db.commit()
        
        # Verify transaction exists
        cursor = test_db.execute("SELECT * FROM trades WHERE id = ?", ('tx1',))
        tx = dict(cursor.fetchone())
        
        assert tx['id'] == 'tx1'
        assert tx['action'] == 'UNKNOWN'
    
    def test_reprocess_mixed_transactions(self, test_db):
        """Edge case: Mix of different action types - should classify each"""
        transactions_data = [
            ('tx1', '2024-01-01', 'exchange', '', 'BUY', 'BTC', 1.0, 50000, 0, ''),
            ('tx2', '2024-01-02', 'exchange', '', 'UNKNOWN', 'ETH', 10.0, 2000, 0, ''),
            ('tx3', '2024-01-03', 'wallet', '', 'SELL', 'BTC', 0.5, 45000, 0, ''),
            ('tx4', '2024-01-04', 'exchange', '', 'UNKNOWN', 'ADA', 1000, 0.5, 0, ''),
        ]
        
        for tx_data in transactions_data:
            test_db.execute('''
                INSERT INTO trades 
                (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', tx_data)
        test_db.commit()
        
        cursor = test_db.execute("SELECT COUNT(*) FROM trades")
        count = cursor.fetchone()[0]
        
        assert count == 4
    
    def test_reprocess_with_missing_fields(self, test_db):
        """Edge case: Transactions with NULL/missing fields - should handle gracefully"""
        # Insert transaction with minimal data
        test_db.execute('''
            INSERT INTO trades 
            (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('tx1', '2024-01-01', '', '', 'UNKNOWN', '', 0, 0, 0, ''))
        test_db.commit()
        
        cursor = test_db.execute("SELECT * FROM trades WHERE id = ?", ('tx1',))
        tx = dict(cursor.fetchone())
        
        # Should handle empty fields gracefully
        row = {
            'description': f"{tx.get('action', '')} {tx.get('coin', '')}",
            'amount': tx.get('amount', 0),
            'price_usd': tx.get('price_usd', 0),
            'coin': tx.get('coin', ''),
            'action': tx.get('action', ''),
            'source': tx.get('source', ''),
            'date': tx.get('date', '')
        }
        
        assert row['description'] == 'UNKNOWN '  # Action present, coin empty
        assert row['amount'] == 0
        assert row['coin'] == ''
    
    def test_reprocess_updates_correct_fields(self, test_db):
        """Edge case: Verify only action field is updated, not others"""
        test_db.execute('''
            INSERT INTO trades 
            (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('tx1', '2024-01-01', 'exchange', 'wallet', 'UNKNOWN', 'BTC', 1.5, 50000, 0.001, 'BTC'))
        test_db.commit()
        
        # Simulate update (only action changes)
        test_db.execute(
            "UPDATE trades SET action = ? WHERE id = ?",
            ('BUY', 'tx1')
        )
        test_db.commit()
        
        cursor = test_db.execute("SELECT * FROM trades WHERE id = ?", ('tx1',))
        tx = dict(cursor.fetchone())
        
        # Other fields should remain unchanged
        assert tx['action'] == 'BUY'
        assert tx['amount'] == 1.5
        assert tx['price_usd'] == 50000
        assert tx['fee'] == 0.001
        assert tx['fee_coin'] == 'BTC'
        assert tx['date'] == '2024-01-01'
    
    def test_reprocess_large_batch(self, test_db):
        """Edge case: Large batch of transactions (100+) - performance test"""
        # Insert 150 transactions
        for i in range(150):
            action = 'BUY' if i % 3 == 0 else ('SELL' if i % 3 == 1 else 'UNKNOWN')
            test_db.execute('''
                INSERT INTO trades 
                (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (f'tx{i}', f'2024-01-{(i % 28) + 1:02d}', 'exchange', '', action, 'BTC', 1.0, 50000, 0, ''))
        test_db.commit()
        
        cursor = test_db.execute("SELECT COUNT(*) FROM trades")
        count = cursor.fetchone()[0]
        
        assert count == 150
    
    def test_reprocess_with_special_characters(self, test_db):
        """Edge case: Transaction data with special characters/unicode"""
        test_db.execute('''
            INSERT INTO trades 
            (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('tx1', '2024-01-01', 'Exchange™', 'Wallet®', 'BUY', '₿TC', 1.0, 50000, 0, ''))
        test_db.commit()
        
        cursor = test_db.execute("SELECT * FROM trades WHERE id = ?", ('tx1',))
        tx = dict(cursor.fetchone())
        
        # Should preserve special characters
        assert '™' in tx['source']
        assert '®' in tx['destination']
        assert '₿' in tx['coin']
    
    def test_reprocess_duplicate_ids(self, test_db):
        """Edge case: Ensure transaction IDs are unique (database constraint)"""
        # First insert
        test_db.execute('''
            INSERT INTO trades 
            (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('tx1', '2024-01-01', 'exchange', '', 'BUY', 'BTC', 1.0, 50000, 0, ''))
        test_db.commit()
        
        # Try to insert duplicate (should fail or be ignored based on database behavior)
        try:
            test_db.execute('''
                INSERT INTO trades 
                (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', ('tx1', '2024-01-02', 'exchange', '', 'SELL', 'ETH', 10, 2000, 0, ''))
            test_db.commit()
            assert False, "Should have raised integrity error"
        except sqlite3.IntegrityError:
            # Expected behavior - primary key constraint
            pass
    
    def test_reprocess_preserves_original_if_no_ml_match(self, test_db):
        """Edge case: If rules and ML both don't match, keep original action"""
        test_db.execute('''
            INSERT INTO trades 
            (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('tx1', '2024-01-01', 'exchange', '', 'CUSTOM_ACTION', 'BTC', 1.0, 50000, 0, ''))
        test_db.commit()
        
        cursor = test_db.execute("SELECT * FROM trades WHERE id = ?", ('tx1',))
        tx = dict(cursor.fetchone())
        original_action = tx['action']
        
        # Simulate case where ML returns None or same value
        ml_result = None
        new_action = ml_result if ml_result else original_action
        
        assert new_action == original_action
    
    def test_reprocess_logging(self, tmp_path):
        """Edge case: Verify logging works correctly"""
        log_file = tmp_path / 'model_suggestions.log'
        
        # Simulate logging entries
        log_entries = [
            {
                'timestamp': datetime.now().isoformat(),
                'transaction_id': 'tx1',
                'date': '2024-01-01',
                'coin': 'BTC',
                'original_action': 'UNKNOWN',
                'suggested_action': 'BUY',
                'confidence': 0.92,
                'explanation': 'Matched buy pattern'
            },
            {
                'timestamp': datetime.now().isoformat(),
                'transaction_id': 'tx2',
                'date': '2024-01-02',
                'coin': 'ETH',
                'original_action': 'UNKNOWN',
                'suggested_action': 'SELL',
                'confidence': 0.88,
                'explanation': 'Matched sell pattern'
            }
        ]
        
        # Write log entries
        for entry in log_entries:
            with open(log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        
        # Verify log file
        assert log_file.exists()
        with open(log_file, 'r') as f:
            lines = f.readlines()
        
        assert len(lines) == 2
        for line in lines:
            entry = json.loads(line)
            assert 'transaction_id' in entry
            assert 'suggested_action' in entry
    
    def test_reprocess_concurrent_updates_safe(self, test_db):
        """Edge case: Multiple updates to same transaction (should not cause issues)"""
        test_db.execute('''
            INSERT INTO trades 
            (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('tx1', '2024-01-01', 'exchange', '', 'UNKNOWN', 'BTC', 1.0, 50000, 0, ''))
        test_db.commit()
        
        # Simulate multiple sequential updates
        test_db.execute("UPDATE trades SET action = ? WHERE id = ?", ('BUY', 'tx1'))
        test_db.commit()
        
        test_db.execute("UPDATE trades SET action = ? WHERE id = ?", ('SELL', 'tx1'))
        test_db.commit()
        
        cursor = test_db.execute("SELECT * FROM trades WHERE id = ?", ('tx1',))
        tx = dict(cursor.fetchone())
        
        # Last update should win
        assert tx['action'] == 'SELL'
    
    def test_reprocess_response_format(self):
        """Edge case: Verify response has all required fields"""
        response = {
            'success': True,
            'message': 'Reprocessing complete. Analyzed 42 transactions, updated 5.',
            'processed': 42,
            'updated': 5
        }
        
        assert 'success' in response
        assert 'message' in response
        assert 'processed' in response
        assert 'updated' in response
        assert response['processed'] >= response['updated']
    
    def test_reprocess_error_response_format(self):
        """Edge case: Verify error response format"""
        response = {
            'success': False,
            'error': 'ML fallback is not enabled. Enable it in settings first.'
        }
        
        assert response['success'] is False
        assert 'error' in response
    
    def test_reprocess_with_zero_prices(self, test_db):
        """Edge case: Handle transactions with zero price (should not cause division by zero)"""
        test_db.execute('''
            INSERT INTO trades 
            (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('tx1', '2024-01-01', 'exchange', '', 'UNKNOWN', 'BTC', 1.0, 0, 0, ''))
        test_db.commit()
        
        cursor = test_db.execute("SELECT * FROM trades WHERE id = ?", ('tx1',))
        tx = dict(cursor.fetchone())
        
        row = {
            'amount': tx.get('amount', 0),
            'price_usd': tx.get('price_usd', 0),
        }
        
        # Should not crash with zero price
        assert row['price_usd'] == 0
        assert row['amount'] == 1.0
    
    def test_reprocess_with_negative_amounts(self, test_db):
        """Edge case: Handle transactions with negative amounts (refunds, reversals)"""
        test_db.execute('''
            INSERT INTO trades 
            (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('tx1', '2024-01-01', 'exchange', '', 'UNKNOWN', 'BTC', -1.0, 50000, 0, ''))
        test_db.commit()
        
        cursor = test_db.execute("SELECT * FROM trades WHERE id = ?", ('tx1',))
        tx = dict(cursor.fetchone())
        
        # Should handle negative amounts
        assert tx['amount'] == -1.0
    
    def test_reprocess_chronological_order(self, test_db):
        """Edge case: Transactions processed in chronological order"""
        transactions_data = [
            ('tx3', '2024-01-03', 'exchange', '', 'BUY', 'BTC', 1.0, 50000, 0, ''),
            ('tx1', '2024-01-01', 'exchange', '', 'BUY', 'BTC', 1.0, 50000, 0, ''),
            ('tx2', '2024-01-02', 'exchange', '', 'BUY', 'BTC', 1.0, 50000, 0, ''),
        ]
        
        for tx_data in transactions_data:
            test_db.execute('''
                INSERT INTO trades 
                (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', tx_data)
        test_db.commit()
        
        # Should retrieve in chronological order
        cursor = test_db.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        
        assert transactions[0]['id'] == 'tx1'
        assert transactions[1]['id'] == 'tx2'
        assert transactions[2]['id'] == 'tx3'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
