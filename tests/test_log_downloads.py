"""Tests for log download functionality"""
import unittest
import json
import tempfile
import zipfile
import io
from pathlib import Path
import sys

parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

import web_server as ws


class TestLogDownloads(unittest.TestCase):
    """Test log download endpoints"""
    
    def setUp(self):
        """Set up test client"""
        self.tmpdir = Path(tempfile.mkdtemp())
        ws.USERS_FILE = self.tmpdir / 'web_users.json'
        ws.OUTPUT_DIR = self.tmpdir / 'outputs'
        ws.DB_FILE = self.tmpdir / 'crypto_master.db'
        
        # Create logs directory with sample logs
        log_dir = ws.OUTPUT_DIR / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Sample log with sensitive data
        self.sample_log1 = log_dir / 'app.log'
        self.sample_log1.write_text("""
2024-01-01 10:00:00 - INFO - Starting application
2024-01-01 10:00:01 - INFO - User testuser logged in from 192.168.1.100
2024-01-01 10:00:02 - INFO - Processing wallet 0x742d35Cc6634C0532925a3b844Bc9e7595f0bEbA
2024-01-01 10:00:03 - INFO - API key configured: sk_live_abc123def456ghi789
2024-01-01 10:00:04 - INFO - Bitcoin address: 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa
2024-01-01 10:00:05 - INFO - User email: user@example.com
2024-01-01 10:00:06 - ERROR - Database error occurred
""")
        
        # Another sample log
        self.sample_log2 = log_dir / 'sync.log'
        self.sample_log2.write_text("""
2024-01-01 11:00:00 - INFO - Sync started
2024-01-01 11:00:01 - INFO - Fetching data from exchange
2024-01-01 11:00:02 - INFO - Sync completed successfully
""")
        
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
    
    def test_download_all_logs(self):
        """Test downloading all logs as zip"""
        response = self.client.get('/api/logs/download-all')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/zip')
        
        # Verify zip contains both log files
        zip_data = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_data, 'r') as zf:
            names = zf.namelist()
            self.assertIn('app.log', names)
            self.assertIn('sync.log', names)
            
            # Verify content is unchanged
            app_content = zf.read('app.log').decode('utf-8')
            self.assertIn('0x742d35Cc6634C0532925a3b844Bc9e7595f0bEbA', app_content)
            self.assertIn('192.168.1.100', app_content)
    
    def test_download_redacted_logs(self):
        """Test downloading redacted logs"""
        response = self.client.get('/api/logs/download-redacted')
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/zip')
        
        # Verify zip contains redacted log files
        zip_data = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_data, 'r') as zf:
            names = zf.namelist()
            self.assertIn('redacted_app.log', names)
            self.assertIn('redacted_sync.log', names)
            
            # Verify sensitive data is redacted
            app_content = zf.read('redacted_app.log').decode('utf-8')
            self.assertNotIn('0x742d35Cc6634C0532925a3b844Bc9e7595f0bEbA', app_content)
            self.assertNotIn('192.168.1.100', app_content)
            self.assertNotIn('user@example.com', app_content)
            self.assertNotIn('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa', app_content)
            self.assertNotIn('sk_live_abc123def456ghi789', app_content)
            
            # Verify non-sensitive data is kept
            self.assertIn('Starting application', app_content)
            self.assertIn('Database error occurred', app_content)
            
            # Verify redaction markers are present
            self.assertIn('[WALLET_ADDRESS]', app_content)
            self.assertIn('[IP_REDACTED]', app_content)
            self.assertIn('[EMAIL_REDACTED]', app_content)
    
    def test_download_all_logs_no_logs(self):
        """Test downloading when no logs exist"""
        # Remove logs directory
        import shutil
        shutil.rmtree(ws.OUTPUT_DIR / 'logs')
        
        response = self.client.get('/api/logs/download-all')
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertIn('error', data)
    
    def test_redacted_logs_preserves_structure(self):
        """Test that redacted logs preserve line structure"""
        response = self.client.get('/api/logs/download-redacted')
        
        zip_data = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_data, 'r') as zf:
            app_content = zf.read('redacted_app.log').decode('utf-8')
            lines = app_content.strip().split('\n')
            
            # Should have same number of lines as original
            original_lines = self.sample_log1.read_text().strip().split('\n')
            self.assertEqual(len(lines), len(original_lines))
    
    def test_download_requires_authentication(self):
        """Test that log downloads require authentication"""
        # Create new client without login
        client = ws.app.test_client()
        
        response = client.get('/api/logs/download-all')
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
        response = client.get('/api/logs/download-redacted')
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def tearDown(self):
        """Clean up"""
        import shutil
        shutil.rmtree(self.tmpdir)


if __name__ == '__main__':
    unittest.main()


