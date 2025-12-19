"""
================================================================================
TEST: System Diagnostics
================================================================================

Validates system diagnostic and health check features.

Test Coverage:
    - System health checks
    - Database integrity verification
    - Configuration validation
    - Dependency checks
    - Error log analysis
    - Performance metrics

Author: robertbiv
================================================================================
"""

import os
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch

import web_server as ws


class TestDiagnostics(unittest.TestCase):
    def setUp(self):
        self.app = ws.app
        self.client = self.app.test_client()
        # Use a temp base dir to control file existence
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Patch paths used by diagnostics
        self.patches = [
            patch.object(ws, 'BASE_DIR', self.temp_dir),
            patch.object(ws, 'API_KEYS_FILE', self.temp_dir / 'api_keys.json'),
            patch.object(ws, 'API_KEYS_ENCRYPTED_FILE', self.temp_dir / 'api_keys_encrypted.json'),
            patch.object(ws, 'WALLETS_FILE', self.temp_dir / 'wallets.json'),
            patch.object(ws, 'OUTPUT_DIR', self.temp_dir / 'outputs'),
            patch.object(ws, 'DB_FILE', self.temp_dir / 'crypto_master.db'),
        ]
        for p in self.patches:
            p.start()
        
        # Ensure outputs/logs dir exists
        (self.temp_dir / 'outputs' / 'logs').mkdir(parents=True, exist_ok=True)
        
        # Simulate logged-in session with CSRF token
        with self.client.session_transaction() as sess:
            sess['username'] = 'admin'
            sess['csrf_token'] = 'test_csrf_token'
        
        # Reset DB key
        ws.app.config['DB_ENCRYPTION_KEY'] = None
    
    def tearDown(self):
        for p in self.patches:
            p.stop()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_diagnostics_reports_db_locked(self):
        resp = self.client.get('/api/diagnostics')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        ids = [i['id'] for i in data['issues']]
        self.assertIn('db_locked', ids)
    
    def test_diagnostics_reports_missing_key_files_and_certs(self):
        # Neither .db_key/.db_salt nor certs exist
        resp = self.client.get('/api/diagnostics')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        ids = [i['id'] for i in data['issues']]
        self.assertIn('missing_key_files', ids)
        self.assertIn('https_cert', ids)
    
    def test_diagnostics_reports_missing_api_keys_and_wallets(self):
        # No API keys or wallets files
        resp = self.client.get('/api/diagnostics')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        ids = [i['id'] for i in data['issues']]
        self.assertIn('api_keys_missing', ids)
        self.assertIn('wallets_missing', ids)
    
    def test_diagnostics_db_connect_failure(self):
        # Patch DB connection to raise
        with patch.object(ws, 'get_db_connection', side_effect=Exception('fail')):
            resp = self.client.get('/api/diagnostics')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            ids = [i['id'] for i in data['issues']]
            self.assertIn('db_connect', ids)
    
    def test_diagnostics_unlock_success(self):
        # Mock encryption initialize
        with patch('Crypto_Transaction_Engine.DatabaseEncryption.initialize_encryption', return_value=b'fakekey'):
            payload = {'password': 'webpw'}
            resp = self.client.post(
                '/api/diagnostics/unlock',
                data=json.dumps(payload),
                content_type='application/json',
                headers={'X-CSRF-Token': 'test_csrf_token'}
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get('success'))
            self.assertIsNotNone(ws.app.config.get('DB_ENCRYPTION_KEY'))
    
    def test_diagnostics_unlock_already_unlocked(self):
        ws.app.config['DB_ENCRYPTION_KEY'] = b'k'
        payload = {'password': 'anything'}
        resp = self.client.post(
            '/api/diagnostics/unlock',
            data=json.dumps(payload),
            content_type='application/json',
            headers={'X-CSRF-Token': 'test_csrf_token'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('already', data.get('message', '').lower())
    
    def test_diagnostics_last_returns_cached(self):
        # On startup, DIAGNOSTICS_LAST should be set; if not, the endpoint computes it
        resp = self.client.get('/api/diagnostics/last')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        # Should include timestamp and either ok or issues
        self.assertIn('timestamp', data)
        self.assertIn('ok', data)
    
    def test_diagnostics_ok_when_no_issues(self):
        # Create certs and key files
        (self.temp_dir / 'certs').mkdir(exist_ok=True)
        (self.temp_dir / 'certs' / 'server.crt').write_text('crt')
        (self.temp_dir / 'certs' / 'server.key').write_text('key')
        (self.temp_dir / '.db_key').write_bytes(b'key')
        (self.temp_dir / '.db_salt').write_bytes(b'salt')
        (self.temp_dir / 'api_keys.json').write_text('{}')
        (self.temp_dir / 'wallets.json').write_text('{}')
        ws.app.config['DB_ENCRYPTION_KEY'] = b'k'
        
        with patch.object(ws, 'get_db_connection') as mock_conn:
            mock_conn.return_value = type('C', (), {'execute': lambda *_: 1, 'close': lambda *_: None})()
            resp = self.client.get('/api/diagnostics')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get('ok'))
            self.assertEqual(len(data.get('issues', [])), 0)
    
    def test_diagnostics_returns_status_confirmations(self):
        """Test that diagnostics include positive status confirmations"""
        resp = self.client.get('/api/diagnostics')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        # Should have 'status' key
        self.assertIn('status', data)
        self.assertIsInstance(data['status'], list)
    
    def test_status_includes_db_encryption_when_key_loaded(self):
        """Test that DB encryption status appears when key is loaded"""
        ws.app.config['DB_ENCRYPTION_KEY'] = b'testkey'
        
        # Mock DB connection to avoid errors
        with patch.object(ws, 'get_db_connection') as mock_conn:
            mock_instance = type('C', (), {
                'execute': lambda *_: type('R', (), {'fetchone': lambda: ('ok',)})(),
                'close': lambda *_: None
            })()
            mock_conn.return_value = mock_instance
            
            resp = self.client.get('/api/diagnostics')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            status_ids = [s['id'] for s in data.get('status', [])]
            self.assertIn('db_encrypted', status_ids)
            
            # Verify status item structure
            db_enc_status = next((s for s in data['status'] if s['id'] == 'db_encrypted'), None)
            self.assertIsNotNone(db_enc_status)
            self.assertIn('icon', db_enc_status)
            self.assertIn('message', db_enc_status)
            self.assertIn('encryption', db_enc_status['message'].lower())
    
    def test_status_includes_https_when_cert_exists(self):
        """Test that HTTPS status appears when certificate exists"""
        (self.temp_dir / 'certs').mkdir(exist_ok=True)
        (self.temp_dir / 'certs' / 'server.crt').write_text('cert')
        (self.temp_dir / 'certs' / 'server.key').write_text('key')
        
        resp = self.client.get('/api/diagnostics')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        status_ids = [s['id'] for s in data.get('status', [])]
        self.assertIn('https_enabled', status_ids)
        
        # Verify content
        https_status = next((s for s in data['status'] if s['id'] == 'https_enabled'), None)
        self.assertIsNotNone(https_status)
        self.assertIn('HTTPS', https_status['message'])
    
    def test_status_includes_db_connected_when_db_works(self):
        """Test that DB connected status appears when connection succeeds"""
        ws.app.config['DB_ENCRYPTION_KEY'] = b'key'
        
        with patch.object(ws, 'get_db_connection') as mock_conn:
            mock_instance = type('C', (), {
                'execute': lambda *_: type('R', (), {'fetchone': lambda: ('ok',)})(),
                'close': lambda *_: None
            })()
            mock_conn.return_value = mock_instance
            
            resp = self.client.get('/api/diagnostics')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            status_ids = [s['id'] for s in data.get('status', [])]
            self.assertIn('db_connected', status_ids)
    
    def test_status_includes_schema_ok_when_integrity_passes(self):
        """Test that schema integrity status appears when check passes"""
        ws.app.config['DB_ENCRYPTION_KEY'] = b'key'
        
        with patch.object(ws, 'get_db_connection') as mock_conn:
            # Mock result object that has fetchone returning ('ok',)
            class MockResult:
                def fetchone(self):
                    return ('ok',)
            
            # Track calls
            calls = []
            
            def mock_execute(query, *args):
                calls.append(str(query))
                return MockResult()
            
            class MockConnection:
                def execute(self, query, *args):
                    return mock_execute(query, *args)
                
                def close(self):
                    pass
            
            mock_conn.return_value = MockConnection()
            
            resp = self.client.get('/api/diagnostics')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            status_ids = [s['id'] for s in data.get('status', [])]
            
            self.assertIn('schema_ok', status_ids)
            
            # Verify content
            schema_status = next((s for s in data['status'] if s['id'] == 'schema_ok'), None)
            self.assertIsNotNone(schema_status)
            self.assertIn('integrity', schema_status['message'].lower())
    
    def test_status_includes_auth_enabled_when_users_exist(self):
        """Test that authentication status appears when users file exists"""
        with patch.object(ws, 'USERS_FILE') as mock_users_file:
            mock_users_file.exists.return_value = True
            
            resp = self.client.get('/api/diagnostics')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            status_ids = [s['id'] for s in data.get('status', [])]
            self.assertIn('auth_enabled', status_ids)
    
    def test_no_db_encryption_status_when_key_not_loaded(self):
        """Test that DB encryption status does NOT appear when key is not loaded"""
        ws.app.config['DB_ENCRYPTION_KEY'] = None
        
        resp = self.client.get('/api/diagnostics')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        status_ids = [s['id'] for s in data.get('status', [])]
        self.assertNotIn('db_encrypted', status_ids)
    
    def test_no_https_status_when_cert_missing(self):
        """Test that HTTPS status does NOT appear when certificate is missing"""
        # Ensure cert directory doesn't exist
        resp = self.client.get('/api/diagnostics')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        status_ids = [s['id'] for s in data.get('status', [])]
        self.assertNotIn('https_enabled', status_ids)
    
    def test_status_all_icons_present(self):
        """Test that all status items have icons"""
        # Set up ideal conditions
        ws.app.config['DB_ENCRYPTION_KEY'] = b'key'
        (self.temp_dir / 'certs').mkdir(exist_ok=True)
        (self.temp_dir / 'certs' / 'server.crt').write_text('cert')
        (self.temp_dir / 'certs' / 'server.key').write_text('key')
        
        with patch.object(ws, 'get_db_connection') as mock_conn, \
             patch.object(ws, 'USERS_FILE') as mock_users:
            mock_instance = type('C', (), {
                'execute': lambda *_: type('R', (), {'fetchone': lambda: ('ok',)})(),
                'close': lambda *_: None
            })()
            mock_conn.return_value = mock_instance
            mock_users.exists.return_value = True
            
            resp = self.client.get('/api/diagnostics')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            
            # Verify every status item has an icon
            for status_item in data.get('status', []):
                self.assertIn('icon', status_item)
                self.assertIsInstance(status_item['icon'], str)
                self.assertGreater(len(status_item['icon']), 0)


if __name__ == '__main__':
    unittest.main()


