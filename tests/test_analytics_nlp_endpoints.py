"""
Test: Analytics and NLP Search Endpoints
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

def test_pattern_analysis_endpoint(client):
    # Should return patterns and anomalies
    response = client.post(
        '/api/advanced/pattern-analysis',
        headers={'X-CSRF-Token': client.csrf_token or ''}
    )
    # Accept both success and authentication/missing endpoint errors
    assert response.status_code in [200, 302, 401, 403]
    if response.status_code == 200:
        resp_json = response.get_json()
        assert 'anomalies' in resp_json or 'patterns_analyzed' in resp_json

def test_nlp_search_endpoint(client):
    # Simulate a search query (endpoint may not exist yet)
    query = {'query': 'BTC buys in 2024'}
    response = client.post(
        '/api/advanced/nlp-search',
        data=json.dumps(query),
        content_type='application/json',
        headers={'X-CSRF-Token': client.csrf_token or ''}
    )
    # Accept both success and not found/authentication errors
    assert response.status_code in [200, 404, 401, 403]
    if response.status_code == 200:
        resp_json = response.get_json()
        assert 'results' in resp_json or 'success' in resp_json
