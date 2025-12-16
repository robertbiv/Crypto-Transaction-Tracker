import unittest
import sys
import os
import json
import tempfile
import shutil
import zipfile
import io
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import hashlib
import hmac

# Import the app
from web_server import app

class TestFactoryResetAndBackup(unittest.TestCase):
    
    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        
        # Define test paths
        self.db_file = self.test_path / 'test_crypto_master.db'
        self.config_file = self.test_path / 'test_config.json'
        self.api_keys_file = self.test_path / 'test_api_keys.json'
        self.wallets_file = self.test_path / 'test_wallets.json'
        self.users_file = self.test_path / 'test_users.json'
        
        self.upload_folder = self.test_path / 'inputs'
        self.output_dir = self.test_path / 'outputs'
        self.archive_dir = self.test_path / 'processed_archive'
        
        # Create directories
        self.upload_folder.mkdir()
        self.output_dir.mkdir()
        self.archive_dir.mkdir()
        
        # Create dummy files
        self.config_file.write_text('{"test": "config"}')
        self.api_keys_file.write_text('{"test": "keys"}')
        self.wallets_file.write_text('{"test": "wallets"}')
        self.users_file.write_text('{"test": "users"}')
        (self.upload_folder / 'test.csv').write_text('test data')
        
        # Initialize test DB
        self.conn = sqlite3.connect(str(self.db_file))
        self.conn.execute('''CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY, date TEXT, source TEXT, destination TEXT,
            action TEXT, coin TEXT, amount TEXT, price_usd TEXT, fee TEXT, fee_coin TEXT, batch_id TEXT
        )''')
        self.conn.execute("INSERT INTO trades (id, coin, amount) VALUES ('1', 'BTC', '1.0')")
        self.conn.commit()
        self.conn.close()
        
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret_key'
        self.client = app.test_client()
        
        # Patches
        self.patches = []
        self.patches.append(patch('web_server.DB_FILE', self.db_file))
        self.patches.append(patch('web_server.CONFIG_FILE', self.config_file))
        self.patches.append(patch('web_server.API_KEYS_FILE', self.api_keys_file))
        self.patches.append(patch('web_server.WALLETS_FILE', self.wallets_file))
        self.patches.append(patch('web_server.USERS_FILE', self.users_file))
        self.patches.append(patch('web_server.UPLOAD_FOLDER', self.upload_folder))
        self.patches.append(patch('web_server.OUTPUT_DIR', self.output_dir))
        # Patching BASE_DIR is tricky because it's used to derive others, but we can patch the specific usage in factory_reset
        # Instead, let's patch the list of folders in the factory_reset function if possible, or just patch BASE_DIR
        # But BASE_DIR is used for imports etc.
        # Let's look at how factory_reset uses BASE_DIR: BASE_DIR / 'processed_archive'
        # We can patch web_server.BASE_DIR, but it might break other things.
        # Better to patch the specific path for archive
        # Actually, in factory_reset: for folder in [UPLOAD_FOLDER, OUTPUT_DIR, BASE_DIR / 'processed_archive']:
        # We can't easily patch that expression.
        # However, we can patch shutil.rmtree and os.remove to verify they are called with correct paths, 
        # OR we can try to patch BASE_DIR just for the duration of the test.
        
        # Let's try patching BASE_DIR.
        self.patches.append(patch('web_server.BASE_DIR', self.test_path))
        
        for p in self.patches:
            p.start()
            
    def tearDown(self):
        """Clean up test environment"""
        for p in self.patches:
            p.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def login(self):
        """Simulate login"""
        with self.client.session_transaction() as sess:
            sess['username'] = 'admin'
            sess['csrf_token'] = 'test_csrf_token'

    def generate_test_signature(self, data, timestamp, username):
        """Generate signature for testing"""
        message = f"{json.dumps(data, sort_keys=True)}:{timestamp}:{username}"
        signature = hmac.new(
            b'test_secret_key',
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def test_backup_full_csv_export(self):
        """Test that full backup returns a ZIP with CSV export of trades"""
        self.login()
        
        response = self.client.get('/api/backup/full', headers={'X-CSRF-Token': 'test_csrf_token'})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'application/zip')
        
        # Verify ZIP content
        with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
            file_list = zf.namelist()
            self.assertIn('trades_export.csv', file_list)
            
            # Verify CSV content
            csv_content = zf.read('trades_export.csv').decode('utf-8')
            self.assertIn('id,date,source', csv_content) # Header
            self.assertIn('1,,,,,BTC,1.0,,,,', csv_content) # Data row (commas might vary based on empty fields)
            
            # Verify config files are NOT included
            self.assertNotIn('test_config.json', file_list)
            self.assertNotIn('test_api_keys.json', file_list)

    def test_factory_reset(self):
        """Test factory reset deletes all data"""
        self.login()
        
        # Prepare headers for secure API
        timestamp = datetime.now(timezone.utc).isoformat()
        data = {}
        signature = self.generate_test_signature(data, timestamp, 'admin')
        
        headers = {
            'X-CSRF-Token': 'test_csrf_token',
            'X-Request-Timestamp': timestamp,
            'X-Request-Signature': signature,
            'Content-Type': 'application/json'
        }
        
        # Verify files exist before reset
        self.assertTrue(self.db_file.exists())
        self.assertTrue(self.config_file.exists())
        self.assertTrue((self.upload_folder / 'test.csv').exists())
        
        # Call reset
        response = self.client.post('/api/reset/factory', headers=headers, json=data)
        
        self.assertEqual(response.status_code, 200)
        result = json.loads(response.data)
        self.assertTrue(result['success'])
        
        # Verify files are deleted
        # DB file is recreated by init_db(), so check it's empty
        self.assertTrue(self.db_file.exists())
        conn = sqlite3.connect(str(self.db_file))
        cursor = conn.execute("SELECT count(*) FROM trades")
        count = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(count, 0)
        
        self.assertFalse(self.config_file.exists())
        self.assertFalse(self.api_keys_file.exists())
        self.assertFalse(self.wallets_file.exists())
        self.assertFalse(self.users_file.exists())
        
        # Verify directories are cleared (but exist)
        self.assertTrue(self.upload_folder.exists())
        self.assertFalse((self.upload_folder / 'test.csv').exists())
        
        # Verify session is cleared
        with self.client.session_transaction() as sess:
            self.assertNotIn('username', sess)

if __name__ == '__main__':
    unittest.main()


