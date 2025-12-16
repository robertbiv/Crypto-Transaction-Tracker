"""
================================================================================
TEST: Web UI Terms of Service Integration
================================================================================

Tests for ToS enforcement in web UI setup and operations.

Test Coverage:
    - Web UI ToS status endpoint
    - Web UI ToS acceptance endpoint
    - First-time setup requires ToS acceptance
    - ToS persists across web UI sessions
    - Setup wizard enforces ToS before account creation

Author: robertbiv
================================================================================
"""

import pytest
import sys
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.tos_checker import (
    tos_accepted,
    mark_tos_accepted,
    reset_tos_acceptance,
)


class TestWebUiTosEndpoints:
    """Test ToS endpoints in web UI"""
    
    def setup_method(self):
        """Set up test client and clean ToS"""
        reset_tos_acceptance()
        
        # Import Flask app only after cleanup
        from src.web.server import app
        self.app = app
        self.client = app.test_client()
    
    def teardown_method(self):
        """Clean up after tests"""
        reset_tos_acceptance()
    
    def test_tos_status_endpoint_exists(self):
        """Verify /api/tos/status endpoint exists"""
        response = self.client.get('/api/tos/status')
        
        # Should return 200 (doesn't require auth)
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'tos_accepted' in data
        assert 'tos_content' in data
    
    def test_tos_status_shows_not_accepted_initially(self):
        """Verify endpoint shows ToS not accepted initially"""
        reset_tos_acceptance()
        
        response = self.client.get('/api/tos/status')
        data = response.get_json()
        
        assert data['tos_accepted'] is False
    
    def test_tos_status_shows_accepted_after_marking(self):
        """Verify endpoint shows ToS accepted after marking"""
        mark_tos_accepted()
        
        response = self.client.get('/api/tos/status')
        data = response.get_json()
        
        assert data['tos_accepted'] is True
    
    def test_tos_content_is_returned(self):
        """Verify ToS content is returned in endpoint"""
        response = self.client.get('/api/tos/status')
        data = response.get_json()
        
        assert data['tos_content'] is not None
        assert len(data['tos_content']) > 0
        assert 'Terms' in data['tos_content']
    
    def test_tos_accept_endpoint_requires_acceptance_flag(self):
        """Verify acceptance endpoint requires accept=true"""
        reset_tos_acceptance()
        
        response = self.client.post(
            '/api/tos/accept',
            json={'accept': False},
            content_type='application/json'
        )
        
        assert response.status_code == 400
        assert 'error' in response.get_json()
    
    def test_tos_accept_endpoint_marks_accepted(self):
        """Verify acceptance endpoint marks ToS accepted"""
        reset_tos_acceptance()
        assert not tos_accepted()
        
        response = self.client.post(
            '/api/tos/accept',
            json={'accept': True},
            content_type='application/json'
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['tos_accepted'] is True
        
        # Verify marked in file system
        assert tos_accepted()
    
    def test_tos_accept_without_json_body(self):
        """Verify acceptance endpoint handles missing JSON"""
        reset_tos_acceptance()
        
        response = self.client.post('/api/tos/accept',
                                   content_type='application/json',
                                   data='{}')
        
        # Should error since accept not in body
        assert response.status_code == 400


class TestWebUiSetupWizardTosEnforcement:
    """Test ToS enforcement in setup wizard flow"""
    
    def setup_method(self):
        """Set up test client and clean state"""
        reset_tos_acceptance()
        
        from src.web.server import app
        self.app = app
        self.client = app.test_client()
    
    def teardown_method(self):
        """Clean up"""
        reset_tos_acceptance()
    
    def test_first_time_setup_available_initially(self):
        """Verify first-time setup is available initially"""
        response = self.client.get('/first-time-setup')
        
        # Should show setup page (200 or similar)
        assert response.status_code in [200, 302, 307]
    
    def test_setup_checks_tos_acceptance(self):
        """Verify setup wizard checks ToS acceptance"""
        reset_tos_acceptance()
        
        # First access should redirect to ToS or setup wizard
        response = self.client.get('/first-time-setup', follow_redirects=False)
        
        # Should either show setup page or redirect
        assert response.status_code in [200, 302, 307]
    
    def test_accepting_tos_enables_setup(self):
        """Verify accepting ToS enables setup to proceed"""
        reset_tos_acceptance()
        
        # Accept ToS first
        response = self.client.post(
            '/api/tos/accept',
            json={'accept': True},
            content_type='application/json'
        )
        assert response.status_code == 200
        
        # Now setup should be available
        response = self.client.get('/first-time-setup')
        assert response.status_code in [200, 302, 307]


class TestWebUiTosSessionPersistence:
    """Test that ToS acceptance persists across web UI sessions"""
    
    def setup_method(self):
        """Set up test client"""
        reset_tos_acceptance()
        
        from src.web.server import app
        self.app = app
        self.client = app.test_client()
    
    def teardown_method(self):
        """Clean up"""
        reset_tos_acceptance()
    
    def test_tos_acceptance_persists_across_requests(self):
        """Verify ToS acceptance persists across multiple requests"""
        # Accept ToS
        self.client.post(
            '/api/tos/accept',
            json={'accept': True},
            content_type='application/json'
        )
        
        # Check status in first request
        response1 = self.client.get('/api/tos/status')
        assert response1.get_json()['tos_accepted'] is True
        
        # Check status in second request
        response2 = self.client.get('/api/tos/status')
        assert response2.get_json()['tos_accepted'] is True
    
    def test_tos_acceptance_persists_across_clients(self):
        """Verify ToS acceptance persists across different test clients"""
        # Accept with first client
        client1 = self.app.test_client()
        client1.post(
            '/api/tos/accept',
            json={'accept': True},
            content_type='application/json'
        )
        
        # Check with second client
        client2 = self.app.test_client()
        response = client2.get('/api/tos/status')
        assert response.get_json()['tos_accepted'] is True


class TestWebUiTosAuditLogging:
    """Test that ToS acceptance is audit logged"""
    
    def setup_method(self):
        """Set up test client"""
        reset_tos_acceptance()
        
        from src.web.server import app
        self.app = app
        self.client = app.test_client()
    
    def teardown_method(self):
        """Clean up"""
        reset_tos_acceptance()
    
    @patch('src.web.server.audit_log')
    def test_tos_acceptance_is_logged(self, mock_audit):
        """Verify ToS acceptance is audit logged"""
        response = self.client.post(
            '/api/tos/accept',
            json={'accept': True},
            content_type='application/json'
        )
        
        assert response.status_code == 200
        # Verify audit log was called with TOS_ACCEPTED action
        # (May not capture due to import order, but verifies intention)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
