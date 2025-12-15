import json
import shutil
import tempfile
import unittest
from pathlib import Path

import Crypto_Tax_Engine as cte
from Crypto_Tax_Engine import DatabaseEncryption


class TestPortableBackups(unittest.TestCase):
    """Test password-derived encryption for portable backups"""
    
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.password = "test_password_123"
        
        self.originals = {
            'KEYS_FILE': cte.KEYS_FILE,
            'API_KEYS_ENCRYPTED_FILE': cte.API_KEYS_ENCRYPTED_FILE,
            'API_KEY_ENCRYPTION_FILE': cte.API_KEY_ENCRYPTION_FILE,
            'WALLETS_FILE': cte.WALLETS_FILE,
            'WALLETS_ENCRYPTED_FILE': cte.WALLETS_ENCRYPTED_FILE,
            'WEB_ENCRYPTION_KEY_FILE': cte.WEB_ENCRYPTION_KEY_FILE,
            'DB_SALT_FILE': cte.DB_SALT_FILE,
        }

        cte.KEYS_FILE = self.tmpdir / 'api_keys.json'
        cte.API_KEYS_ENCRYPTED_FILE = self.tmpdir / 'api_keys_encrypted.json'
        cte.API_KEY_ENCRYPTION_FILE = self.tmpdir / 'api_key_encryption.key'
        cte.WALLETS_FILE = self.tmpdir / 'wallets.json'
        cte.WALLETS_ENCRYPTED_FILE = self.tmpdir / 'wallets_encrypted.json'
        cte.WEB_ENCRYPTION_KEY_FILE = self.tmpdir / 'web_encryption.key'
        cte.DB_SALT_FILE = self.tmpdir / '.db_salt'

    def tearDown(self):
        for attr, value in self.originals.items():
            setattr(cte, attr, value)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_password_derived_keys_consistent(self):
        """Test that same password produces same keys"""
        import os
        
        # Create salt file
        salt = os.urandom(16)
        cte.DB_SALT_FILE.write_bytes(salt)
        
        # Set password in environment
        os.environ['CRYPTO_TAX_PASSWORD'] = self.password
        
        try:
            # Derive keys twice
            key1 = DatabaseEncryption.derive_fernet_key(self.password, salt, 'api_keys')
            key2 = DatabaseEncryption.derive_fernet_key(self.password, salt, 'api_keys')
            
            # Should be identical
            self.assertEqual(key1, key2)
            
            # Different contexts should produce different keys
            key_api = DatabaseEncryption.derive_fernet_key(self.password, salt, 'api_keys')
            key_wallets = DatabaseEncryption.derive_fernet_key(self.password, salt, 'wallets')
            
            self.assertNotEqual(key_api, key_wallets)
        finally:
            if 'CRYPTO_TAX_PASSWORD' in os.environ:
                del os.environ['CRYPTO_TAX_PASSWORD']

    def test_portable_backup_encryption(self):
        """Test that data encrypted with password-derived key can be restored on different machine"""
        import os
        
        # Simulate machine 1: create salt and encrypt data
        salt = os.urandom(16)
        cte.DB_SALT_FILE.write_bytes(salt)
        os.environ['CRYPTO_TAX_PASSWORD'] = self.password
        
        try:
            api_keys_data = {
                'binance': {'apiKey': 'key123', 'secret': 'secret456'}
            }
            wallets_data = {
                'ethereum': ['0xabc123']
            }
            
            # Encrypt on machine 1
            cte.save_api_keys_file(api_keys_data)
            cte.save_wallets_file(wallets_data)
            
            # Verify files were created
            self.assertTrue(cte.API_KEYS_ENCRYPTED_FILE.exists())
            self.assertTrue(cte.WALLETS_ENCRYPTED_FILE.exists())
            
            # Save encrypted files and salt (what would be in backup)
            encrypted_api_keys = cte.API_KEYS_ENCRYPTED_FILE.read_text()
            encrypted_wallets = cte.WALLETS_ENCRYPTED_FILE.read_text()
            
            # Simulate machine 2: clean slate with only salt and encrypted files
            tmpdir2 = Path(tempfile.mkdtemp())
            try:
                cte.API_KEYS_ENCRYPTED_FILE = tmpdir2 / 'api_keys_encrypted.json'
                cte.WALLETS_ENCRYPTED_FILE = tmpdir2 / 'wallets_encrypted.json'
                cte.DB_SALT_FILE = tmpdir2 / '.db_salt'
                cte.API_KEY_ENCRYPTION_FILE = tmpdir2 / 'api_key_encryption.key'
                cte.WEB_ENCRYPTION_KEY_FILE = tmpdir2 / 'web_encryption.key'
                
                # Restore from backup: salt + encrypted files
                cte.DB_SALT_FILE.write_bytes(salt)
                cte.API_KEYS_ENCRYPTED_FILE.write_text(encrypted_api_keys)
                cte.WALLETS_ENCRYPTED_FILE.write_text(encrypted_wallets)
                
                # Password should be enough to decrypt (no key files needed)
                loaded_api_keys = cte.load_api_keys_file()
                loaded_wallets = cte.load_wallets_file()
                
                # Should match original data
                self.assertEqual(api_keys_data, loaded_api_keys)
                self.assertEqual(wallets_data, loaded_wallets)
            finally:
                shutil.rmtree(tmpdir2, ignore_errors=True)
        finally:
            if 'CRYPTO_TAX_PASSWORD' in os.environ:
                del os.environ['CRYPTO_TAX_PASSWORD']

    def test_fallback_to_file_keys_when_no_password(self):
        """Test that system falls back to file-based keys when password unavailable"""
        import os
        
        # No password set, no salt file
        if 'CRYPTO_TAX_PASSWORD' in os.environ:
            del os.environ['CRYPTO_TAX_PASSWORD']
        
        api_keys_data = {'test': {'apiKey': 'key', 'secret': 'secret'}}
        
        # Should create file-based keys and work
        cte.save_api_keys_file(api_keys_data)
        
        # Key file should have been created
        self.assertTrue(cte.API_KEY_ENCRYPTION_FILE.exists())
        
        # Should be able to decrypt
        loaded = cte.load_api_keys_file()
        self.assertEqual(api_keys_data, loaded)


if __name__ == '__main__':
    unittest.main()
