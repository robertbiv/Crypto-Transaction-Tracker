import json
import shutil
import tempfile
import unittest
from pathlib import Path

import Crypto_Tax_Engine as cte


class TestEncryptedStorage(unittest.TestCase):
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

    def test_api_keys_encryption_round_trip(self):
        payload = {'binance': {'apiKey': 'KEY123', 'secret': 'SECRET456'}}

        cte.save_api_keys_file(payload)

        encrypted_text = cte.API_KEYS_ENCRYPTED_FILE.read_text()
        self.assertFalse(cte.KEYS_FILE.exists())
        self.assertIn('ciphertext', json.loads(encrypted_text))
        self.assertNotIn('SECRET456', encrypted_text)

        loaded = cte.load_api_keys_file()
        self.assertEqual(payload, loaded)

    def test_api_keys_migrate_plaintext(self):
        payload = {'coinbase': {'apiKey': 'ABC', 'secret': 'DEF'}}
        cte.KEYS_FILE.write_text(json.dumps(payload))

        loaded = cte.load_api_keys_file()

        self.assertEqual(payload, loaded)
        self.assertTrue(cte.API_KEYS_ENCRYPTED_FILE.exists())
        self.assertFalse(cte.KEYS_FILE.exists())

    def test_wallets_encryption_round_trip(self):
        wallets = {'ethereum': {'addresses': ['0xabc', '0xdef']}}

        cte.save_wallets_file(wallets)

        encrypted_text = cte.WALLETS_ENCRYPTED_FILE.read_text()
        self.assertFalse(cte.WALLETS_FILE.exists())
        self.assertIn('ciphertext', json.loads(encrypted_text))
        self.assertNotIn('0xabc', encrypted_text)

        loaded = cte.load_wallets_file()
        self.assertEqual(wallets, loaded)

    def test_wallets_migrate_plaintext(self):
        wallets = {'bitcoin': ['addr1', 'addr2']}
        cte.WALLETS_FILE.write_text(json.dumps(wallets))

        loaded = cte.load_wallets_file()

        self.assertEqual(wallets, loaded)
        self.assertTrue(cte.WALLETS_ENCRYPTED_FILE.exists())
        self.assertFalse(cte.WALLETS_FILE.exists())


if __name__ == '__main__':
    unittest.main()
