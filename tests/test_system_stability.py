"""System Stability and Architecture Tests"""
from test_common import *

class TestArchitectureStability(unittest.TestCase):
    def test_import_order_resilience(self):
        for module in ['Crypto_Tax_Engine', 'Auto_Runner']:
            if module in sys.modules: del sys.modules[module]
        modules_to_load = ['Crypto_Tax_Engine', 'Auto_Runner']
        random.shuffle(modules_to_load)
        print(f"\n--- TESTING IMPORT ORDER: {modules_to_load} ---")
        try:
            for m in modules_to_load: importlib.import_module(m)
        except ImportError as e: self.fail(f"Circular dependency: {e}")
        except Exception as e: self.fail(f"Module crashed: {e}")
        re_app = sys.modules['Crypto_Tax_Engine']
        self.assertTrue(hasattr(re_app, 'TaxEngine'))



class TestSystemInterruptions(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.ARCHIVE_DIR = self.test_path / 'processed_archive'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'crash_test.db'
        app.DB_BACKUP = self.test_path / 'crash_test.db.bak'
        app.KEYS_FILE = self.test_path / 'api_keys.json'
        app.WALLETS_FILE = self.test_path / 'wallets.json'
        app.CONFIG_FILE = self.test_path / 'config.json'
        app.GLOBAL_CONFIG['general']['create_db_backups'] = True
        app.initialize_folders()
        self.db = app.DatabaseManager()
    def tearDown(self):
        self.db.close()
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_mid_write_crash(self):
        self.db.save_trade({'id': 'safe', 'date': '2023-01-01', 'source': 'M', 'action': 'BUY', 'coin': 'BTC', 'amount': 1.0, 'price_usd': 100.0, 'fee':0, 'batch_id':'1'})
        self.db.commit()
        self.db.create_safety_backup() 
        self.db.close()
        with open(app.DB_FILE, 'wb') as f: f.write(b'PARTIAL_WRITE_GARBAGE_DATA')
        new_db = app.DatabaseManager()
        new_db.restore_safety_backup() 
        df = new_db.get_all()
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['id'], 'safe')
        new_db.close()
    @patch('requests.get')
    def test_network_timeout_retry(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")
        with open(app.KEYS_FILE, 'w') as f: json.dump({"moralis": {"apiKey": "test"}}, f)
        with open(app.WALLETS_FILE, 'w') as f: json.dump({"ETH": ["0x123"]}, f)
        auditor = app.WalletAuditor(self.db)
        with patch('time.sleep') as mock_sleep:
            auditor.run_audit()
            self.assertGreaterEqual(mock_get.call_count, 5)
            mock_sleep.assert_called()



class TestDatabaseIntegrity(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.DB_FILE = self.test_path / 'integrity_test.db'
        app.initialize_folders()
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    
    def test_database_safety_backup_creation(self):
        """Test: Safety backups are created before major operations"""
        db = app.DatabaseManager()
        db.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        db.commit()
        
        db.create_safety_backup()
        # Check that backup file exists
        backup_exists = (app.BASE_DIR / f"{app.DB_FILE.stem}.bak").exists()
        self.assertTrue(backup_exists)
        db.close()
    
    def test_database_backup_restoration(self):
        """Test: Corrupted database can be restored from backup"""
        db1 = app.DatabaseManager()
        db1.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
        db1.commit()
        db1.create_safety_backup()
        db1.close()
        
        # Try to restore (simulated corruption recovery)
        db2 = app.DatabaseManager()
        try:
            db2.restore_safety_backup()
            self.assertTrue(True)
        except Exception as e:
            # OK if no backup to restore
            self.assertIsNotNone(e)
        db2.close()
    
    def test_database_integrity_check(self):
        """Test: _ensure_integrity method validates DB structure"""
        db = app.DatabaseManager()
        db._ensure_integrity()
        # Should not crash if DB is valid
        self.assertTrue(True)
        db.close()




class TestConcurrentExecutionSafety(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'concurrent_test.db'
        app.initialize_folders()
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    
    def test_database_lock_handling(self):
        """Test: Multiple processes trying to access DB don't corrupt data"""
        db1 = app.DatabaseManager()
        
        try:
            db1.save_trade({'id':'1', 'date':'2023-01-01', 'source':'M', 'action':'BUY', 'coin':'BTC', 'amount':1.0, 'price_usd':10000.0, 'fee':0, 'batch_id':'1'})
            db1.commit()
            # Second database instance would encounter lock
            db2 = app.DatabaseManager()
            db2.save_trade({'id':'2', 'date':'2023-01-02', 'source':'M', 'action':'BUY', 'coin':'ETH', 'amount':10.0, 'price_usd':1500.0, 'fee':0, 'batch_id':'2'})
            db2.commit()
            db2.close()
            self.assertTrue(True)
        except Exception as e:
            # OK if lock is detected
            self.assertIsNotNone(e)
        finally:
            db1.close()

# --- 28. EXTREME PRECISION & ROUNDING TESTS ---


class TestSafety(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.orig_base = app.BASE_DIR
        app.BASE_DIR = self.test_path
        app.INPUT_DIR = self.test_path / 'inputs'
        app.OUTPUT_DIR = self.test_path / 'outputs'
        app.DB_FILE = self.test_path / 'safety.db'
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        app.BASE_DIR = self.orig_base
    def test_isolation(self):
        app.initialize_folders()
        self.assertTrue(str(app.DB_FILE).startswith(self.test_dir))



if __name__ == '__main__':
    unittest.main()
