import io
import json
import tempfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

import web_server as ws
from src.core.engine import DatabaseEncryption


@pytest.fixture()
def client_and_tmp(monkeypatch):
    tmpdir = Path(tempfile.mkdtemp())
    # Patch base paths to temp dir
    monkeypatch.setattr(ws, 'BASE_DIR', tmpdir)
    monkeypatch.setattr(ws, 'DB_FILE', tmpdir / 'crypto_master.db')
    monkeypatch.setattr(ws, 'USERS_FILE', tmpdir / 'web_users.json')
    monkeypatch.setattr(ws, 'CONFIG_FILE', tmpdir / 'config.json')
    monkeypatch.setattr(ws, 'API_KEYS_FILE', tmpdir / 'api_keys.json')
    monkeypatch.setattr(ws, 'API_KEYS_ENCRYPTED_FILE', tmpdir / 'api_keys_encrypted.json')
    monkeypatch.setattr(ws, 'WALLETS_FILE', tmpdir / 'wallets.json')

    # Ensure first-time setup state
    if ws.USERS_FILE.exists():
        ws.USERS_FILE.unlink()

    app = ws.app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c, tmpdir


def make_plain_backup_zip(tmpdir: Path) -> bytes:
    # Create sample file contents
    (tmpdir / 'dummy').write_text('x')
    raw = io.BytesIO()
    import zipfile
    with zipfile.ZipFile(raw, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('crypto_master.db', b'SQLITE_DB_BYTES')
        zf.writestr('config.json', json.dumps({'accounting_method': 'HIFO'}))
        zf.writestr('api_keys.json', json.dumps({'exchange': {'key': 'abc'}}))
        zf.writestr('wallets.json', json.dumps({'BTC': ['addr']}))
        zf.writestr('web_users.json', json.dumps({'admin': {'password_hash': 'hash'}}))
    return raw.getvalue()


def test_wizard_restore_plain_zip(client_and_tmp):
    client, tmpdir = client_and_tmp

    raw_zip = make_plain_backup_zip(tmpdir)

    data = {
        'file': (io.BytesIO(raw_zip), 'backup_123.zip')
    }
    resp = client.post('/api/wizard/restore-backup', data=data, content_type='multipart/form-data')
    if resp.status_code != 200:
        print('resp:', resp.status_code, resp.get_data(as_text=True))
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload.get('success') is True

    # Files should be restored
    assert ws.DB_FILE.exists()
    assert ws.CONFIG_FILE.exists()
    # API keys may go to encrypted or plain; we provided plain
    assert ws.API_KEYS_FILE.exists()
    assert ws.WALLETS_FILE.exists()
    assert ws.USERS_FILE.exists()


def test_wizard_restore_encrypted_zip(client_and_tmp):
    client, tmpdir = client_and_tmp

    password = 'StrongPass!123'
    # Generate db_key and write encrypted key + salt to .db_key/.db_salt
    db_key = DatabaseEncryption.generate_random_key()
    enc_key, salt = DatabaseEncryption.encrypt_key(db_key, password)
    (tmpdir / '.db_key').write_bytes(enc_key)
    (tmpdir / '.db_salt').write_bytes(salt)

    # Build a raw zip identical to plain case
    raw_zip = make_plain_backup_zip(tmpdir)
    cipher = Fernet(db_key)
    enc_payload = cipher.encrypt(raw_zip)

    data = {
        'file': (io.BytesIO(enc_payload), 'backup_123.zip.enc'),
        'password': password
    }

    resp = client.post('/api/wizard/restore-backup', data=data, content_type='multipart/form-data')
    if resp.status_code != 200:
        print('resp:', resp.status_code, resp.get_data(as_text=True))
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload.get('success') is True

    # Files should be restored
    assert ws.DB_FILE.exists()
    assert ws.CONFIG_FILE.exists()
    assert ws.API_KEYS_FILE.exists() or ws.API_KEYS_ENCRYPTED_FILE.exists()
    assert ws.WALLETS_FILE.exists()
    assert ws.USERS_FILE.exists()


def test_wizard_restore_requires_file(client_and_tmp):
    client, _ = client_and_tmp
    resp = client.post('/api/wizard/restore-backup', data={}, content_type='multipart/form-data')
    assert resp.status_code == 400
    payload = resp.get_json()
    assert 'Missing file' in payload.get('error', '')


