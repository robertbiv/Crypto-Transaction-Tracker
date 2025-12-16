import io
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest
import web_server as ws


def make_db(db_path: Path, rows):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS trades (id TEXT PRIMARY KEY, date TEXT, source TEXT, destination TEXT, action TEXT, coin TEXT, amount TEXT, price_usd TEXT, fee TEXT, fee_coin TEXT, batch_id TEXT)")
    for r in rows:
        cur.execute("INSERT OR REPLACE INTO trades (id,date,source,destination,action,coin,amount,price_usd,fee,fee_coin,batch_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)", r)
    conn.commit()
    conn.close()


def count_trades(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    n = cur.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
    conn.close()
    return n


@pytest.fixture()
def client_tmp(monkeypatch):
    tmpdir = Path(tempfile.mkdtemp())
    monkeypatch.setattr(ws, 'BASE_DIR', tmpdir)
    monkeypatch.setattr(ws, 'DB_FILE', tmpdir / 'crypto_master.db')
    monkeypatch.setattr(ws, 'USERS_FILE', tmpdir / 'web_users.json')
    monkeypatch.setattr(ws, 'CONFIG_FILE', tmpdir / 'config.json')
    monkeypatch.setattr(ws, 'API_KEYS_FILE', tmpdir / 'api_keys.json')
    monkeypatch.setattr(ws, 'API_KEYS_ENCRYPTED_FILE', tmpdir / 'api_keys_encrypted.json')
    monkeypatch.setattr(ws, 'WALLETS_FILE', tmpdir / 'wallets.json')

    # mark setup in progress
    tmpdir.joinpath('web_users.json').write_text(json.dumps({'admin': {'password_hash': 'x', 'is_admin': True}}))

    app = ws.app
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c, tmpdir


def test_merge_mode_inserts_unique_ids(client_tmp):
    client, tmpdir = client_tmp

    # Current DB with 1 row id=A
    make_db(ws.DB_FILE, [
        ('A','2025-01-01','SRC',None,'BUY','BTC','1','30000',None,None,None)
    ])

    # Build backup zip with two rows, one overlapping (A) and one new (B)
    import zipfile
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
        tmpdb = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        tmpdb_path = Path(tmpdb.name)
        tmpdb.close()
        make_db(tmpdb_path, [
            ('A','2025-01-01','SRC',None,'BUY','BTC','1','30000',None,None,None),
            ('B','2025-02-01','SRC',None,'BUY','ETH','2','2000',None,None,None)
        ])
        with open(tmpdb_path, 'rb') as f:
            zf.writestr('crypto_master.db', f.read())
        tmpdb_path.unlink(missing_ok=True)

    mem.seek(0)

    data = {
        'file': (io.BytesIO(mem.getvalue()), 'backup.zip'),
        'mode': 'merge'
    }
    resp = client.post('/api/wizard/restore-backup', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200

    # Expect 2 rows after merge (A from current, B from backup)
    assert count_trades(ws.DB_FILE) == 2


def test_replace_mode_overwrites_db(client_tmp):
    client, tmpdir = client_tmp

    # Current DB with 1 row id=A
    make_db(ws.DB_FILE, [
        ('A','2025-01-01','SRC',None,'BUY','BTC','1','30000',None,None,None)
    ])

    # Backup with only row id=B
    import zipfile
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
        tmpdb = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        tmpdb_path = Path(tmpdb.name)
        tmpdb.close()
        make_db(tmpdb_path, [
            ('B','2025-02-01','SRC',None,'BUY','ETH','2','2000',None,None,None)
        ])
        with open(tmpdb_path, 'rb') as f:
            zf.writestr('crypto_master.db', f.read())
        tmpdb_path.unlink(missing_ok=True)

    mem.seek(0)

    data = {
        'file': (io.BytesIO(mem.getvalue()), 'backup.zip'),
        'mode': 'replace'
    }
    resp = client.post('/api/wizard/restore-backup', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200

    # Expect only 1 row from backup after replace
    assert count_trades(ws.DB_FILE) == 1
    # Verify it's B
    conn = sqlite3.connect(str(ws.DB_FILE))
    cur = conn.cursor()
    ids = [r[0] for r in cur.execute('SELECT id FROM trades').fetchall()]
    conn.close()
    assert ids == ['B']


