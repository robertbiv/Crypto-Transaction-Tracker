import json
import tempfile
from pathlib import Path

import pytest
import web_server as ws


@pytest.fixture()
def client_logged_in(monkeypatch):
    tmpdir = Path(tempfile.mkdtemp())
    monkeypatch.setattr(ws, 'BASE_DIR', tmpdir)
    monkeypatch.setattr(ws, 'USERS_FILE', tmpdir / 'web_users.json')

    # Create single user without setup_completed (wizard in progress)
    users = {
        'admin': {
            'password_hash': 'dummy',
            'created_at': '2025-01-01T00:00:00Z',
            'is_admin': True
        }
    }
    ws.USERS_FILE.write_text(json.dumps(users))

    app = ws.app
    app.config['TESTING'] = True
    with app.test_client() as c:
        # Simulate login session
        with c.session_transaction() as sess:
            sess['username'] = 'admin'
        yield c


def test_setup_wizard_contains_restore_controls(client_logged_in):
    resp = client_logged_in.get('/setup/wizard')
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'Upload & Restore Backup' in html
    assert 'wizBackupFile' in html
    assert 'wizBackupPassword' in html
