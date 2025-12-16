"""
================================================================================
TEST: Setup Workflow
================================================================================

Validates first-time setup wizard workflow through web UI.

Test Coverage:
    - Multi-step wizard navigation
    - Form validation
    - User account creation
    - Initial configuration
    - Setup completion status

Author: robertbiv
================================================================================
"""

import json
import tempfile
from pathlib import Path

import pytest

# Import the Flask app and module globals
import web_server
from flask import url_for


@pytest.fixture()
def client(monkeypatch):
    """Provide a Flask test client with an isolated USERS_FILE."""
    # Point USERS_FILE to a temporary location to avoid touching real data
    tmpdir = Path(tempfile.mkdtemp())
    users_path = tmpdir / 'users.json'
    monkeypatch.setattr(web_server, 'USERS_FILE', users_path)

    # Ensure first-time setup state at start
    if users_path.exists():
        users_path.unlink()

    app = web_server.app
    app.config['TESTING'] = True
    with app.test_client() as c:
        with app.app_context():
            yield c


def test_setup_wizard_route_exists(client):
    """url_for('setup_wizard') should build correctly."""
    # Use a request context to allow url building
    with web_server.app.test_request_context():
        assert url_for('setup_wizard') == '/setup/wizard'


def test_first_time_setup_json_post_redirects_to_wizard(client):
    """Posting valid JSON to /first-time-setup returns redirect to setup wizard."""
    payload = {
        'username': 'adminuser',
        'password': 'StrongPass123!',
        'confirm_password': 'StrongPass123!'
    }
    resp = client.post('/first-time-setup',
                       data=json.dumps(payload),
                       content_type='application/json')

    assert resp.status_code in (200, 302)
    data = resp.get_json() or {}
    # When JSON, endpoint returns JSON success + redirect
    assert data.get('success') is True
    assert data.get('redirect') == url_for('setup_wizard')


def test_setup_page_access_only_when_needed(client):
    """/setup renders setup.html when no users; redirects when users exist."""
    # No users yet: should render setup page (200)
    resp1 = client.get('/setup')
    assert resp1.status_code == 200

    # Create a fake user to simulate completed setup
    users = {
        'admin': {
            'password_hash': 'dummy',
            'created_at': '2025-01-01T00:00:00Z',
            'is_admin': True
        }
    }
    with open(web_server.USERS_FILE, 'w') as f:
        json.dump(users, f)

    resp2 = client.get('/setup', follow_redirects=False)
    assert resp2.status_code == 302
    assert resp2.headers['Location'].endswith('/login')


def test_first_time_setup_get_renders_template(client):
    """GET /first-time-setup should render the template when no users exist."""
    resp = client.get('/first-time-setup')
    assert resp.status_code == 200


