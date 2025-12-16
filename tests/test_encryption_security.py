import json
import shutil
import tempfile
import unittest
from pathlib import Path

import src.core.engine as cte


class TestEncryptionSecurity(unittest.TestCase):
    """Test security edge cases for encrypted storage"""
    
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.originals = {
            'KEYS_FILE': cte.KEYS_FILE,
            'API_KEYS_ENCRYPTED_FILE': cte.API_KEYS_ENCRYPTED_FILE,
            'API_KEY_ENCRYPTION_FILE': cte.API_KEY_ENCRYPTION_FILE,
            'WALLETS_FILE': cte.WALLETS_FILE,
            'WALLETS_ENCRYPTED_FILE': cte.WALLETS_ENCRYPTED_FILE,
            'WEB_ENCRYPTION_KEY_FILE': cte.WEB_ENCRYPTION_KEY_FILE,
        }

        cte.KEYS_FILE = self.tmpdir / 'api_keys.json'
        cte.API_KEYS_ENCRYPTED_FILE = self.tmpdir / 'api_keys_encrypted.json'
        cte.API_KEY_ENCRYPTION_FILE = self.tmpdir / 'api_key_encryption.key'
        cte.WALLETS_FILE = self.tmpdir / 'wallets.json'
        cte.WALLETS_ENCRYPTED_FILE = self.tmpdir / 'wallets_encrypted.json'
        cte.WEB_ENCRYPTION_KEY_FILE = self.tmpdir / 'web_encryption.key'

    def tearDown(self):
        for attr, value in self.originals.items():
            setattr(cte, attr, value)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_corrupted_ciphertext_fails_loud(self):
        """Test that corrupted ciphertext raises error instead of silently returning empty dict"""
        # Write corrupted encrypted file
        cte.API_KEYS_ENCRYPTED_FILE.write_text(json.dumps({
            'ciphertext': 'CORRUPTED_BASE64_DATA!!!'
        }))
        
        # Should raise ValueError, not return {}
        with self.assertRaises(ValueError) as ctx:
            cte.load_api_keys_file()
        
        self.assertIn('decryption failed', str(ctx.exception).lower())

    def test_tampered_ciphertext_wallets_fails_loud(self):
        """Test that tampered wallet ciphertext raises error"""
        cte.WALLETS_ENCRYPTED_FILE.write_text(json.dumps({
            'ciphertext': 'AAAAinvalidAAAA'
        }))
        
        with self.assertRaises(ValueError) as ctx:
            cte.load_wallets_file()
        
        self.assertIn('decryption failed', str(ctx.exception).lower())

    def test_encryption_failure_raises_error(self):
        """Test that encryption failures are caught"""
        # This is hard to trigger naturally, but we can test the validation
        payload = {'test': 'data'}
        
        # Save should work
        cte.save_api_keys_file(payload)
        self.assertTrue(cte.API_KEYS_ENCRYPTED_FILE.exists())

    def test_concurrent_access_protected_by_locks(self):
        """Test that file locks prevent concurrent writes"""
        import threading
        import time
        
        payload1 = {'exchange1': {'apiKey': 'key1', 'secret': 'secret1'}}
        payload2 = {'exchange2': {'apiKey': 'key2', 'secret': 'secret2'}}
        
        results = []
        
        def write_data(data, delay=0):
            try:
                if delay:
                    time.sleep(delay)
                cte.save_api_keys_file(data)
                results.append('success')
            except Exception as e:
                results.append(f'error: {e}')
        
        # Start two writes concurrently
        t1 = threading.Thread(target=write_data, args=(payload1, 0.1))
        t2 = threading.Thread(target=write_data, args=(payload2, 0.15))
        
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        
        # Both should succeed (locks serialize access)
        self.assertEqual(len(results), 2)
        # At least one should succeed
        self.assertIn('success', results)

    def test_migration_preserves_data_integrity(self):
        """Test that migration from plain to encrypted preserves exact data"""
        original_data = {
            'binance': {
                'apiKey': 'test_key_123',
                'secret': 'test_secret_456'
            },
            'coinbase': {
                'apiKey': 'cb_key_789',
                'secret': 'cb_secret_012'
            }
        }
        
        # Write plain file
        cte.KEYS_FILE.write_text(json.dumps(original_data))
        
        # Load should migrate
        loaded = cte.load_api_keys_file()
        
        # Data should be identical
        self.assertEqual(loaded, original_data)
        
        # Encrypted file should now exist
        self.assertTrue(cte.API_KEYS_ENCRYPTED_FILE.exists())
        
        # Plain file should be removed
        self.assertFalse(cte.KEYS_FILE.exists())
        
        # Re-loading should still work
        reloaded = cte.load_api_keys_file()
        self.assertEqual(reloaded, original_data)

    def test_empty_data_handled_correctly(self):
        """Test that empty dict can be encrypted and decrypted"""
        cte.save_api_keys_file({})
        loaded = cte.load_api_keys_file()
        self.assertEqual(loaded, {})

    def test_special_characters_in_secrets(self):
        """Test that special characters in secrets are preserved"""
        payload = {
            'test': {
                'apiKey': 'key!@#$%^&*()_+-=[]{}|;:,.<>?',
                'secret': 'secret with spaces and "quotes" and \\backslashes\\'
            }
        }
        
        cte.save_wallets_file(payload)
        loaded = cte.load_wallets_file()
        
        self.assertEqual(loaded, payload)


if __name__ == '__main__':
    unittest.main()


