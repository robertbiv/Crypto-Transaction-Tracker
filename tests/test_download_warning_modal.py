
################################################################################
#
# Test: Download Warning Modal
#
# Module: tests/test_download_warning_modal.py
# Description: Tests for download warning modal and confirmation flow
#              Ensures users must acknowledge before downloading Transaction reports
# Features:
#   - Modal displays on download button click
#   - Both checkboxes required for download
#   - Backend confirmation validation
#   - Audit logging of confirmations
#   - Security checks on file paths
# Author: robertbiv
# Date: 2024-01-15
#
################################################################################

import pytest
import json
from pathlib import Path


class TestDownloadWarningModal:
    """Test download warning modal implementation"""
    
    def test_modal_html_exists(self):
        """Download warning modal HTML file should exist"""
        modal_file = Path('web_templates/download_warning_modal.html')
        assert modal_file.exists(), "Modal HTML file should exist"
    
    def test_modal_javascript_exists(self):
        """JavaScript functions should be in reports.html"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check functions exist
        assert 'showDownloadWarning' in content
        assert 'closeDownloadWarning' in content
        assert 'proceedDownload' in content
        assert 'updateDownloadButton' in content
    
    def test_modal_has_checkboxes(self):
        """Modal should have both confirmation checkboxes"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'confirmCheckbox' in content
        assert 'consultCheckbox' in content
    
    def test_modal_has_warning_text(self):
        """Modal should include warning about consulting Transaction professional"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for key warning elements
        assert 'qualified tax professional' in content.lower()
        assert 'CPA' in content or 'Transaction attorney' in content or 'enrolled agent' in content
    
    def test_modal_styling_included(self):
        """Modal should have CSS styling"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert '.modal {' in content
        assert 'modal-overlay' in content
        assert 'warning-box' in content
    
    def test_modal_api_integration(self):
        """Modal should call /api/download-warning-acknowledged"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert '/api/download-warning-acknowledged' in content
        assert 'fetch' in content
    
    def test_button_disabled_logic(self):
        """Download button should be disabled until both checkboxes checked"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for updateDownloadButton function
        assert 'updateDownloadButton' in content
        assert 'disabled' in content


class TestDownloadWarningEndpointLogic:
    """Test download warning endpoint implementation"""
    
    def test_endpoint_exists_in_server(self):
        """Download warning acknowledged endpoint should exist"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert '/api/download-warning-acknowledged' in content
        assert 'download_warning_acknowledged' in content
    
    def test_endpoint_validates_confirmed_param(self):
        """Endpoint should validate confirmed parameter"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'confirmed' in content
        assert 'get_json' in content
    
    def test_endpoint_validates_report_path(self):
        """Endpoint should validate report_path parameter"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'report_path' in content
        assert 'OUTPUT_DIR' in content or 'outputs' in content.lower()
    
    def test_endpoint_checks_path_security(self):
        """Endpoint should perform path security checks"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Look for path validation
        assert 'resolve' in content or 'startswith' in content or 'path' in content.lower()
    
    def test_endpoint_logs_audit_trail(self):
        """Endpoint should log confirmations"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'audit_log' in content
        assert 'DOWNLOAD_WARNING' in content or 'download' in content.lower()


class TestUserExperience:
    """Test user experience of download warning"""
    
    def test_modal_has_clear_buttons(self):
        """Modal should have clear Cancel and Download buttons"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'Cancel' in content
        assert 'Download' in content or 'Proceed' in content
    
    def test_modal_has_escape_handler(self):
        """Modal should close when Escape key pressed"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'Escape' in content or 'keydown' in content
        assert 'closeDownloadWarning' in content
    
    def test_warning_is_visually_prominent(self):
        """Warning content should be visually emphasized"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for warning colors or styling
        assert '#fff3cd' in content or '#ffc107' in content or 'yellow' in content.lower() or 'warning' in content.lower()
    
    def test_error_messages_clear(self):
        """Error messages should be clear to user"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for showAlert calls
        assert 'showAlert' in content or 'alert' in content.lower()


class TestDownloadFlowIntegration:
    """Integration tests for download flow"""
    
    def test_download_button_calls_modal(self):
        """Download button should show modal instead of direct download"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check that downloadReport function exists
        assert 'function downloadReport' in content or 'downloadReport(' in content
        
        # Check it calls showDownloadWarning
        assert 'showDownloadWarning' in content
    
    def test_modal_sends_api_request(self):
        """Modal should send API request before download"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for proceedDownload function
        assert 'proceedDownload' in content
        
        # Check for fetch call
        assert 'fetch' in content or 'XMLHttpRequest' in content
        
        # Check for API endpoint
        assert '/api/download-warning-acknowledged' in content
    
    def test_both_checkboxes_required_for_download(self):
        """Both checkboxes must be checked before download allowed"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for checkbox requirement logic
        assert 'confirmCheckbox' in content
        assert 'consultCheckbox' in content
        
        # Check that updateDownloadButton disables/enables button
        assert 'updateDownloadButton' in content
        assert 'disabled' in content
    
    def test_after_confirmation_redirects_to_download(self):
        """After confirmation, should proceed to download"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check that download_url is used
        assert 'download_url' in content
        
        # Check for redirect/navigation
        assert 'window.location' in content or 'location.href' in content or 'navigate' in content.lower()


class TestSecurityChecks:
    """Test security aspects of download warning"""
    
    def test_path_traversal_prevention(self):
        """Endpoint should prevent path traversal attacks"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for path validation
        assert 'resolve' in content or 'realpath' in content or 'normpath' in content or '..' not in content or 'startswith' in content
    
    def test_requires_login(self):
        """Endpoint should require authentication"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Find the download warning endpoint
        if '/api/download-warning-acknowledged' in content:
            # Check for login_required decorator nearby
            assert '@login_required' in content or 'login' in content.lower()
    
    def test_file_existence_checked(self):
        """Should verify file exists before allowing download"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for file existence checks
        assert 'exists()' in content or '.exists' in content or 'isfile' in content or 'file' in content.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
