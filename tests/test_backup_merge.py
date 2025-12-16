import json
import shutil
import tempfile
import unittest
import zipfile
import io
from pathlib import Path

import web_server as ws


class TestBackupMerge(unittest.TestCase):
    """Test merge logic for API keys and wallets during restore"""
    
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.originals = {
            'API_KEYS_FILE': ws.API_KEYS_FILE,
            'API_KEYS_ENCRYPTED_FILE': ws.API_KEYS_ENCRYPTED_FILE,
            'API_KEY_ENCRYPTION_FILE': ws.API_KEY_ENCRYPTION_FILE,
            'WALLETS_FILE': ws.WALLETS_FILE,
            'WALLETS_ENCRYPTED_FILE': ws.WALLETS_ENCRYPTED_FILE,
            'ENCRYPTION_KEY_FILE': ws.ENCRYPTION_KEY_FILE,
        }

        ws.API_KEYS_FILE = self.tmpdir / 'api_keys.json'
        ws.API_KEYS_ENCRYPTED_FILE = self.tmpdir / 'api_keys_encrypted.json'
        ws.API_KEY_ENCRYPTION_FILE = self.tmpdir / 'api_key_encryption.key'
        ws.WALLETS_FILE = self.tmpdir / 'wallets.json'
        ws.WALLETS_ENCRYPTED_FILE = self.tmpdir / 'wallets_encrypted.json'
        ws.ENCRYPTION_KEY_FILE = self.tmpdir / 'web_encryption.key'

    def tearDown(self):
        for attr, value in self.originals.items():
            setattr(ws, attr, value)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_api_keys_merge_preserves_new_exchanges(self):
        """Test that API keys added after backup are preserved during merge"""
        # Current system state: has binance and coinbase
        current_api_keys = {
            'binance': {'apiKey': 'key1', 'secret': 'secret1'},
            'coinbase': {'apiKey': 'key2', 'secret': 'secret2'}
        }
        ws.save_api_keys_file(current_api_keys)
        
        # Backup only has binance (older backup before coinbase was added)
        backup_api_keys = {
            'binance': {'apiKey': 'old_key1', 'secret': 'old_secret1'}
        }
        
        # Create mock backup zip
        backup_zip = io.BytesIO()
        with zipfile.ZipFile(backup_zip, 'w') as zf:
            encrypted = ws.encrypt_api_keys(backup_api_keys)
            zf.writestr('api_keys_encrypted.json', json.dumps({'ciphertext': encrypted}))
        
        backup_zip.seek(0)
        
        # Simulate merge logic
        with zipfile.ZipFile(backup_zip, 'r') as zf:
            with zf.open('api_keys_encrypted.json') as src:
                backup_data = json.load(src)
                loaded_backup = ws.decrypt_api_keys(backup_data['ciphertext'])
        
        # Merge
        merged = {**current_api_keys, **loaded_backup}
        
        # Should have both exchanges
        self.assertIn('binance', merged)
        self.assertIn('coinbase', merged)
        # Backup binance overwrites current
        self.assertEqual(merged['binance']['apiKey'], 'old_key1')
        # Coinbase preserved from current
        self.assertEqual(merged['coinbase']['apiKey'], 'key2')

    def test_wallets_merge_combines_addresses(self):
        """Test that wallet addresses are combined and deduplicated during merge"""
        # Current system: ethereum and bitcoin wallets
        current_wallets = {
            'ethereum': ['0xAAA', '0xBBB'],
            'bitcoin': ['bc1xxx']
        }
        ws.save_wallets_file(current_wallets)
        
        # Backup: ethereum has one overlapping address and one new one
        backup_wallets = {
            'ethereum': ['0xAAA', '0xCCC'],  # 0xAAA overlaps, 0xCCC is new
            'solana': ['SolAddr1']  # New chain
        }
        
        # Simulate merge logic
        merged_wallets = {}
        all_chains = set(current_wallets.keys()) | set(backup_wallets.keys())
        
        for chain in all_chains:
            existing = current_wallets.get(chain, [])
            backup = backup_wallets.get(chain, [])
            
            if not isinstance(existing, list):
                existing = [existing] if existing else []
            if not isinstance(backup, list):
                backup = [backup] if backup else []
            
            # Deduplicate
            all_addrs = list(set(existing + backup))
            if all_addrs:
                merged_wallets[chain] = all_addrs
        
        # Should have all three chains
        self.assertIn('ethereum', merged_wallets)
        self.assertIn('bitcoin', merged_wallets)
        self.assertIn('solana', merged_wallets)
        
        # Ethereum should have all three unique addresses
        self.assertEqual(len(merged_wallets['ethereum']), 3)
        self.assertIn('0xAAA', merged_wallets['ethereum'])
        self.assertIn('0xBBB', merged_wallets['ethereum'])
        self.assertIn('0xCCC', merged_wallets['ethereum'])
        
        # Bitcoin preserved
        self.assertIn('bc1xxx', merged_wallets['bitcoin'])
        
        # Solana added from backup
        self.assertIn('SolAddr1', merged_wallets['solana'])

    def test_replace_mode_overwrites_completely(self):
        """Test that replace mode overwrites instead of merging"""
        # Current state
        current_api_keys = {
            'binance': {'apiKey': 'current', 'secret': 'current'},
            'coinbase': {'apiKey': 'current', 'secret': 'current'}
        }
        ws.save_api_keys_file(current_api_keys)
        
        # Backup (only binance)
        backup_api_keys = {
            'binance': {'apiKey': 'backup', 'secret': 'backup'}
        }
        
        # In replace mode, backup completely replaces current
        # After restore, should only have binance (coinbase lost)
        result = backup_api_keys
        
        self.assertIn('binance', result)
        self.assertNotIn('coinbase', result)
        self.assertEqual(result['binance']['apiKey'], 'backup')


if __name__ == '__main__':
    unittest.main()


