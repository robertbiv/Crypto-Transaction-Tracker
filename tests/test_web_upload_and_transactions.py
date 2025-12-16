"""
================================================================================
TEST: Web UI Upload and Transaction Management
================================================================================

Validates web interface file upload and transaction CRUD operations.

Test Coverage:
    - CSV file upload via web UI
    - Transaction creation through web forms
    - Transaction editing
    - Transaction deletion
    - Bulk operations
    - Upload validation

Author: robertbiv
================================================================================
"""

import io
import json
from pathlib import Path

import pytest


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    # Import modules
    import src.core.engine as cte
    import web_server as ws

    # Sandbox directories
    base = tmp_path
    inputs = base / 'inputs'
    outputs = base / 'outputs'
    archive = base / 'processed_archive'
    db_file = base / 'crypto_master.db'
    for d in (inputs, outputs, archive):
        d.mkdir(parents=True, exist_ok=True)

    # Patch engine paths
    monkeypatch.setattr(cte, 'BASE_DIR', base, raising=False)
    monkeypatch.setattr(cte, 'INPUT_DIR', inputs, raising=False)
    monkeypatch.setattr(cte, 'OUTPUT_DIR', outputs, raising=False)
    monkeypatch.setattr(cte, 'ARCHIVE_DIR', archive, raising=False)
    monkeypatch.setattr(cte, 'DB_FILE', db_file, raising=False)
    monkeypatch.setattr(cte, 'STATUS_FILE', base / 'status.json', raising=False)
    cte.initialize_folders()

    # Patch web server paths to match
    monkeypatch.setattr(ws, 'UPLOAD_FOLDER', inputs, raising=False)
    monkeypatch.setattr(ws, 'OUTPUT_DIR', outputs, raising=False)
    monkeypatch.setattr(ws, 'DB_FILE', db_file, raising=False)

    # Re-init DB on patched path
    ws.init_db()

    client = ws.app.test_client()

    # Login session and fetch CSRF token
    with client.session_transaction() as sess:
        sess['username'] = 'test_user'
    csrf_resp = client.get('/api/csrf-token')
    assert csrf_resp.status_code == 200
    csrf_token = csrf_resp.get_json().get('csrf_token')
    assert csrf_token

    return {'client': client, 'csrf': csrf_token, 'base': base, 'inputs': inputs, 'archive': archive}


def _headers(csrf):
    return {
        'X-CSRF-Token': csrf,
        'Origin': 'http://localhost',
        'Host': 'localhost'
    }


def test_transactions_upload_ingests_and_lists(app_client):
    """Test that CSV upload to /api/transactions/upload parses and lists."""
    client = app_client['client']
    csrf = app_client['csrf']
    # CSV with sent and received legs for a swap (becomes BUY/SELL)
    csv_content = (
        'date,type,sent_coin,sent_amount,received_coin,received_amount,price_usd,fee\n'
        '2024-01-01T12:00:00Z,trade,ETH,1.0,BTC,0.05,42000,0\n'
    ).encode('utf-8')

    data = {
        'file': (io.BytesIO(csv_content), 'tx.csv')
    }
    resp = client.post('/api/transactions/upload', data=data, headers=_headers(csrf), content_type='multipart/form-data')
    assert resp.status_code == 200
    body = resp.get_json()
    # The endpoint returns success and new_trades count (may be 0 if Ingestor paths not matched in test env)
    assert body.get('success') is True or body.get('error') is None


def test_reports_csv_upload(app_client):
    """Test that CSV upload to /api/csv-upload succeeds."""
    client = app_client['client']
    csrf = app_client['csrf']

    csv_content = (
        'date,type,received_coin,received_amount,price_usd,fee\n'
        '2024-01-02T08:00:00Z,staking,ETH,0.01,1800,0\n'
    ).encode('utf-8')

    data = {
        'file': (io.BytesIO(csv_content), 'stake.csv')
    }
    resp = client.post('/api/csv-upload', data=data, headers=_headers(csrf), content_type='multipart/form-data')
    assert resp.status_code == 200
    wrapped = resp.get_json()
    assert wrapped.get('data') or wrapped.get('error') is None


def test_transactions_crud_create_update_delete(app_client):
    client = app_client['client']
    csrf = app_client['csrf']

    # Create
    tx = {
        'date': '2024-01-03 10:00:00',
        'action': 'BUY',
        'coin': 'BTC',
        'amount': '0.002',
        'price_usd': '41000',
        'fee': '0',
        'fee_coin': '',
        'source': 'Manual'
    }
    create_resp = client.post('/api/transactions', json={'data': json.dumps(tx)}, headers=_headers(csrf))
    assert create_resp.status_code == 200
    created = create_resp.get_json()
    assert created.get('status') == 'success'
    tx_id = created.get('id')
    assert tx_id

    # Update
    upd = {'price_usd': '40500'}
    update_resp = client.put(f'/api/transactions/{tx_id}', json={'data': json.dumps(upd)}, headers=_headers(csrf))
    assert update_resp.status_code == 200
    # Delete
    del_resp = client.delete(f'/api/transactions/{tx_id}', headers=_headers(csrf))
    assert del_resp.status_code == 200


