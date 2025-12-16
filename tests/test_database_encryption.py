"""Unit tests for database encryption functionality.

Tests two-layer encryption system:
- Layer 1: Random 256-bit key encrypts database
- Layer 2: Password-derived key (PBKDF2) encrypts Layer 1 key

Covers:
- Key derivation from password
- Key encryption/decryption
- Backup encryption/restoration
- Password verification
- Salt handling
- Edge cases
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import os

# Need to patch paths before import
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.engine import (
    DatabaseEncryption,
    DB_ENCRYPTION_SALT_LENGTH,
    DB_ENCRYPTION_ITERATIONS,
)


class TestKeyDerivation:
    """Test password-to-key derivation (PBKDF2)"""
    
    def test_derive_key_generates_different_keys_for_different_passwords(self):
        """Different passwords should produce different keys"""
        password1 = "password123"
        password2 = "password456"
        
        key1, salt1 = DatabaseEncryption.derive_key_from_password(password1)
        key2, salt2 = DatabaseEncryption.derive_key_from_password(password2)
        
        assert key1 != key2, "Different passwords should produce different keys"
    
    def test_derive_key_with_same_password_and_salt_produces_same_key(self):
        """Same password + salt should produce identical key"""
        password = "mypassword"
        salt = os.urandom(DB_ENCRYPTION_SALT_LENGTH)
        
        key1, _ = DatabaseEncryption.derive_key_from_password(password, salt)
        key2, _ = DatabaseEncryption.derive_key_from_password(password, salt)
        
        assert key1 == key2, "Same password and salt should produce identical keys"
    
    def test_derive_key_generates_random_salt_when_none_provided(self):
        """When salt is None, should generate random salt"""
        password = "testpass"
        
        key1, salt1 = DatabaseEncryption.derive_key_from_password(password, None)
        key2, salt2 = DatabaseEncryption.derive_key_from_password(password, None)
        
        assert salt1 != salt2, "Should generate different salts each time"
        assert len(salt1) == DB_ENCRYPTION_SALT_LENGTH
        assert len(salt2) == DB_ENCRYPTION_SALT_LENGTH
    
    def test_derive_key_returns_fernet_compatible_key(self):
        """Returned key should be base64-encoded and Fernet-compatible"""
        from cryptography.fernet import Fernet
        
        password = "test"
        key, _ = DatabaseEncryption.derive_key_from_password(password)
        
        # Should not raise InvalidToken
        cipher = Fernet(key)
        assert cipher is not None
    
    def test_derive_key_uses_correct_iteration_count(self):
        """Should use OWASP 2023 recommended iteration count"""
        # This is more of a documentation test - verify constant is set correctly
        assert DB_ENCRYPTION_ITERATIONS == 480000, "Should use 480,000 iterations (OWASP 2023)"
    
    def test_derive_key_with_different_salts_produces_different_keys(self):
        """Different salts with same password should produce different keys"""
        password = "samepassword"
        salt1 = os.urandom(DB_ENCRYPTION_SALT_LENGTH)
        salt2 = os.urandom(DB_ENCRYPTION_SALT_LENGTH)
        
        key1, _ = DatabaseEncryption.derive_key_from_password(password, salt1)
        key2, _ = DatabaseEncryption.derive_key_from_password(password, salt2)
        
        assert key1 != key2, "Different salts should produce different keys"


class TestRandomKeyGeneration:
    """Test database encryption key generation"""
    
    def test_generate_random_key_creates_fernet_key(self):
        """Generated key should be Fernet-compatible"""
        from cryptography.fernet import Fernet
        
        key = DatabaseEncryption.generate_random_key()
        
        # Should not raise
        cipher = Fernet(key)
        assert cipher is not None
    
    def test_generate_random_key_produces_different_keys(self):
        """Each call should produce a different key"""
        key1 = DatabaseEncryption.generate_random_key()
        key2 = DatabaseEncryption.generate_random_key()
        
        assert key1 != key2, "Should generate different keys each time"
    
    def test_generate_random_key_is_256_bits(self):
        """Generated key should be 256-bit (when decoded)"""
        from cryptography.fernet import Fernet
        import base64
        
        key = DatabaseEncryption.generate_random_key()
        decoded = base64.urlsafe_b64decode(key)
        
        # Fernet keys are 32 bytes (256 bits)
        assert len(decoded) == 32


class TestKeyEncryption:
    """Test encrypting/decrypting database key with password"""
    
    def test_encrypt_key_can_be_decrypted_with_correct_password(self):
        """Encrypted key should decrypt to original with correct password"""
        db_key = DatabaseEncryption.generate_random_key()
        password = "correctpassword"
        
        encrypted_key, salt = DatabaseEncryption.encrypt_key(db_key, password)
        decrypted_key = DatabaseEncryption.decrypt_key(encrypted_key, password, salt)
        
        assert decrypted_key == db_key, "Decrypted key should match original"
    
    def test_encrypt_key_fails_with_wrong_password(self):
        """Decryption with wrong password should fail"""
        from cryptography.fernet import InvalidToken
        
        db_key = DatabaseEncryption.generate_random_key()
        password = "correctpassword"
        wrong_password = "wrongpassword"
        
        encrypted_key, salt = DatabaseEncryption.encrypt_key(db_key, password)
        
        with pytest.raises(InvalidToken):
            DatabaseEncryption.decrypt_key(encrypted_key, wrong_password, salt)
    
    def test_encrypt_key_generates_different_ciphertexts(self):
        """Same key + password should produce different ciphertexts (due to random salt)"""
        db_key = DatabaseEncryption.generate_random_key()
        password = "samepassword"
        
        encrypted_key1, salt1 = DatabaseEncryption.encrypt_key(db_key, password)
        encrypted_key2, salt2 = DatabaseEncryption.encrypt_key(db_key, password)
        
        # Ciphertexts should be different (random salts)
        assert encrypted_key1 != encrypted_key2
        assert salt1 != salt2
    
    def test_encrypt_key_with_provided_salt(self):
        """Should accept and use provided salt"""
        db_key = DatabaseEncryption.generate_random_key()
        password = "test"
        salt = os.urandom(DB_ENCRYPTION_SALT_LENGTH)
        
        encrypted_key, returned_salt = DatabaseEncryption.encrypt_key(db_key, password, salt)
        
        assert returned_salt == salt, "Should use provided salt"
        
        # Should decrypt with same salt
        decrypted_key = DatabaseEncryption.decrypt_key(encrypted_key, password, salt)
        assert decrypted_key == db_key


class TestInitialization:
    """Test encryption initialization"""
    
    def test_initialize_encryption_creates_new_keys(self):
        """First initialization should create key and salt files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            key_file = tmpdir_path / '.db_key'
            salt_file = tmpdir_path / '.db_salt'
            
            with patch('Crypto_Tax_Engine.DB_KEY_FILE', key_file), \
                 patch('Crypto_Tax_Engine.DB_SALT_FILE', salt_file), \
                 patch('Crypto_Tax_Engine.logger'):
                
                password = "mypassword"
                db_key = DatabaseEncryption.initialize_encryption(password)
                
                assert key_file.exists(), "Should create key file"
                assert salt_file.exists(), "Should create salt file"
                assert len(db_key) > 0, "Should return valid database key"
    
    def test_initialize_encryption_retrieves_existing_keys(self):
        """Second initialization should retrieve existing keys"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            key_file = tmpdir_path / '.db_key'
            salt_file = tmpdir_path / '.db_salt'
            
            with patch('Crypto_Tax_Engine.DB_KEY_FILE', key_file), \
                 patch('Crypto_Tax_Engine.DB_SALT_FILE', salt_file), \
                 patch('Crypto_Tax_Engine.logger'):
                
                password = "mypassword"
                
                # First initialization
                db_key1 = DatabaseEncryption.initialize_encryption(password)
                
                # Second initialization should return same key
                db_key2 = DatabaseEncryption.initialize_encryption(password)
                
                assert db_key1 == db_key2, "Should retrieve same key on second init"
    
    def test_initialize_encryption_fails_with_wrong_password(self):
        """Should fail if wrong password provided on retrieval"""
        from cryptography.fernet import InvalidToken
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            key_file = tmpdir_path / '.db_key'
            salt_file = tmpdir_path / '.db_salt'
            
            with patch('Crypto_Tax_Engine.DB_KEY_FILE', key_file), \
                 patch('Crypto_Tax_Engine.DB_SALT_FILE', salt_file), \
                 patch('Crypto_Tax_Engine.logger'):
                
                # Initialize with correct password
                DatabaseEncryption.initialize_encryption("correctpassword")
                
                # Try with wrong password
                with pytest.raises(InvalidToken):
                    DatabaseEncryption.initialize_encryption("wrongpassword")


class TestBackupEncryption:
    """Test backup encryption/decryption"""
    
    def test_create_encrypted_backup_encrypts_database(self):
        """Backup should be encrypted and different from original"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create mock database file
            db_file = tmpdir_path / 'test.db'
            db_content = b"database content with secret data"
            db_file.write_bytes(db_content)
            
            key_file = tmpdir_path / '.db_key'
            salt_file = tmpdir_path / '.db_salt'
            backup_file = tmpdir_path / 'backup.enc'
            
            with patch('Crypto_Tax_Engine.DB_FILE', db_file), \
                 patch('Crypto_Tax_Engine.DB_KEY_FILE', key_file), \
                 patch('Crypto_Tax_Engine.DB_SALT_FILE', salt_file), \
                 patch('Crypto_Tax_Engine.logger'):
                
                password = "testpassword"
                
                # Initialize encryption
                DatabaseEncryption.initialize_encryption(password)
                
                # Create backup
                result_path = DatabaseEncryption.create_encrypted_backup(password, backup_file)
                
                assert result_path.exists(), "Should create backup file"
                
                # Backup should be encrypted (different from original)
                backup_content = backup_file.read_bytes()
                assert backup_content != db_content, "Backup should be encrypted"
    
    def test_restore_encrypted_backup_recovers_original_database(self):
        """Restored backup should match original database"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            # Create mock database
            db_file = tmpdir_path / 'test.db'
            original_content = b"original database content"
            db_file.write_bytes(original_content)
            
            key_file = tmpdir_path / '.db_key'
            salt_file = tmpdir_path / '.db_salt'
            backup_file = tmpdir_path / 'backup.enc'
            
            with patch('Crypto_Tax_Engine.DB_FILE', db_file), \
                 patch('Crypto_Tax_Engine.DB_KEY_FILE', key_file), \
                 patch('Crypto_Tax_Engine.DB_SALT_FILE', salt_file), \
                 patch('Crypto_Tax_Engine.logger'):
                
                password = "testpassword"
                
                # Initialize and create backup
                DatabaseEncryption.initialize_encryption(password)
                DatabaseEncryption.create_encrypted_backup(password, backup_file)
                
                # Modify database
                db_file.write_bytes(b"corrupted content")
                
                # Restore from backup
                DatabaseEncryption.restore_encrypted_backup(backup_file, password, db_file)
                
                # Should be restored to original
                restored_content = db_file.read_bytes()
                assert restored_content == original_content, "Should restore original content"
    
    def test_restore_encrypted_backup_fails_with_wrong_password(self):
        """Restore should fail with wrong password"""
        from cryptography.fernet import InvalidToken
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            
            db_file = tmpdir_path / 'test.db'
            db_file.write_bytes(b"test content")
            
            key_file = tmpdir_path / '.db_key'
            salt_file = tmpdir_path / '.db_salt'
            backup_file = tmpdir_path / 'backup.enc'
            
            with patch('Crypto_Tax_Engine.DB_FILE', db_file), \
                 patch('Crypto_Tax_Engine.DB_KEY_FILE', key_file), \
                 patch('Crypto_Tax_Engine.DB_SALT_FILE', salt_file), \
                 patch('Crypto_Tax_Engine.logger'):
                
                # Create backup with correct password
                DatabaseEncryption.initialize_encryption("correctpassword")
                DatabaseEncryption.create_encrypted_backup("correctpassword", backup_file)
                
                # Try restore with wrong password
                with pytest.raises(InvalidToken):
                    DatabaseEncryption.restore_encrypted_backup(backup_file, "wrongpassword", db_file)


class TestSecurityProperties:
    """Test security properties of encryption system"""
    
    def test_encrypted_key_file_has_restricted_permissions(self):
        """Key file should have restricted permissions (owner only)"""
        import platform
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            key_file = tmpdir_path / '.db_key'
            salt_file = tmpdir_path / '.db_salt'
            
            with patch('Crypto_Tax_Engine.DB_KEY_FILE', key_file), \
                 patch('Crypto_Tax_Engine.DB_SALT_FILE', salt_file), \
                 patch('Crypto_Tax_Engine.logger'):
                
                DatabaseEncryption.initialize_encryption("password")
                
                # On Unix-like systems, check permissions (mode & 0o077 should be 0)
                # On Windows, permissions are handled differently, just verify file exists
                if platform.system() != 'Windows':
                    mode = os.stat(key_file).st_mode
                    group_other_perms = mode & 0o077
                    assert group_other_perms == 0, "Key file should not be readable by group/others"
                
                assert key_file.exists(), "Key file should exist"
    
    def test_encryption_uses_strong_iteration_count(self):
        """PBKDF2 should use strong iteration count"""
        # Verify constant
        assert DB_ENCRYPTION_ITERATIONS >= 480000, \
            "Should use at least OWASP 2023 recommended iterations (480,000)"
    
    def test_encryption_uses_strong_salt_length(self):
        """Should use adequate salt length"""
        assert DB_ENCRYPTION_SALT_LENGTH >= 16, "Should use at least 16-byte salt"
    
    def test_wrong_password_completely_prevents_access(self):
        """Wrong password should completely prevent any data access"""
        from cryptography.fernet import InvalidToken
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            key_file = tmpdir_path / '.db_key'
            salt_file = tmpdir_path / '.db_salt'
            
            with patch('Crypto_Tax_Engine.DB_KEY_FILE', key_file), \
                 patch('Crypto_Tax_Engine.DB_SALT_FILE', salt_file), \
                 patch('Crypto_Tax_Engine.logger'):
                
                DatabaseEncryption.initialize_encryption("correctpassword")
                
                # Even a single character wrong should fail
                with pytest.raises(InvalidToken):
                    DatabaseEncryption.initialize_encryption("correctpassworx")


class TestEdgeCases:
    """Test edge cases and error conditions"""
    
    def test_empty_password_is_accepted(self):
        """Empty password should still be processed (though not recommended)"""
        db_key = DatabaseEncryption.generate_random_key()
        password = ""
        
        encrypted_key, salt = DatabaseEncryption.encrypt_key(db_key, password)
        decrypted_key = DatabaseEncryption.decrypt_key(encrypted_key, password, salt)
        
        assert decrypted_key == db_key
    
    def test_long_password_is_accepted(self):
        """Very long passwords should work"""
        db_key = DatabaseEncryption.generate_random_key()
        password = "x" * 1000
        
        encrypted_key, salt = DatabaseEncryption.encrypt_key(db_key, password)
        decrypted_key = DatabaseEncryption.decrypt_key(encrypted_key, password, salt)
        
        assert decrypted_key == db_key
    
    def test_unicode_password_is_supported(self):
        """Unicode characters in password should work"""
        db_key = DatabaseEncryption.generate_random_key()
        password = "пароль🔐密码🗝️"
        
        encrypted_key, salt = DatabaseEncryption.encrypt_key(db_key, password)
        decrypted_key = DatabaseEncryption.decrypt_key(encrypted_key, password, salt)
        
        assert decrypted_key == db_key
    
    def test_special_characters_in_password(self):
        """Special characters in password should work"""
        db_key = DatabaseEncryption.generate_random_key()
        password = "P@$$w0rd!#%&*()_+-={}[]|:;<>?,./"
        
        encrypted_key, salt = DatabaseEncryption.encrypt_key(db_key, password)
        decrypted_key = DatabaseEncryption.decrypt_key(encrypted_key, password, salt)
        
        assert decrypted_key == db_key


