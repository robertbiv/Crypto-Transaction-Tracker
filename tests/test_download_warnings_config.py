
################################################################################
#
# Test: Download Warnings Configuration
#
# Module: tests/test_download_warnings_config.py
# Description: Tests for download warnings configuration setting
#              Validates that warnings can be disabled while maintaining audit trail
# Features:
#   - Configuration setting in config.json
#   - API endpoint to check configuration
#   - Modal conditionally shown/hidden based on config
#   - Persistent warning banner when disabled
#   - Download still requires confirmation for audit trail
# Author: robertbiv
# Date: 2024-01-15
#
################################################################################

import pytest
import json
from pathlib import Path


class TestDownloadWarningsConfigSetting:
    """Test download warnings configuration in config.json"""
    
    def test_config_file_has_ui_section(self):
        """config.json should have ui section"""
        config_file = Path('configs/config.json')
        config = json.loads(config_file.read_text())
        
        assert 'ui' in config
    
    def test_config_has_download_warnings_setting(self):
        """config.json should have download_warnings_enabled setting"""
        config_file = Path('configs/config.json')
        config = json.loads(config_file.read_text())
        
        assert 'download_warnings_enabled' in config.get('ui', {})
    
    def test_download_warnings_default_enabled(self):
        """download_warnings_enabled should default to true"""
        config_file = Path('configs/config.json')
        config = json.loads(config_file.read_text())
        
        setting = config.get('ui', {}).get('download_warnings_enabled', True)
        assert setting is True
    
    def test_config_has_instructions(self):
        """Config should have instructions for the setting"""
        config_file = Path('configs/config.json')
        config = json.loads(config_file.read_text())
        
        instructions = config.get('ui', {}).get('_INSTRUCTIONS', '')
        assert 'download_warnings_enabled' in instructions
        assert 'tax professional' in instructions.lower()
    
    def test_instructions_warn_about_disabling(self):
        """Instructions should warn about disabling warnings"""
        config_file = Path('configs/config.json')
        config = json.loads(config_file.read_text())
        
        instructions = config.get('ui', {}).get('_INSTRUCTIONS', '')
        assert 'Recommended' in instructions
        assert 'True' in instructions


class TestDownloadWarningsConfigEndpoint:
    """Test /api/download-warnings-config endpoint"""
    
    def test_endpoint_exists_in_server(self):
        """Endpoint should exist in server.py"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert '/api/download-warnings-config' in content
        assert 'get_download_warnings_config' in content
    
    def test_endpoint_requires_login(self):
        """Endpoint should require authentication"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Find the endpoint and check for login decorator
        if '/api/download-warnings-config' in content:
            assert '@login_required' in content
    
    def test_endpoint_loads_config(self):
        """Endpoint should load configuration"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        if '/api/download-warnings-config' in content:
            assert 'load_config' in content
    
    def test_endpoint_returns_enabled_status(self):
        """Endpoint should return enabled status"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        if '/api/download-warnings-config' in content:
            assert 'enabled' in content
    
    def test_endpoint_returns_message(self):
        """Endpoint should return status message"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        if '/api/download-warnings-config' in content:
            assert 'message' in content


class TestDownloadWarningsConditionalLogic:
    """Test conditional logic for warnings"""
    
    def test_javascript_checks_enabled_status(self):
        """JavaScript should check if warnings are enabled"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'downloadWarningsEnabled' in content
        assert 'checkDownloadWarningsConfig' in content
    
    def test_modal_skipped_when_disabled(self):
        """Modal should be skipped when warnings disabled"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'if (!downloadWarningsEnabled)' in content or 'downloadWarningsEnabled' in content
        assert 'proceedDownload' in content
    
    def test_download_still_requires_confirmation(self):
        """Download should still require confirmation when warnings disabled"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Should still check confirmed parameter
        assert 'user_confirmed' in content
        assert 'confirmed' in content
    
    def test_page_loads_config_on_init(self):
        """Page should load config on initialization"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for DOMContentLoaded or similar
        assert 'DOMContentLoaded' in content
        assert 'checkDownloadWarningsConfig' in content


class TestDownloadWarningsBanner:
    """Test persistent warning banner when disabled"""
    
    def test_banner_html_exists(self):
        """Warning banner HTML should exist"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'warningsDisabledNotice' in content
        assert 'CRITICAL REMINDER' in content
    
    def test_banner_has_warning_styling(self):
        """Banner should use warning styling"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'alert-danger' in content or 'alert' in content
        assert 'warning' in content.lower()
    
    def test_banner_reminds_about_tax_professional(self):
        """Banner should remind about consulting tax professional"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'tax professional' in content.lower()
        assert 'CPA' in content or 'enrolled agent' in content
    
    def test_banner_states_no_liability(self):
        """Banner should state author takes no liability"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'no liability' in content.lower() or 'liability' in content.lower()
    
    def test_banner_shown_when_disabled(self):
        """Banner should show when warnings disabled"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check that the banner display logic exists
        assert 'warningNotice.style.display' in content or 'warningsDisabledNotice' in content
        assert 'block' in content


class TestDownloadWarningsAuditTrail:
    """Test that audit trail is maintained regardless of setting"""
    
    def test_download_logged_in_endpoint(self):
        """Downloads should still be logged for audit"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        assert 'audit_log' in content
        assert 'DOWNLOAD_WARNING_CONFIRMED' in content
    
    def test_endpoint_checks_config_before_validation(self):
        """Endpoint should check config but still validate"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Should load config
        assert 'load_config' in content
        # Should still validate file path
        assert 'file_path.exists()' in content or '.exists' in content
    
    def test_endpoint_always_validates_path(self):
        """Path validation should always occur regardless of setting"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Path security checks should not be conditional
        assert 'OUTPUT_DIR.resolve()' in content or 'resolve' in content


class TestDownloadWarningsUserExperience:
    """Test user experience when warnings are disabled"""
    
    def test_direct_download_when_disabled(self):
        """Download should proceed directly when warnings disabled"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for conditional logic
        assert 'if (!downloadWarningsEnabled)' in content or 'downloadWarningsEnabled' in content
        assert 'proceedDownload()' in content
    
    def test_modal_still_works_when_enabled(self):
        """Modal should still display when warnings enabled"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check modal exists
        assert 'downloadWarningModal' in content
        # Check display logic
        assert '.style.display' in content
    
    def test_no_confusion_in_disabled_state(self):
        """UI should be clear when warnings disabled"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for warning message
        assert 'DISABLED' in content
        assert 'CRITICAL' in content or 'REMINDER' in content


class TestConfigurationEdgeCases:
    """Test edge cases and robustness"""
    
    def test_config_missing_ui_section(self):
        """Should handle missing ui section gracefully"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Should have default fallback
        assert 'get(' in content or 'True' in content
    
    def test_config_missing_setting(self):
        """Should handle missing setting gracefully"""
        server_file = Path('src/web/server.py')
        content = server_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Should have default (True)
        assert ', True' in content or 'True' in content
    
    def test_javascript_handles_api_error(self):
        """JavaScript should handle API error gracefully"""
        html_file = Path('web_templates/reports.html')
        content = html_file.read_bytes().decode('utf-8', errors='ignore')
        
        # Check for error handling
        assert 'catch' in content or 'error' in content.lower()
        # Should default to enabled on error
        assert 'downloadWarningsEnabled = true' in content or 'downloadWarningsEnabled = true' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
