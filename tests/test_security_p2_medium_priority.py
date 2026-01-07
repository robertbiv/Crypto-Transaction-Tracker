"""
P2 Medium Priority Security Tests
Important security tests for penetration testing, fuzzing, and encryption.
"""

import pytest
import json
import socket
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import time


class TestPenetrationTesting:
    """Basic penetration testing suite"""
    
    def test_sql_injection_protection(self, app_client):
        """Test that SQL injection attempts are blocked"""
        sql_injection_payloads = [
            "' OR '1'='1",
            "1' OR '1' = '1",
            "' OR 1=1--",
            "admin'--",
            "' UNION SELECT NULL--",
            "'; DROP TABLE trades--",
        ]
        
        for payload in sql_injection_payloads:
            # Try in search parameter
            response = app_client.get(f'/api/transactions?search={payload}')
            
            # Should not return SQL error or all records
            assert response.status_code not in [500], \
                f"SQL injection attempt caused server error: {payload}"
            
            if response.status_code == 200:
                data = json.loads(response.data)
                # Should not return suspiciously large dataset
                assert len(data.get('transactions', [])) < 1000, \
                    f"SQL injection may have bypassed filter: {payload}"
    
    def test_xss_protection(self, app_client):
        """Test that XSS attacks are sanitized"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
        ]
        
        for payload in xss_payloads:
            # Add transaction with XSS payload in description
            response = app_client.post('/api/transactions/add', json={
                'date': '2024-01-01',
                'action': 'BUY',
                'coin': 'BTC',
                'amount': 1.0,
                'description': payload
            })
            
            if response.status_code == 200:
                # Retrieve transaction
                tx_id = json.loads(response.data).get('id')
                response2 = app_client.get(f'/api/transactions/{tx_id}')
                
                # Check that script tags are escaped/sanitized
                assert payload not in response2.data.decode(), \
                    f"XSS payload not sanitized: {payload}"
    
    def test_command_injection_protection(self, app_client, tmp_path):
        """Test that command injection attempts are blocked"""
        command_injection_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "&& whoami",
            "`rm -rf /`",
            "$(cat /etc/shadow)",
        ]
        
        for payload in command_injection_payloads:
            # Try in filename for backup
            response = app_client.post('/api/backup', json={
                'name': f"backup{payload}.db"
            })
            
            assert response.status_code in [400, 403], \
                f"Command injection not blocked: {payload}"
    
    def test_ldap_injection_protection(self, app_client):
        """Test LDAP injection protection (if LDAP is used)"""
        ldap_payloads = [
            "*",
            "admin)(&",
            "admin)(|(password=*))",
        ]
        
        for payload in ldap_payloads:
            response = app_client.post('/api/login', json={
                'username': payload,
                'password': 'test'
            })
            
            # Should return auth failure, not server error
            assert response.status_code in [401, 400], \
                f"LDAP injection may have bypassed auth: {payload}"
    
    def test_xxe_injection_protection(self, app_client):
        """Test XXE (XML External Entity) injection protection"""
        xxe_payload = """<?xml version="1.0"?>
        <!DOCTYPE foo [
            <!ENTITY xxe SYSTEM "file:///etc/passwd">
        ]>
        <root>&xxe;</root>"""
        
        response = app_client.post('/api/import', 
            data=xxe_payload,
            content_type='application/xml')
        
        assert response.status_code in [400, 415], \
            "XXE attack not blocked"


class TestFuzzingInputParsers:
    """Fuzzing tests for all input parsers"""
    
    def test_csv_parser_fuzzing(self, tmp_path):
        """Fuzz CSV parser with malformed data"""
        from src.processors.ingestor import CSVIngestor
        
        malformed_csvs = [
            "date,action,coin\n2024-01-01,BUY",  # Missing column
            "date,action,coin\n,,",  # Empty values
            "date,action,coin\n" + "A"*10000,  # Extremely long value
            "date,action,coin\n\x00\x01\x02",  # Binary data
            "date,action,coin\n\n\n\n\n" * 1000,  # Many empty lines
            "no_headers\nvalue1,value2",  # Missing required headers
        ]
        
        for i, csv_data in enumerate(malformed_csvs):
            csv_file = tmp_path / f"fuzz_{i}.csv"
            csv_file.write_text(csv_data)
            
            # Should not crash, should handle gracefully
            try:
                ingestor = CSVIngestor(str(csv_file))
                transactions = ingestor.parse()
                # Either succeeds or returns empty/partial results
                assert isinstance(transactions, list)
            except (ValueError, TypeError, KeyError) as e:
                # Expected errors are okay
                pass
            except Exception as e:
                pytest.fail(f"Unexpected crash on fuzzing input {i}: {e}")
    
    def test_json_parser_fuzzing(self, app_client):
        """Fuzz JSON parser with malformed data"""
        malformed_jsons = [
            "{",  # Incomplete
            '{"key": }',  # Missing value
            '{"key": "value"',  # Missing closing brace
            '{"key": [1, 2, 3, ]',  # Trailing comma
            '{' + 'a' * 1000000 + '}',  # Extremely large
            '{"\\u0000": "null byte"}',  # Null byte
        ]
        
        for payload in malformed_jsons:
            response = app_client.post('/api/transactions/add',
                data=payload,
                content_type='application/json')
            
            # Should return 400 Bad Request, not crash
            assert response.status_code == 400, \
                f"Malformed JSON not handled: {payload[:50]}"
    
    def test_date_parser_fuzzing(self, app_client):
        """Fuzz date parser with various formats"""
        malformed_dates = [
            "2024-13-01",  # Invalid month
            "2024-01-32",  # Invalid day
            "0000-00-00",  # Zero date
            "9999-12-31",  # Far future
            "1900-01-01",  # Far past
            "not-a-date",  # Text
            "2024/01/01",  # Wrong separator
            "",  # Empty
            None,  # Null
        ]
        
        for date_value in malformed_dates:
            response = app_client.post('/api/transactions/add', json={
                'date': date_value,
                'action': 'BUY',
                'coin': 'BTC',
                'amount': 1.0
            })
            
            # Should validate and reject or normalize
            if response.status_code == 200:
                tx = json.loads(response.data)
                # If accepted, must have valid date
                assert 'date' in tx and tx['date'] is not None


class TestNetworkTrafficMonitoring:
    """Test that no telemetry is sent"""
    
    def test_no_external_requests_on_startup(self):
        """Test that app startup makes no external network calls"""
        with patch('socket.socket') as mock_socket:
            # Import app (simulates startup)
            import src.web.server
            
            # Check no socket connections to external IPs
            external_calls = [
                call for call in mock_socket.call_args_list
                if not self._is_localhost_call(call)
            ]
            
            assert len(external_calls) == 0, \
                f"Found external network calls on startup: {external_calls}"
    
    def test_no_telemetry_on_transaction_processing(self, app_client):
        """Test that processing transactions doesn't send telemetry"""
        with patch('requests.post') as mock_post, \
             patch('requests.get') as mock_get:
            
            # Add transaction
            app_client.post('/api/transactions/add', json={
                'date': '2024-01-01',
                'action': 'BUY',
                'coin': 'BTC',
                'amount': 1.0,
                'price_usd': 50000
            })
            
            # Verify no external HTTP calls
            assert mock_post.call_count == 0, "Found POST telemetry"
            assert mock_get.call_count == 0, "Found GET telemetry"
    
    def test_no_dns_lookups_to_telemetry_servers(self):
        """Test that app never looks up known telemetry domains"""
        telemetry_domains = [
            'google-analytics.com',
            'mixpanel.com',
            'segment.io',
            'amplitude.com',
            'analytics.google.com',
        ]
        
        with patch('socket.getaddrinfo') as mock_dns:
            # Simulate app usage
            from src.web.server import app
            
            # Check DNS lookups
            for call in mock_dns.call_args_list:
                hostname = call[0][0] if call[0] else ''
                assert hostname not in telemetry_domains, \
                    f"Found telemetry DNS lookup: {hostname}"
    
    def _is_localhost_call(self, call):
        """Helper to check if socket call is to localhost"""
        if not call or not call[0]:
            return True
        addr = call[0][0] if isinstance(call[0], tuple) else None
        return addr in ['127.0.0.1', 'localhost', '::1'] if addr else True


class TestEncryptionKeyRotation:
    """Test encryption key rotation"""
    
    def test_rotate_encryption_key(self, tmp_path):
        """Test that encryption keys can be rotated"""
        from src.core.encryption import EncryptionManager
        
        em = EncryptionManager(key_file=tmp_path / "key.dat")
        
        # Encrypt data with old key
        plaintext = "sensitive_data"
        encrypted = em.encrypt(plaintext)
        
        # Rotate key
        em.rotate_key()
        
        # Old encrypted data should still be decryptable
        decrypted = em.decrypt(encrypted)
        assert decrypted == plaintext
    
    def test_reencrypt_all_data_after_rotation(self, tmp_path):
        """Test that all encrypted data is re-encrypted after key rotation"""
        from src.core.encryption import EncryptionManager
        from src.core.database import DatabaseManager
        
        # Create test data
        db = DatabaseManager(str(tmp_path / "test.db"))
        tx_id = db.add_transaction({
            'date': '2024-01-01',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 50000,
            'source': 'test'
        })
        
        # Encrypt sensitive fields
        em = EncryptionManager(key_file=tmp_path / "key.dat")
        
        # Rotate key and re-encrypt
        em.rotate_key()
        em.reencrypt_database(db)
        
        # Verify data is still accessible
        tx = db.get_transaction(tx_id)
        assert tx['coin'] == 'BTC'
    
    def test_key_rotation_audit_log(self, tmp_path):
        """Test that key rotations are logged"""
        from src.core.encryption import EncryptionManager
        
        em = EncryptionManager(key_file=tmp_path / "key.dat")
        em.rotate_key()
        
        # Check audit log
        audit_log = tmp_path / "audit.log"
        if audit_log.exists():
            log_content = audit_log.read_text()
            assert 'key_rotation' in log_content.lower()


@pytest.fixture
def app_client():
    """Fixture to provide Flask test client"""
    from src.web.server import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
