import json
import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile
import shutil

import web_server as ws

class TestDiagnosticsActions(unittest.TestCase):
    def setUp(self):
        self.app = ws.app
        self.client = self.app.test_client()
        self.temp_dir = Path(tempfile.mkdtemp())
        
        self.patches = [
            patch.object(ws, 'BASE_DIR', self.temp_dir),
            patch.object(ws, 'CERT_DIR', self.temp_dir / 'certs'),
        ]
        for p in self.patches:
            p.start()
        
        # Ensure session
        with self.client.session_transaction() as sess:
            sess['username'] = 'admin'
            sess['csrf_token'] = 'test_csrf_token'
        
        # Reset diagnostics
        ws.app.config['DIAGNOSTICS_LAST'] = None
    
    def tearDown(self):
        for p in self.patches:
            p.stop()
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def test_generate_cert_endpoint(self):
        # Call endpoint; should generate files
        resp = self.client.post(
            '/api/diagnostics/generate-cert',
            data=json.dumps({}),
            content_type='application/json',
            headers={'X-CSRF-Token': 'test_csrf_token'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get('success'))
        # Cert files should exist
        cert_file = ws.CERT_DIR / 'cert.pem'
        key_file = ws.CERT_DIR / 'key.pem'
        self.assertTrue(cert_file.exists())
        self.assertTrue(key_file.exists())
    
    def test_schema_check_ok(self):
        # Mock DB connection to return 'ok'
        class Conn:
            def execute(self, q):
                class Row:
                    def fetchone(self_inner):
                        return ('ok',)
                return Row()
            def close(self):
                pass
        with patch.object(ws, 'get_db_connection', return_value=Conn()):
            resp = self.client.get('/api/diagnostics/schema-check')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertTrue(data.get('ok'))
            self.assertEqual(data.get('status'), 'ok')
    
    def test_schema_check_fail(self):
        # Mock DB connection to return 'fail'
        class Conn:
            def execute(self, q):
                class Row:
                    def fetchone(self_inner):
                        return ('database disk image is malformed',)
                return Row()
            def close(self):
                pass
        with patch.object(ws, 'get_db_connection', return_value=Conn()):
            resp = self.client.get('/api/diagnostics/schema-check')
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertFalse(data.get('ok'))
            self.assertIn('malformed', data.get('status'))

if __name__ == '__main__':
    unittest.main()
