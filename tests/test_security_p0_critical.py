"""
P0 Critical Security Tests
Tests for the most critical security vulnerabilities that must be addressed immediately.
"""

import pytest
import time
import threading
import sqlite3
import json
import socket
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import tempfile


class TestCSRFTokenExpiration:
    """Test CSRF token expiration and rotation"""
    
    def test_csrf_token_expires_after_timeout(self, app_client):
        """Test that CSRF tokens expire after configured timeout"""
        from src.web.server import generate_csrf_token, validate_csrf_token
        
        # Generate token
        token = generate_csrf_token()
        
        # Should be valid immediately
        assert validate_csrf_token(token) is True
        
        # Mock time to simulate expiration (typically 1 hour)
        with patch('time.time', return_value=time.time() + 3601):
            assert validate_csrf_token(token) is False, "Expired token should be invalid"
    
    def test_csrf_token_single_use(self, app_client):
        """Test that CSRF tokens can only be used once"""
        from src.web.server import generate_csrf_token, validate_csrf_token, consume_csrf_token
        
        token = generate_csrf_token()
        
        # First use should succeed
        assert validate_csrf_token(token) is True
        consume_csrf_token(token)
        
        # Second use should fail
        assert validate_csrf_token(token) is False, "Token should be invalid after consumption"
    
    def test_csrf_token_rotation_on_login(self, app_client):
        """Test that CSRF tokens are rotated after login"""
        from src.web.server import app
        
        # Get initial CSRF token
        response1 = app_client.get('/setup/wizard')
        assert response1.status_code == 200
        
        # Extract CSRF token from response
        csrf_token_1 = self._extract_csrf_token(response1.data)
        
        # Perform login (simulate)
        response2 = app_client.post('/api/setup/create-account', json={
            'username': 'testuser',
            'password': 'TestPass123!',
            'csrf_token': csrf_token_1
        })
        
        # Get new page, should have different CSRF token
        response3 = app_client.get('/setup/wizard')
        csrf_token_2 = self._extract_csrf_token(response3.data)
        
        assert csrf_token_1 != csrf_token_2, "CSRF token should rotate after authentication"
    
    def test_csrf_missing_token_rejected(self, app_client):
        """Test that requests without CSRF tokens are rejected"""
        from src.web.server import app
        
        response = app_client.post('/api/transactions/add', json={
            'date': '2024-01-01',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 1.0
        })
        
        assert response.status_code == 403, "Request without CSRF token should be rejected"
        data = json.loads(response.data)
        assert 'csrf' in data.get('error', '').lower()
    
    def test_csrf_invalid_token_rejected(self, app_client):
        """Test that requests with invalid CSRF tokens are rejected"""
        response = app_client.post('/api/transactions/add', 
            json={'date': '2024-01-01', 'action': 'BUY', 'coin': 'BTC', 'amount': 1.0},
            headers={'X-CSRF-Token': 'invalid_token_12345'}
        )
        
        assert response.status_code == 403
    
    def _extract_csrf_token(self, html_data):
        """Helper to extract CSRF token from HTML"""
        import re
        match = re.search(r'csrf_token["\s:=]+([a-zA-Z0-9_-]+)', html_data.decode())
        return match.group(1) if match else None


class TestConcurrentWriteConflicts:
    """Test concurrent database write scenarios"""
    
    def test_concurrent_transaction_updates_same_record(self, tmp_path):
        """Test that concurrent updates to the same transaction don't corrupt data"""
        from src.core.database import DatabaseManager
        
        db_path = tmp_path / "test_concurrent.db"
        db = DatabaseManager(str(db_path))
        
        # Insert initial transaction
        tx_id = db.add_transaction({
            'date': '2024-01-01',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 50000,
            'source': 'exchange'
        })
        
        results = []
        errors = []
        
        def update_transaction(field, value):
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute(f"UPDATE trades SET {field} = ? WHERE id = ?", (value, tx_id))
                conn.commit()
                conn.close()
                results.append((field, value))
            except Exception as e:
                errors.append((field, str(e)))
        
        # Spawn concurrent threads updating different fields
        threads = [
            threading.Thread(target=update_transaction, args=('amount', 2.0)),
            threading.Thread(target=update_transaction, args=('price_usd', 60000)),
            threading.Thread(target=update_transaction, args=('fee', 10.0))
        ]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify all updates succeeded
        assert len(errors) == 0, f"Concurrent updates failed: {errors}"
        assert len(results) == 3
        
        # Verify final state is consistent
        tx = db.get_transaction(tx_id)
        assert tx['amount'] == 2.0
        assert tx['price_usd'] == 60000
        assert tx['fee'] == 10.0
    
    def test_concurrent_inserts_different_records(self, tmp_path):
        """Test that concurrent inserts of different transactions succeed"""
        from src.core.database import DatabaseManager
        
        db_path = tmp_path / "test_concurrent_inserts.db"
        db = DatabaseManager(str(db_path))
        
        inserted_ids = []
        errors = []
        
        def insert_transaction(coin_index):
            try:
                tx_id = db.add_transaction({
                    'date': '2024-01-01',
                    'action': 'BUY',
                    'coin': f'COIN{coin_index}',
                    'amount': 1.0,
                    'price_usd': 100,
                    'source': 'test'
                })
                inserted_ids.append(tx_id)
            except Exception as e:
                errors.append(str(e))
        
        # Spawn 10 concurrent insert threads
        threads = [threading.Thread(target=insert_transaction, args=(i,)) for i in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All inserts should succeed
        assert len(errors) == 0, f"Concurrent inserts failed: {errors}"
        assert len(inserted_ids) == 10
        assert len(set(inserted_ids)) == 10, "All transaction IDs should be unique"
    
    def test_concurrent_read_write_consistency(self, tmp_path):
        """Test that reads during writes return consistent data"""
        from src.core.database import DatabaseManager
        
        db_path = tmp_path / "test_read_write.db"
        db = DatabaseManager(str(db_path))
        
        # Insert initial transactions
        for i in range(5):
            db.add_transaction({
                'date': '2024-01-01',
                'action': 'BUY',
                'coin': f'COIN{i}',
                'amount': 1.0,
                'price_usd': 100,
                'source': 'test'
            })
        
        read_results = []
        write_complete = threading.Event()
        
        def continuous_reader():
            """Read transaction count repeatedly"""
            while not write_complete.is_set():
                count = len(db.get_all_transactions())
                read_results.append(count)
                time.sleep(0.001)
        
        def batch_writer():
            """Write 5 more transactions"""
            for i in range(5, 10):
                db.add_transaction({
                    'date': '2024-01-01',
                    'action': 'BUY',
                    'coin': f'COIN{i}',
                    'amount': 1.0,
                    'price_usd': 100,
                    'source': 'test'
                })
                time.sleep(0.002)
            write_complete.set()
        
        reader = threading.Thread(target=continuous_reader)
        writer = threading.Thread(target=batch_writer)
        
        reader.start()
        writer.start()
        reader.join()
        writer.join()
        
        # Verify reads never saw inconsistent state
        assert all(count >= 5 and count <= 10 for count in read_results), \
            f"Read inconsistent state: {set(read_results)}"
    
    def test_database_lock_timeout_handling(self, tmp_path):
        """Test that database lock timeouts are handled gracefully"""
        from src.core.database import DatabaseManager
        
        db_path = tmp_path / "test_lock.db"
        db = DatabaseManager(str(db_path))
        
        # Start a long-running transaction that holds lock
        conn = sqlite3.connect(str(db_path))
        conn.execute("BEGIN EXCLUSIVE")
        
        # Try to write from another connection - should timeout
        db2 = DatabaseManager(str(db_path))
        with pytest.raises((sqlite3.OperationalError, TimeoutError)):
            db2.add_transaction({
                'date': '2024-01-01',
                'action': 'BUY',
                'coin': 'BTC',
                'amount': 1.0,
                'price_usd': 50000,
                'source': 'test'
            })
        
        conn.rollback()
        conn.close()


class TestLocalhostBindingVerification:
    """Test that server only binds to localhost"""
    
    def test_server_binds_only_to_localhost(self):
        """Test that web server is configured to bind only to 127.0.0.1"""
        from src.web.server import app
        
        # Check Flask config
        assert app.config.get('HOST', '127.0.0.1') == '127.0.0.1', \
            "Server should only bind to localhost"
    
    def test_server_not_accessible_from_external_ip(self):
        """Test that server cannot be accessed from external IPs"""
        # This test would require actually starting the server
        # For now, verify configuration only
        from src.web.server import app
        
        host = app.config.get('HOST', '127.0.0.1')
        assert host in ['127.0.0.1', 'localhost'], \
            f"Server is configured to bind to {host} which may allow external access"
    
    def test_no_0_0_0_0_binding(self):
        """Test that server is never configured to bind to 0.0.0.0 (all interfaces)"""
        import src.web.server as server_module
        
        # Check if there's any reference to 0.0.0.0 in the server code
        server_code = Path(server_module.__file__).read_text(encoding='utf-8')
        
        # Allow 0.0.0.0 in comments or as a warning, but not as actual binding
        dangerous_patterns = [
            "app.run(host='0.0.0.0'",
            'app.run(host="0.0.0.0"',
            "HOST = '0.0.0.0'",
            'HOST = "0.0.0.0"'
        ]
        
        for pattern in dangerous_patterns:
            assert pattern not in server_code, \
                f"Found dangerous binding pattern: {pattern}"


class TestAPIRateLimitExhaustion:
    """Test API rate limiting"""
    
    def test_rate_limit_enforced_per_endpoint(self, app_client):
        """Test that rate limits are enforced for API endpoints"""
        from src.web.server import app
        
        # Attempt 100 rapid requests to an endpoint
        responses = []
        for i in range(100):
            response = app_client.get('/api/transactions')
            responses.append(response.status_code)
        
        # Should eventually hit rate limit (429 Too Many Requests)
        assert 429 in responses, "Rate limit should be triggered after many requests"
        
        # Count how many succeeded before rate limit
        success_count = responses.index(429) if 429 in responses else len(responses)
        assert success_count < 100, "Not all requests should succeed"
    
    def test_rate_limit_resets_after_window(self, app_client):
        """Test that rate limit resets after time window"""
        from src.web.server import app
        
        # Make requests until rate limited
        for i in range(50):
            response = app_client.get('/api/transactions')
            if response.status_code == 429:
                break
        
        # Wait for rate limit window to reset (typically 60 seconds)
        time.sleep(61)
        
        # Should be able to make requests again
        response = app_client.get('/api/transactions')
        assert response.status_code != 429, "Rate limit should reset after window"
    
    def test_rate_limit_per_ip_address(self, app_client):
        """Test that rate limits are applied per IP address"""
        # This test would require mocking multiple IP addresses
        # For now, verify rate limit middleware is configured
        from src.web.server import app
        
        # Check if rate limiting middleware is present
        # This is a basic check - implementation details may vary
        middleware_present = any('limiter' in str(type(m)).lower() 
                                for m in getattr(app, 'before_request_funcs', {}).get(None, []))
        
        # If no middleware found, check for decorator usage
        if not middleware_present:
            # Look for rate limiting in route definitions
            import src.web.server as server_module
            server_code = Path(server_module.__file__).read_text(encoding='utf-8')
            assert 'rate_limit' in server_code.lower() or 'limiter' in server_code.lower(), \
                "No rate limiting implementation found"
    
    def test_rate_limit_different_endpoints_independent(self, app_client):
        """Test that rate limits for different endpoints are independent"""
        # Hit rate limit on one endpoint
        for i in range(50):
            app_client.get('/api/transactions')
        
        # Should still be able to access different endpoint
        response = app_client.get('/api/wallets')
        assert response.status_code != 429, \
            "Rate limit on one endpoint should not affect others"


@pytest.fixture
def app_client():
    """Fixture to provide Flask test client"""
    from src.web.server import app
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = True
    with app.test_client() as client:
        yield client
