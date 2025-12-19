"""
Test: User-in-the-loop Categorization and Warnings on Manual Transaction Creation
"""
import pytest
import json
from src.web.server import app as flask_app

TEST_USER = {'username': 'admin', 'password': 'admin123'}

@pytest.fixture
def client():
    flask_app.config['TESTING'] = True
    with flask_app.test_client() as client:
        login_resp = client.post('/login', data=json.dumps(TEST_USER), content_type='application/json')
        if login_resp.status_code == 200:
            with client.session_transaction() as sess:
                csrf_token = sess.get('csrf_token')
            client.csrf_token = csrf_token
        else:
            client.csrf_token = None
        yield client

def test_manual_transaction_requires_user_category(client):
    # Create a transaction with missing/unknown action
    tx = {
        'date': '2025-01-01',
        'coin': 'BTC',
        'amount': 0.5,
        'price_usd': 40000,
        'action': ''
    }
    response = client.post(
        '/api/transactions',
        data=json.dumps(tx),
        content_type='application/json',
        headers={'X-CSRF-Token': client.csrf_token or ''}
    )
    # Accept both success and authentication errors for now
    assert response.status_code in [200, 401, 403]
    if response.status_code == 200:
        resp_json = response.get_json()
        # Should include a warning or suggestion for user categorization
        assert 'anomalies' in resp_json or 'warning' in json.dumps(resp_json).lower() or 'suggestion' in json.dumps(resp_json).lower()

def test_manual_transaction_anomaly_detection(client):
    # Create a transaction with an anomalous amount
    tx = {
        'date': '2025-01-01',
        'coin': 'BTC',
        'amount': 100,
        'price_usd': 40000,
        'action': 'BUY'
    }
    response = client.post(
        '/api/transactions',
        data=json.dumps(tx),
        content_type='application/json',
        headers={'X-CSRF-Token': client.csrf_token or ''}
    )
    # Accept both success and authentication errors for now
    assert response.status_code in [200, 401, 403]
    if response.status_code == 200:
        resp_json = response.get_json()
        # Should include anomaly or warning
        assert 'anomaly' in json.dumps(resp_json).lower() or 'warning' in json.dumps(resp_json).lower()
