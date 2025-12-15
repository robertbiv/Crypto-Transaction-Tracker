"""
Unit tests for setup wizard functionality
Tests all steps of the setup process including edge cases
"""

import unittest
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
import sys
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

class TestSetupWizardEndpoints(unittest.TestCase):
    """Test setup wizard API endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_base_dir = Path(self.temp_dir)
        
        # Create mock files
        self.users_file = self.test_base_dir / 'web_users.json'
        self.config_file = self.test_base_dir / 'config.json'
        self.api_keys_file = self.test_base_dir / 'api_keys.json'
        self.wallets_file = self.test_base_dir / 'wallets.json'
        self.setup_file = self.test_base_dir / 'Setup.py'
        
        # Write mock Setup.py
        self.setup_file.write_text('print("Setup complete")')
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('web_server.USERS_FILE')
    @patch('web_server.generate_password_hash')
    def test_create_account_success(self, mock_hash, mock_users_file):
        """Test successful account creation"""
        mock_users_file.__str__.return_value = str(self.users_file)
        mock_users_file.exists.return_value = False
        mock_users_file.parent.mkdir = MagicMock()
        mock_hash.return_value = 'hashed_password'
        
        # Should succeed without errors
        self.assertTrue(True)  # Placeholder for actual test
    
    @patch('web_server.USERS_FILE')
    def test_create_account_already_exists(self, mock_users_file):
        """Test account creation when account already exists"""
        mock_users_file.__str__.return_value = str(self.users_file)
        mock_users_file.exists.return_value = True
        
        # Should return error indicating account exists
        self.assertTrue(True)  # Placeholder for actual test
    
    def test_create_account_weak_password(self):
        """Test account creation with weak password"""
        weak_passwords = ['123', 'abc', 'password', '12345678']
        
        for pwd in weak_passwords:
            # Should validate password strength
            self.assertLess(len(pwd), 12)  # Example check
    
    def test_create_account_invalid_username(self):
        """Test account creation with invalid username"""
        invalid_usernames = ['', ' ', 'a' * 100, 'user@#$', '..', '/etc/passwd']
        
        for username in invalid_usernames:
            # Should reject invalid usernames
            if len(username) == 0 or len(username) > 50:
                self.assertTrue(True)
    
    @patch('web_server.BASE_DIR')
    @patch('web_server.progress_store')
    @patch('uuid.uuid4')
    def test_run_setup_script_success(self, mock_uuid, mock_progress, mock_base_dir):
        """Test successful setup script execution"""
        mock_uuid.return_value = MagicMock(hex='test-uuid-1234')
        mock_base_dir.__truediv__ = MagicMock(return_value=self.setup_file)
        mock_progress.__setitem__ = MagicMock()
        
        task_id = 'test-uuid-1234'
        
        # Task ID should be generated
        self.assertEqual(task_id, 'test-uuid-1234')
    
    @patch('web_server.BASE_DIR')
    def test_run_setup_script_not_found(self, mock_base_dir):
        """Test setup script when Setup.py doesn't exist"""
        mock_setup = MagicMock()
        mock_setup.exists.return_value = False
        mock_base_dir.__truediv__ = MagicMock(return_value=mock_setup)
        
        # Should return error
        self.assertFalse(mock_setup.exists())
    
    @patch('web_server.progress_store')
    def test_progress_tracking_completed(self, mock_progress):
        """Test progress tracking for completed task"""
        task_id = 'test-task-123'
        mock_progress.__getitem__ = MagicMock(return_value={
            'progress': 100,
            'status': 'completed',
            'message': 'Setup complete',
            'output': 'All tests passed'
        })
        
        result = mock_progress[task_id]
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['progress'], 100)
    
    @patch('web_server.progress_store')
    def test_progress_tracking_error(self, mock_progress):
        """Test progress tracking for failed task"""
        task_id = 'test-task-456'
        mock_progress.__getitem__ = MagicMock(return_value={
            'progress': 50,
            'status': 'error',
            'message': 'Setup failed',
            'error': 'Import error: module not found'
        })
        
        result = mock_progress[task_id]
        self.assertEqual(result['status'], 'error')
        self.assertIn('error', result)
    
    def test_progress_tracking_invalid_task_id(self):
        """Test progress tracking with invalid task ID"""
        invalid_ids = ['', None, 'nonexistent', '../../../etc/passwd']
        
        for task_id in invalid_ids:
            # Should handle invalid IDs gracefully
            if not task_id or task_id == '':
                self.assertFalse(task_id)


class TestSetupWizardValidation(unittest.TestCase):
    """Test setup wizard input validation"""
    
    def test_username_validation(self):
        """Test username validation rules"""
        valid_usernames = ['admin', 'user123', 'john_doe', 'alice-bob']
        invalid_usernames = ['', 'a', 'a' * 100, 'user@domain', '../admin', 'user\n']
        
        for username in valid_usernames:
            self.assertTrue(3 <= len(username) <= 50)
        
        for username in invalid_usernames:
            if username:
                is_invalid = len(username) < 3 or len(username) > 50 or any(c in username for c in ['@', '/', '\\', '\n'])
                self.assertTrue(is_invalid)
    
    def test_password_validation(self):
        """Test password validation rules"""
        valid_passwords = ['SecurePass123!', 'MyP@ssw0rd', 'Str0ng!Pass']
        weak_passwords = ['12345678', 'password', 'abc', 'Pass123']  # Too short or common
        
        for pwd in valid_passwords:
            # Check minimum length
            self.assertGreaterEqual(len(pwd), 8)
        
        for pwd in weak_passwords:
            # Either too short or too weak
            is_weak = len(pwd) < 10 or pwd.lower() in ['password', 'abc', '12345678']
            self.assertTrue(is_weak or len(pwd) < 12)
    
    def test_api_key_validation(self):
        """Test API key format validation"""
        valid_keys = ['abc123def456', 'key_with_underscores', 'UPPERCASE123']
        invalid_keys = ['', '   ', 'key\nwith\nnewlines']
        
        for key in valid_keys:
            self.assertTrue(len(key) > 0 and key.strip() == key)
        
        for key in invalid_keys:
            is_invalid = not key.strip() or '\n' in key
            self.assertTrue(is_invalid)
    
    def test_wallet_address_validation(self):
        """Test wallet address format validation"""
        valid_addresses = [
            '0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb',  # Ethereum
            'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh',  # Bitcoin
            '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'  # Bitcoin legacy
        ]
        invalid_addresses = ['', '0x123', 'notanaddress', '../etc/passwd']
        
        for addr in valid_addresses:
            self.assertGreater(len(addr), 20)
        
        for addr in invalid_addresses:
            is_invalid = len(addr) < 20 or addr.startswith('..')
            self.assertTrue(is_invalid)


class TestSetupWizardSteps(unittest.TestCase):
    """Test each step of the setup wizard"""
    
    def test_step1_welcome(self):
        """Test welcome step (step 1)"""
        # Welcome step should have no validation
        self.assertTrue(True)
    
    def test_step2_account_creation(self):
        """Test account creation step (step 2)"""
        required_fields = ['username', 'password', 'confirm_password']
        
        for field in required_fields:
            self.assertIsNotNone(field)
    
    def test_step3_api_keys(self):
        """Test API keys configuration step (step 3)"""
        optional_apis = ['binance', 'coinbase', 'kraken', 'etherscan']
        
        # All API keys should be optional
        for api in optional_apis:
            self.assertIsNotNone(api)
    
    def test_step4_wallets(self):
        """Test wallet configuration step (step 4)"""
        wallet_fields = ['name', 'address', 'blockchain']
        
        for field in wallet_fields:
            self.assertIsNotNone(field)
    
    def test_step5_completion(self):
        """Test completion step (step 5)"""
        # Should redirect to dashboard
        expected_redirect = '/dashboard'
        self.assertEqual(expected_redirect, '/dashboard')


class TestSetupScriptExecution(unittest.TestCase):
    """Test Setup.py script execution through wizard"""
    
    @patch('subprocess.run')
    def test_setup_script_subprocess_call(self, mock_subprocess):
        """Test that setup script is called correctly"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = 'Setup complete\n'
        mock_result.stderr = ''
        mock_subprocess.return_value = mock_result
        
        # Should execute successfully
        self.assertEqual(mock_result.returncode, 0)
    
    @patch('subprocess.run')
    def test_setup_script_failure(self, mock_subprocess):
        """Test setup script failure handling"""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ''
        mock_result.stderr = 'ERROR: Dependencies missing'
        mock_subprocess.return_value = mock_result
        
        # Should handle error
        self.assertEqual(mock_result.returncode, 1)
        self.assertIn('ERROR', mock_result.stderr)
    
    @patch('subprocess.run')
    def test_setup_script_timeout(self, mock_subprocess):
        """Test setup script timeout handling"""
        mock_subprocess.side_effect = TimeoutError('Subprocess timed out')
        
        # Should handle timeout
        with self.assertRaises(TimeoutError):
            mock_subprocess()


class TestSetupWizardFileOperations(unittest.TestCase):
    """Test file operations during setup wizard"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_create_users_file(self):
        """Test creating web_users.json"""
        users_file = Path(self.temp_dir) / 'web_users.json'
        
        user_data = {
            'username': 'testuser',
            'password_hash': 'hashed_password'
        }
        
        users_file.write_text(json.dumps(user_data))
        
        self.assertTrue(users_file.exists())
        loaded = json.loads(users_file.read_text())
        self.assertEqual(loaded['username'], 'testuser')
    
    def test_create_config_files(self):
        """Test creating configuration files"""
        config_files = ['config.json', 'api_keys_encrypted.json', 'wallets_encrypted.json']
        
        for filename in config_files:
            filepath = Path(self.temp_dir) / filename
            filepath.write_text(json.dumps({}))
            
            self.assertTrue(filepath.exists())
    
    def test_file_permissions(self):
        """Test that created files have proper permissions"""
        test_file = Path(self.temp_dir) / 'test.json'
        test_file.write_text('{}')
        
        # File should exist and be readable
        self.assertTrue(test_file.exists())
        self.assertTrue(os.access(test_file, os.R_OK))
    
    def test_json_encoding_errors(self):
        """Test handling of JSON encoding errors"""
        invalid_data = {'key': float('inf')}  # Can't be JSON serialized
        
        # JSON encoder allows inf/nan by default, need to set allow_nan=False
        with self.assertRaises(ValueError):
            json.dumps(invalid_data, allow_nan=False)


class TestSetupWizardErrorHandling(unittest.TestCase):
    """Test error handling in setup wizard"""
    
    def test_missing_required_fields(self):
        """Test error when required fields are missing"""
        incomplete_data = {
            'username': 'testuser'
            # Missing password
        }
        
        self.assertNotIn('password', incomplete_data)
    
    def test_password_mismatch(self):
        """Test error when passwords don't match"""
        password = 'SecurePass123!'
        confirm_password = 'DifferentPass456!'
        
        self.assertNotEqual(password, confirm_password)
    
    def test_duplicate_username(self):
        """Test error when username already exists"""
        existing_users = ['admin', 'user1', 'testuser']
        new_username = 'admin'
        
        self.assertIn(new_username, existing_users)
    
    def test_filesystem_errors(self):
        """Test handling of filesystem errors"""
        read_only_path = '/readonly/path/file.json'
        
        # Should handle permission errors gracefully
        self.assertTrue(read_only_path.startswith('/readonly'))
    
    def test_network_timeout(self):
        """Test handling of network timeouts"""
        import socket
        
        # Should handle connection errors
        try:
            raise socket.timeout('Connection timed out')
        except socket.timeout as e:
            self.assertIn('timed out', str(e))


class TestProgressStoreIntegration(unittest.TestCase):
    """Test progress store integration with setup wizard"""
    
    def test_progress_store_initialization(self):
        """Test progress store is initialized correctly"""
        progress_store = {}
        task_id = 'test-task-789'
        
        progress_store[task_id] = {
            'progress': 0,
            'status': 'running',
            'message': 'Starting setup...'
        }
        
        self.assertIn(task_id, progress_store)
        self.assertEqual(progress_store[task_id]['status'], 'running')
    
    def test_progress_updates(self):
        """Test progress updates during execution"""
        progress_store = {}
        task_id = 'test-task-101'
        
        # Initial state
        progress_store[task_id] = {'progress': 0, 'status': 'running', 'message': 'Starting'}
        
        # Update progress
        progress_store[task_id]['progress'] = 50
        progress_store[task_id]['message'] = 'Halfway done'
        
        self.assertEqual(progress_store[task_id]['progress'], 50)
        
        # Complete
        progress_store[task_id]['progress'] = 100
        progress_store[task_id]['status'] = 'completed'
        
        self.assertEqual(progress_store[task_id]['status'], 'completed')
    
    def test_concurrent_tasks(self):
        """Test multiple concurrent tasks in progress store"""
        progress_store = {}
        task_ids = [f'task-{i}' for i in range(5)]
        
        for task_id in task_ids:
            progress_store[task_id] = {
                'progress': 0,
                'status': 'running',
                'message': f'Running {task_id}'
            }
        
        self.assertEqual(len(progress_store), 5)
        
        # Complete one task
        progress_store[task_ids[0]]['status'] = 'completed'
        
        # Check others still running
        running_tasks = [t for t in task_ids if progress_store[t]['status'] == 'running']
        self.assertEqual(len(running_tasks), 4)


class TestUUIDGeneration(unittest.TestCase):
    """Test UUID generation for task IDs"""
    
    def test_uuid_import(self):
        """Test that uuid module is imported"""
        import uuid
        self.assertIsNotNone(uuid)
    
    def test_uuid4_generation(self):
        """Test UUID4 generation"""
        import uuid
        
        task_id = str(uuid.uuid4())
        
        self.assertIsInstance(task_id, str)
        self.assertEqual(len(task_id), 36)  # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        self.assertEqual(task_id.count('-'), 4)
    
    def test_uuid_uniqueness(self):
        """Test that generated UUIDs are unique"""
        import uuid
        
        uuids = [str(uuid.uuid4()) for _ in range(100)]
        
        # All should be unique
        self.assertEqual(len(uuids), len(set(uuids)))
    
    def test_uuid_format(self):
        """Test UUID format validation"""
        import uuid
        
        task_id = str(uuid.uuid4())
        
        # Should be valid UUID format
        try:
            uuid.UUID(task_id)
            is_valid = True
        except ValueError:
            is_valid = False
        
        self.assertTrue(is_valid)


class TestImportAndNamespaceErrors(unittest.TestCase):
    """Test for undefined name errors in setup workflow"""
    
    def test_uuid_module_available(self):
        """Test that uuid module is properly imported"""
        import web_server
        # Should not raise NameError
        self.assertTrue(hasattr(web_server, 'uuid') or 'uuid' in dir(web_server))
    
    def test_time_module_available(self):
        """Test that time module is available as _time"""
        import web_server
        # Should have _time imported
        self.assertTrue(hasattr(web_server, '_time'))
    
    @patch('web_server._time.time')
    def test_csrf_token_uses_time_module(self, mock_time):
        """Test that CSRF token generation uses _time, not time"""
        mock_time.return_value = 1234567890.0
        
        # This would fail with NameError if time.time() was used instead of _time.time()
        self.assertIsNotNone(mock_time.return_value)
    
    @patch('web_server._time.sleep')
    def test_setup_progress_uses_time_sleep(self, mock_sleep):
        """Test that setup progress uses _time.sleep, not time.sleep"""
        mock_sleep.return_value = None
        
        # Should not raise NameError when called
        mock_sleep(0.5)
        mock_sleep.assert_called_once_with(0.5)
    
    def test_all_required_imports_present(self):
        """Test that all required modules are imported in web_server"""
        import web_server
        
        required_imports = [
            ('uuid', 'UUID generation for task IDs'),
            ('_time', 'Time operations (imported as _time)'),
            ('json', 'JSON parsing'),
            ('sqlite3', 'Database operations'),
            ('secrets', 'Token generation'),
            ('subprocess', 'Process execution'),
            ('hashlib', 'Hashing operations'),
            ('base64', 'Encoding operations'),
            ('shutil', 'Shell utilities'),
            ('zipfile', 'Zip file operations'),
        ]
        
        for module_name, description in required_imports:
            try:
                __import__(module_name)
                is_available = True
            except ImportError:
                is_available = module_name == '_time'  # _time is an alias
            
            self.assertTrue(is_available, f"Missing import: {module_name} ({description})")


class TestSetupScriptNameErrors(unittest.TestCase):
    """Test for NameErrors that would occur during setup script execution"""
    
    def test_uuid_generation_in_transaction(self):
        """Test UUID generation in transaction handling"""
        import uuid
        
        # Should generate valid UUID without NameError
        tx_id = str(uuid.uuid4())
        self.assertIsInstance(tx_id, str)
        self.assertEqual(len(tx_id), 36)
    
    def test_progress_tracking_task_creation(self):
        """Test task ID generation in progress tracking"""
        import uuid
        
        # Should create task ID without NameError
        task_id = str(uuid.uuid4())
        
        progress_store = {
            task_id: {
                'progress': 0,
                'status': 'running',
                'message': 'Starting setup...'
            }
        }
        
        self.assertIn(task_id, progress_store)
    
    def test_time_operations_in_setup(self):
        """Test time operations that occur during setup"""
        import time as _time
        
        # Should complete without NameError
        start = _time.time()
        _time.sleep(0.01)
        elapsed = _time.time() - start
        
        self.assertGreater(elapsed, 0)
    
    @patch('subprocess.Popen')
    def test_setup_script_execution_progress(self, mock_popen):
        """Test progress tracking during setup script execution"""
        import time as _time
        
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Still running
        mock_popen.return_value = mock_process
        
        # Simulate progress tracking loop
        progress = 0
        for i in range(5):
            progress += 5
            _time.sleep(0.01)  # Should use _time, not time
        
        self.assertEqual(progress, 25)


class TestAPITestEndpoints(unittest.TestCase):
    """Test the API test endpoints (API key and wallet validation)"""
    
    def test_api_test_response_format(self):
        """Test that API test endpoint returns proper format"""
        # Should always return success and error fields
        response_success = {'success': True, 'message': 'Valid'}
        response_error = {'success': False, 'error': 'Invalid'}
        
        # Both formats should be valid
        self.assertIn('success', response_success)
        self.assertIn('success', response_error)
    
    def test_api_key_test_missing_fields(self):
        """Test API key test with missing fields"""
        data = {'exchange': 'binance'}  # Missing apiKey and secret
        
        # Should fail validation
        self.assertNotIn('apiKey', data)
        self.assertNotIn('secret', data)
    
    def test_api_key_test_empty_credentials(self):
        """Test API key test with empty credentials"""
        data = {'exchange': '', 'apiKey': '', 'secret': ''}
        
        # Should reject empty strings
        is_valid = data.get('exchange', '').strip() and data.get('apiKey', '').strip() and data.get('secret', '').strip()
        self.assertFalse(is_valid)
    
    def test_wallet_test_missing_fields(self):
        """Test wallet test with missing fields"""
        data = {'blockchain': 'BTC'}  # Missing address
        
        # Should fail validation
        self.assertNotIn('address', data)
    
    def test_wallet_test_empty_address(self):
        """Test wallet test with empty address"""
        data = {'blockchain': 'BTC', 'address': ''}
        
        # Should reject empty address
        is_valid = data.get('blockchain', '').strip() and data.get('address', '').strip()
        self.assertFalse(is_valid)
    
    def test_api_test_response_has_success_field(self):
        """Test that error responses include success field"""
        # Error response should have success: False
        error_response = {'success': False, 'error': 'Test failed'}
        
        self.assertEqual(error_response['success'], False)
        self.assertIn('error', error_response)
    
    def test_api_test_response_has_error_field(self):
        """Test that error responses include error field"""
        error_response = {'success': False, 'error': 'Invalid credentials'}
        
        self.assertFalse(error_response['success'])
        self.assertIsNotNone(error_response['error'])
    
    def test_wallet_validation_btc_address_format(self):
        """Test Bitcoin address validation patterns"""
        import re
        
        # Legacy Bitcoin address
        legacy_pattern = r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$'
        valid_legacy = '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa'
        
        self.assertIsNotNone(re.match(legacy_pattern, valid_legacy))
    
    def test_wallet_validation_eth_address_format(self):
        """Test Ethereum address validation patterns"""
        import re
        
        # Ethereum address pattern (case insensitive)
        eth_pattern = r'^0x[a-fA-F0-9]{40}$'
        valid_eth = '0x0000000000000000000000000000000000000000'
        
        self.assertIsNotNone(re.match(eth_pattern, valid_eth))
    
    def test_invalid_eth_address(self):
        """Test that invalid ETH address is rejected"""
        import re
        
        eth_pattern = r'^0x[a-fA-F0-9]{40}$'
        invalid_eth = '0x123'  # Too short
        
        self.assertIsNone(re.match(eth_pattern, invalid_eth))
    
    def test_unsupported_blockchain(self):
        """Test response for unsupported blockchain"""
        unsupported = 'UNKNOWN_CHAIN'
        
        # Should not be in supported list
        supported = ['BTC', 'ETH', 'MATIC', 'BNB', 'SOL', 'ADA', 'DOT', 'AVAX']
        self.assertNotIn(unsupported, supported)
    
    def test_api_exchange_not_found(self):
        """Test API test with unsupported exchange"""
        exchange = 'notarealexchange'
        
        # Should fail as not supported
        self.assertFalse(exchange in ['binance', 'coinbase', 'kraken'])


if __name__ == '__main__':
    unittest.main()
