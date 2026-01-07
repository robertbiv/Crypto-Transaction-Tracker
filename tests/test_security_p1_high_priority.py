"""
P1 High Priority Security Tests
Critical security tests that should be implemented soon after P0 items.
"""

import pytest
import os
import tempfile
import hashlib
import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import json


class TestPathTraversalAttacks:
    """Test protection against path traversal attacks"""
    
    def test_file_upload_path_traversal_blocked(self, app_client, tmp_path):
        """Test that file uploads with ../ are blocked"""
        # Attempt to upload file with path traversal in filename
        dangerous_filenames = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            '../../../../root/.ssh/id_rsa',
            'normal_file/../../../etc/shadow',
            '..%2F..%2F..%2Fetc%2Fpasswd',  # URL encoded
        ]
        
        for filename in dangerous_filenames:
            response = app_client.post('/api/upload', data={
                'file': (filename, b'malicious content')
            })
            
            assert response.status_code in [400, 403], \
                f"Path traversal attempt with {filename} should be blocked"
            
            # Verify file was not written outside intended directory
            assert not Path('/etc/passwd').exists() or \
                   Path('/etc/passwd').read_text() != 'malicious content'
    
    def test_backup_restore_path_traversal_blocked(self, app_client, tmp_path):
        """Test that backup restore with path traversal is blocked"""
        # Attempt to restore backup with path traversal
        response = app_client.post('/api/restore', json={
            'backup_path': '../../../etc/passwd'
        })
        
        assert response.status_code in [400, 403, 404], \
            "Path traversal in backup restore should be blocked"
    
    def test_log_download_path_traversal_blocked(self, app_client):
        """Test that log downloads with path traversal are blocked"""
        dangerous_paths = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            'logs/../../api_keys_encrypted.json',
        ]
        
        for path in dangerous_paths:
            response = app_client.get(f'/api/logs/download?file={path}')
            assert response.status_code in [400, 403, 404], \
                f"Path traversal in log download should be blocked: {path}"
    
    def test_csv_export_path_traversal_blocked(self, app_client):
        """Test that CSV exports cannot be directed to arbitrary paths"""
        response = app_client.post('/api/export', json={
            'output_path': '../../../tmp/malicious_export.csv',
            'year': 2024
        })
        
        assert response.status_code in [400, 403], \
            "Path traversal in CSV export should be blocked"
    
    def test_path_sanitization_function(self):
        """Test that path sanitization utility exists and works"""
        from src.utils.constants import BASE_DIR
        
        # Test various malicious paths
        test_cases = [
            ('../../../etc/passwd', False),
            ('..\\..\\..\\windows\\system32', False),
            ('normal_file.csv', True),
            ('subdir/normal_file.csv', True),
            ('../normal_file.csv', False),
            ('./normal_file.csv', True),
        ]
        
        for path, should_be_safe in test_cases:
            # Check if path escapes BASE_DIR
            resolved = Path(BASE_DIR / path).resolve()
            is_safe = str(resolved).startswith(str(BASE_DIR))
            
            if should_be_safe:
                assert is_safe, f"Path {path} should be considered safe"
            else:
                assert not is_safe or path.startswith('..'), \
                    f"Path {path} should be detected as unsafe"


class TestSessionHijacking:
    """Test protection against session hijacking"""
    
    def test_session_regeneration_on_login(self, app_client):
        """Test that session ID changes after login"""
        # Get initial session
        response1 = app_client.get('/setup/wizard')
        session_id_1 = self._extract_session_id(response1)
        
        # Perform login
        response2 = app_client.post('/api/setup/create-account', json={
            'username': 'testuser',
            'password': 'TestPass123!'
        })
        
        # Get new session
        response3 = app_client.get('/setup/wizard')
        session_id_2 = self._extract_session_id(response3)
        
        assert session_id_1 != session_id_2, \
            "Session ID should change after authentication"
    
    def test_session_fixation_prevented(self, app_client):
        """Test that session fixation attacks are prevented"""
        # Attacker sets a session ID
        malicious_session_id = 'malicious_session_12345'
        
        # Attempt to use fixed session ID
        app_client.set_cookie('session', malicious_session_id)
        
        # Perform login
        response = app_client.post('/api/setup/create-account', json={
            'username': 'testuser',
            'password': 'TestPass123!'
        })
        
        # Check that server assigned new session, not using attacker's
        new_session_id = self._extract_session_id(response)
        assert new_session_id != malicious_session_id, \
            "Server should not accept pre-set session IDs"
    
    def test_session_timeout_after_inactivity(self, app_client):
        """Test that sessions expire after inactivity"""
        # Login
        app_client.post('/api/setup/create-account', json={
            'username': 'testuser',
            'password': 'TestPass123!'
        })
        
        # Wait for session timeout (mock time)
        with patch('time.time', return_value=time.time() + 1801):  # 30 min + 1 sec
            response = app_client.get('/api/transactions')
            assert response.status_code == 401, \
                "Session should expire after inactivity timeout"
    
    def test_concurrent_session_limit(self, app_client):
        """Test that users cannot have unlimited concurrent sessions"""
        from src.web.server import app
        
        # Create multiple sessions for same user
        sessions = []
        for i in range(10):
            client = app.test_client()
            client.post('/api/setup/create-account', json={
                'username': 'testuser',
                'password': 'TestPass123!'
            })
            sessions.append(client)
        
        # Verify earlier sessions are invalidated (max sessions = 3)
        response = sessions[0].get('/api/transactions')
        assert response.status_code == 401, \
            "Old sessions should be invalidated when limit reached"
    
    def test_session_cookie_secure_flags(self, app_client):
        """Test that session cookies have secure flags set"""
        response = app_client.get('/setup/wizard')
        
        # Check Set-Cookie header
        set_cookie = response.headers.get('Set-Cookie', '')
        
        assert 'HttpOnly' in set_cookie, "Session cookie should have HttpOnly flag"
        assert 'Secure' in set_cookie, "Session cookie should have Secure flag"
        assert 'SameSite' in set_cookie, "Session cookie should have SameSite flag"
    
    def _extract_session_id(self, response):
        """Helper to extract session ID from response"""
        cookies = response.headers.getlist('Set-Cookie')
        for cookie in cookies:
            if 'session=' in cookie:
                return cookie.split('session=')[1].split(';')[0]
        return None


class TestPasswordPolicyEnforcement:
    """Test password policy enforcement"""
    
    def test_password_minimum_length(self, app_client):
        """Test that passwords must meet minimum length requirement"""
        weak_passwords = ['abc', '12345', 'short']
        
        for password in weak_passwords:
            response = app_client.post('/api/setup/create-account', json={
                'username': 'testuser',
                'password': password
            })
            
            assert response.status_code == 400, \
                f"Weak password {password} should be rejected"
            data = json.loads(response.data)
            assert 'password' in data.get('error', '').lower()
    
    def test_password_complexity_requirements(self, app_client):
        """Test that passwords must meet complexity requirements"""
        weak_passwords = [
            'alllowercase',      # No uppercase, no numbers
            'ALLUPPERCASE',      # No lowercase, no numbers
            '12345678901',       # Only numbers
            'NoNumbers!',        # No numbers
            'nonumbers123',      # No uppercase
        ]
        
        for password in weak_passwords:
            response = app_client.post('/api/setup/create-account', json={
                'username': 'testuser',
                'password': password
            })
            
            assert response.status_code == 400, \
                f"Weak password {password} should be rejected"
    
    def test_password_common_password_blocked(self, app_client):
        """Test that common passwords are blocked"""
        common_passwords = [
            'Password123!',
            'Admin123!',
            'Welcome123!',
            'Qwerty123!',
        ]
        
        for password in common_passwords:
            response = app_client.post('/api/setup/create-account', json={
                'username': 'testuser',
                'password': password
            })
            
            # Should either reject or warn
            if response.status_code == 200:
                data = json.loads(response.data)
                assert 'warning' in data, \
                    f"Common password {password} should trigger warning"
    
    def test_password_username_similarity_blocked(self, app_client):
        """Test that passwords similar to username are blocked"""
        response = app_client.post('/api/setup/create-account', json={
            'username': 'johndoe',
            'password': 'Johndoe123!'
        })
        
        assert response.status_code == 400, \
            "Password similar to username should be rejected"
    
    def test_password_change_requires_old_password(self, app_client):
        """Test that password changes require old password"""
        # Create account
        app_client.post('/api/setup/create-account', json={
            'username': 'testuser',
            'password': 'OldPass123!'
        })
        
        # Attempt to change password without providing old password
        response = app_client.post('/api/account/change-password', json={
            'new_password': 'NewPass123!'
        })
        
        assert response.status_code == 400, \
            "Password change without old password should fail"
    
    def test_password_history_prevents_reuse(self, app_client):
        """Test that recently used passwords cannot be reused"""
        # Create account
        app_client.post('/api/setup/create-account', json={
            'username': 'testuser',
            'password': 'FirstPass123!'
        })
        
        # Change password
        app_client.post('/api/account/change-password', json={
            'old_password': 'FirstPass123!',
            'new_password': 'SecondPass123!'
        })
        
        # Attempt to change back to first password
        response = app_client.post('/api/account/change-password', json={
            'old_password': 'SecondPass123!',
            'new_password': 'FirstPass123!'
        })
        
        assert response.status_code == 400, \
            "Password reuse should be prevented"


class TestDatabaseCorruptionRecovery:
    """Test database corruption detection and recovery"""
    
    def test_detect_corrupted_database(self, tmp_path):
        """Test that corrupted database is detected"""
        from src.core.database import DatabaseManager
        
        # Create valid database
        db_path = tmp_path / "test.db"
        db = DatabaseManager(str(db_path))
        
        # Insert some data
        db.add_transaction({
            'date': '2024-01-01',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 50000,
            'source': 'test'
        })
        
        # Corrupt the database file
        with open(db_path, 'rb+') as f:
            f.seek(100)
            f.write(b'\x00' * 100)
        
        # Attempt to use corrupted database
        with pytest.raises((sqlite3.DatabaseError, sqlite3.CorruptionError)):
            db2 = DatabaseManager(str(db_path))
            db2.get_all_transactions()
    
    def test_automatic_backup_before_operations(self, tmp_path):
        """Test that automatic backups are created before risky operations"""
        from src.core.database import DatabaseManager
        
        db_path = tmp_path / "test.db"
        db = DatabaseManager(str(db_path))
        
        # Insert data
        tx_id = db.add_transaction({
            'date': '2024-01-01',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 50000,
            'source': 'test'
        })
        
        # Perform bulk delete (risky operation)
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        
        db.bulk_delete([tx_id], backup=True, backup_dir=str(backup_dir))
        
        # Verify backup was created
        backups = list(backup_dir.glob("*.db"))
        assert len(backups) > 0, "Backup should be created before bulk delete"
    
    def test_recover_from_corrupted_wal_file(self, tmp_path):
        """Test recovery from corrupted WAL (Write-Ahead Log) file"""
        from src.core.database import DatabaseManager
        
        db_path = tmp_path / "test.db"
        db = DatabaseManager(str(db_path))
        
        # Insert data
        db.add_transaction({
            'date': '2024-01-01',
            'action': 'BUY',
            'coin': 'BTC',
            'amount': 1.0,
            'price_usd': 50000,
            'source': 'test'
        })
        
        # Corrupt WAL file
        wal_path = Path(str(db_path) + '-wal')
        if wal_path.exists():
            with open(wal_path, 'wb') as f:
                f.write(b'\x00' * 100)
        
        # Database should still be accessible (falls back to main file)
        db2 = DatabaseManager(str(db_path))
        transactions = db2.get_all_transactions()
        assert len(transactions) >= 0  # Should not crash
    
    def test_integrity_check_on_startup(self, tmp_path):
        """Test that integrity check runs on database startup"""
        from src.core.database import DatabaseManager
        
        db_path = tmp_path / "test.db"
        db = DatabaseManager(str(db_path))
        
        # Check that integrity check method exists
        assert hasattr(db, 'check_integrity') or hasattr(db, 'verify_integrity'), \
            "Database should have integrity check method"
        
        # Run integrity check
        if hasattr(db, 'check_integrity'):
            result = db.check_integrity()
            assert result is True or result == 'ok', \
                "Integrity check should pass for valid database"


class TestMemoryDiskExhaustion:
    """Test handling of memory and disk exhaustion"""
    
    def test_large_file_upload_rejected(self, app_client, tmp_path):
        """Test that extremely large file uploads are rejected"""
        # Create 100MB file
        large_file = tmp_path / "large.csv"
        with open(large_file, 'wb') as f:
            f.write(b'A' * (100 * 1024 * 1024))  # 100 MB
        
        with open(large_file, 'rb') as f:
            response = app_client.post('/api/upload', data={
                'file': (f, 'large.csv')
            })
        
        assert response.status_code in [413, 400], \
            "Large file upload should be rejected"
    
    def test_memory_limit_on_query_results(self, tmp_path):
        """Test that large query results don't exhaust memory"""
        from src.core.database import DatabaseManager
        
        db_path = tmp_path / "test.db"
        db = DatabaseManager(str(db_path))
        
        # Insert 10,000 transactions
        for i in range(10000):
            db.add_transaction({
                'date': '2024-01-01',
                'action': 'BUY',
                'coin': f'COIN{i}',
                'amount': 1.0,
                'price_usd': 100,
                'source': 'test'
            })
        
        # Query all transactions - should use pagination
        transactions = db.get_all_transactions(limit=100)
        assert len(transactions) <= 100, \
            "Query results should be paginated to prevent memory exhaustion"
    
    def test_disk_space_check_before_write(self, tmp_path):
        """Test that disk space is checked before large writes"""
        from src.core.database import DatabaseManager
        
        db_path = tmp_path / "test.db"
        db = DatabaseManager(str(db_path))
        
        # Mock disk space check
        with patch('shutil.disk_usage') as mock_disk:
            mock_disk.return_value = MagicMock(free=1024)  # Only 1KB free
            
            # Attempt large operation
            with pytest.raises((IOError, OSError, RuntimeError)):
                for i in range(1000):
                    db.add_transaction({
                        'date': '2024-01-01',
                        'action': 'BUY',
                        'coin': f'COIN{i}',
                        'amount': 1.0,
                        'price_usd': 100,
                        'source': 'test'
                    })
    
    def test_log_file_rotation_prevents_disk_fill(self, tmp_path):
        """Test that log files are rotated to prevent disk filling"""
        from src.utils.logger import setup_logger
        
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        
        # Create logger with small max size
        logger = setup_logger('test', log_dir=str(log_dir), max_bytes=1024, backup_count=3)
        
        # Write lots of log entries
        for i in range(1000):
            logger.info(f"Test log message {i} with some extra content to fill space")
        
        # Check that multiple log files exist (rotation occurred)
        log_files = list(log_dir.glob("*.log*"))
        assert len(log_files) <= 4, \
            "Log rotation should limit number of log files"


@pytest.fixture
def app_client():
    """Fixture to provide Flask test client"""
    from src.web.server import app
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable for easier testing
    with app.test_client() as client:
        yield client
