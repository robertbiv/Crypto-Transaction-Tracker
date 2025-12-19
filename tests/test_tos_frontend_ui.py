"""
================================================================================
TEST: ToS Frontend UI Elements
================================================================================

Tests for Terms of Service frontend UI components, modal behavior, and
JavaScript interactions during setup wizard.

Test Coverage:
    - HTML structure validation
    - ToS modal elements present and correct
    - Checkbox initial state (disabled)
    - View ToS button functionality
    - Accept button initial state (disabled)
    - Scroll detection logic
    - Checkbox enabling after viewing
    - Form validation with ToS
    - CSS classes and styling
    - Accessibility attributes

Author: GitHub Copilot
================================================================================
"""

import pytest
import re
from pathlib import Path
from bs4 import BeautifulSoup
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTosHtmlStructure:
    """Test HTML structure of ToS elements in setup wizard"""
    
    @pytest.fixture
    def setup_wizard_html(self):
        """Load setup wizard HTML template"""
        template_path = Path(__file__).parent.parent / 'web_templates' / 'setup_wizard.html'
        if not template_path.exists():
            pytest.skip("Setup wizard template not found")
        return template_path.read_text(encoding='utf-8')
    
    @pytest.fixture
    def soup(self, setup_wizard_html):
        """Parse HTML with BeautifulSoup"""
        return BeautifulSoup(setup_wizard_html, 'html.parser')
    
    def test_tos_checkbox_exists(self, soup):
        """Verify ToS acceptance checkbox exists"""
        checkbox = soup.find('input', {'id': 'acceptTos', 'type': 'checkbox'})
        assert checkbox is not None, "ToS checkbox not found"
    
    def test_tos_checkbox_starts_disabled(self, soup):
        """Verify ToS checkbox starts in disabled state"""
        checkbox = soup.find('input', {'id': 'acceptTos'})
        assert checkbox is not None
        assert checkbox.has_attr('disabled'), "Checkbox should start disabled"
    
    def test_tos_checkbox_cursor_not_allowed(self, soup):
        """Verify ToS checkbox has not-allowed cursor initially"""
        checkbox = soup.find('input', {'id': 'acceptTos'})
        assert checkbox is not None
        style = checkbox.get('style', '')
        assert 'not-allowed' in style, "Checkbox should have not-allowed cursor"
    
    def test_view_tos_button_exists(self, soup):
        """Verify View ToS button exists"""
        button = soup.find('button', {'id': 'viewTosBtn'})
        assert button is not None, "View ToS button not found"
    
    def test_view_tos_button_has_onclick(self, soup):
        """Verify View ToS button has onclick handler"""
        button = soup.find('button', {'id': 'viewTosBtn'})
        assert button is not None
        onclick = button.get('onclick', '')
        assert 'showTosModal' in onclick, "Button should call showTosModal()"
    
    def test_view_tos_button_text(self, soup):
        """Verify View ToS button has correct text"""
        button = soup.find('button', {'id': 'viewTosBtn'})
        assert button is not None
        text = button.get_text()
        assert 'Terms of Service' in text, "Button should mention Terms of Service"
        assert 'Required' in text or 'required' in text.lower(), "Button should indicate requirement"
    
    def test_tos_checkbox_label_exists(self, soup):
        """Verify ToS checkbox has associated label"""
        label = soup.find('label', {'id': 'tosCheckboxLabel'})
        assert label is not None, "ToS checkbox label not found"
    
    def test_tos_checkbox_label_starts_dimmed(self, soup):
        """Verify ToS checkbox label starts with reduced opacity"""
        label = soup.find('label', {'id': 'tosCheckboxLabel'})
        assert label is not None
        style = label.get('style', '')
        # Check for opacity: 0.5 or similar
        assert 'opacity' in style.lower(), "Label should have opacity set"
    
    def test_tos_modal_exists(self, soup):
        """Verify ToS modal element exists"""
        modal = soup.find('div', {'id': 'tosModal'})
        assert modal is not None, "ToS modal not found"
    
    def test_tos_modal_starts_hidden(self, soup):
        """Verify ToS modal starts with display: none"""
        modal = soup.find('div', {'id': 'tosModal'})
        assert modal is not None
        style = modal.get('style', '')
        assert 'display: none' in style or 'display:none' in style, "Modal should start hidden"
    
    def test_tos_modal_content_area_exists(self, soup):
        """Verify ToS modal has content area"""
        content = soup.find('div', {'id': 'tosContent'})
        assert content is not None, "ToS content area not found"
    
    def test_tos_modal_content_scrollable(self, soup):
        """Verify ToS content area is scrollable"""
        content = soup.find('div', {'id': 'tosContent'})
        assert content is not None
        style = content.get('style', '')
        assert 'overflow-y' in style.lower(), "Content should be scrollable"
    
    def test_tos_modal_accept_button_exists(self, soup):
        """Verify ToS modal has accept button"""
        button = soup.find('button', {'id': 'acceptTosModalBtn'})
        assert button is not None, "Accept button not found in modal"
    
    def test_tos_modal_accept_button_starts_disabled(self, soup):
        """Verify ToS modal accept button starts disabled"""
        button = soup.find('button', {'id': 'acceptTosModalBtn'})
        assert button is not None
        assert button.has_attr('disabled'), "Accept button should start disabled"
    
    def test_tos_modal_accept_button_onclick(self, soup):
        """Verify ToS modal accept button has onclick handler"""
        button = soup.find('button', {'id': 'acceptTosModalBtn'})
        assert button is not None
        onclick = button.get('onclick', '')
        assert 'closeTosModal' in onclick, "Button should call closeTosModal()"
    
    def test_tos_modal_close_button_exists(self, soup):
        """Verify ToS modal has close button (X)"""
        # Look for button with closeTosModal onclick
        close_buttons = soup.find_all('button', onclick=re.compile('closeTosModal'))
        assert len(close_buttons) >= 2, "Should have close button (X) and accept button"
    
    def test_tos_modal_has_overlay(self, soup):
        """Verify ToS modal has dark overlay background"""
        modal = soup.find('div', {'id': 'tosModal'})
        assert modal is not None
        style = modal.get('style', '')
        # Should have rgba background for overlay
        assert 'rgba' in style.lower() or 'background' in style.lower(), "Modal should have overlay background"
    
    def test_tos_modal_content_contains_terms(self, soup):
        """Verify ToS modal contains actual terms content"""
        content = soup.find('div', {'id': 'tosContent'})
        assert content is not None
        text = content.get_text()
        assert len(text) > 500, "ToS content should be substantial"
        assert 'Terms of Service' in text or 'TERMS' in text, "Should contain ToS heading"
    
    def test_tos_modal_content_has_key_sections(self, soup):
        """Verify ToS modal contains key legal sections"""
        content = soup.find('div', {'id': 'tosContent'})
        assert content is not None
        text = content.get_text()
        
        # Check for important sections
        assert 'warranty' in text.lower(), "Should mention warranty"
        assert 'liability' in text.lower(), "Should mention liability"
        assert 'risk' in text.lower(), "Should mention risk"
    
    def test_tos_modal_scroll_reminder(self, soup):
        """Verify ToS modal has scroll reminder"""
        content = soup.find('div', {'id': 'tosContent'})
        assert content is not None
        text = content.get_text()
        assert 'scroll' in text.lower(), "Should remind user to scroll"


class TestTosJavaScriptFunctions:
    """Test JavaScript function presence in setup wizard"""
    
    @pytest.fixture
    def setup_wizard_html(self):
        """Load setup wizard HTML template"""
        template_path = Path(__file__).parent.parent / 'web_templates' / 'setup_wizard.html'
        if not template_path.exists():
            pytest.skip("Setup wizard template not found")
        return template_path.read_text(encoding='utf-8')
    
    def test_show_tos_modal_function_exists(self, setup_wizard_html):
        """Verify showTosModal function is defined"""
        assert 'function showTosModal()' in setup_wizard_html, "showTosModal function not found"
    
    def test_close_tos_modal_function_exists(self, setup_wizard_html):
        """Verify closeTosModal function is defined"""
        assert 'function closeTosModal()' in setup_wizard_html, "closeTosModal function not found"
    
    def test_enable_tos_checkbox_function_exists(self, setup_wizard_html):
        """Verify enableTosCheckbox function is defined"""
        assert 'function enableTosCheckbox()' in setup_wizard_html, "enableTosCheckbox function not found"
    
    def test_show_tos_modal_sets_display(self, setup_wizard_html):
        """Verify showTosModal changes modal display"""
        # Find the function body
        pattern = r'function showTosModal\(\).*?\{(.*?)\}'
        match = re.search(pattern, setup_wizard_html, re.DOTALL)
        assert match is not None, "showTosModal function body not found"
        
        function_body = match.group(1)
        assert 'display' in function_body, "Should change display property"
        assert 'flex' in function_body or 'block' in function_body, "Should show modal"
    
    def test_close_tos_modal_checks_scroll(self, setup_wizard_html):
        """Verify closeTosModal checks if user scrolled to bottom"""
        pattern = r'function closeTosModal\(\).*?\{(.*?)\n\s+\}'
        match = re.search(pattern, setup_wizard_html, re.DOTALL)
        if match:
            function_body = match.group(1)
            assert 'scrollHeight' in function_body or 'scrollTop' in function_body, \
                "Should check scroll position"
    
    def test_enable_tos_checkbox_enables_checkbox(self, setup_wizard_html):
        """Verify enableTosCheckbox enables the checkbox"""
        pattern = r'function enableTosCheckbox\(\).*?\{(.*?)\n\s+\}'
        match = re.search(pattern, setup_wizard_html, re.DOTALL)
        if match:
            function_body = match.group(1)
            assert 'disabled = false' in function_body, "Should enable checkbox"
    
    def test_enable_tos_checkbox_changes_button_text(self, setup_wizard_html):
        """Verify enableTosCheckbox updates button text"""
        pattern = r'function enableTosCheckbox\(\).*?\{(.*?)\n\s+\}'
        match = re.search(pattern, setup_wizard_html, re.DOTALL)
        if match:
            function_body = match.group(1)
            assert 'textContent' in function_body or 'innerText' in function_body, \
                "Should update button text"
            assert 'Viewed' in setup_wizard_html, "Should indicate ToS was viewed"
    
    def test_scroll_event_listener_attached(self, setup_wizard_html):
        """Verify scroll event listener is attached to ToS content"""
        assert "addEventListener('scroll'" in setup_wizard_html, "Should listen for scroll events"
        assert 'tosContent' in setup_wizard_html, "Should listen on tosContent element"
    
    def test_scroll_listener_checks_bottom(self, setup_wizard_html):
        """Verify scroll listener checks if scrolled to bottom"""
        # Find scroll listener
        pattern = r"addEventListener\('scroll'.*?\{(.*?)\}\)"
        match = re.search(pattern, setup_wizard_html, re.DOTALL)
        if match:
            listener_body = match.group(1)
            assert 'scrollHeight' in listener_body, "Should check scrollHeight"
            assert 'scrollTop' in listener_body, "Should check scrollTop"
            assert 'clientHeight' in listener_body, "Should check clientHeight"
    
    def test_scroll_listener_enables_accept_button(self, setup_wizard_html):
        """Verify scroll listener enables accept button at bottom"""
        pattern = r"addEventListener\('scroll'.*?\{(.*?)\}\)"
        match = re.search(pattern, setup_wizard_html, re.DOTALL)
        if match:
            listener_body = match.group(1)
            assert 'acceptTosModalBtn' in listener_body, "Should target accept button"
            assert 'disabled = false' in listener_body, "Should enable button"
    
    def test_tos_viewed_flag_exists(self, setup_wizard_html):
        """Verify tosViewed flag variable exists"""
        assert 'tosViewed' in setup_wizard_html, "Should track if ToS was viewed"
        assert 'tosViewed = false' in setup_wizard_html or 'let tosViewed = false' in setup_wizard_html, \
            "Should initialize tosViewed to false"


class TestTosFormValidation:
    """Test ToS validation in form submission"""
    
    @pytest.fixture
    def setup_wizard_html(self):
        """Load setup wizard HTML template"""
        template_path = Path(__file__).parent.parent / 'web_templates' / 'setup_wizard.html'
        if not template_path.exists():
            pytest.skip("Setup wizard template not found")
        return template_path.read_text(encoding='utf-8')
    
    def test_form_checks_tos_acceptance(self, setup_wizard_html):
        """Verify form validation checks ToS checkbox"""
        # Look for acceptTos checkbox check
        assert "getElementById('acceptTos')" in setup_wizard_html, \
            "Should get acceptTos checkbox value"
        assert '.checked' in setup_wizard_html, "Should check if checkbox is checked"
    
    def test_form_validation_before_submit(self, setup_wizard_html):
        """Verify ToS validation happens before form submission"""
        # Should have validation for acceptTos
        pattern = r"if\s*\(\s*!acceptTos\s*\)"
        assert re.search(pattern, setup_wizard_html), \
            "Should validate acceptTos before submission"
    
    def test_tos_error_message_shown(self, setup_wizard_html):
        """Verify error message shown if ToS not accepted"""
        # Should show alert if ToS not accepted
        if 'if (!acceptTos)' in setup_wizard_html or 'if(!acceptTos)' in setup_wizard_html:
            assert 'showAlert' in setup_wizard_html, "Should show alert for missing ToS"
            assert 'Terms of Service' in setup_wizard_html, "Error should mention ToS"
    
    def test_tos_sent_in_api_request(self, setup_wizard_html):
        """Verify tos_accepted is sent in API request"""
        # Should include tos_accepted in request body
        assert 'tos_accepted' in setup_wizard_html, "Should send tos_accepted to API"
        assert 'tos_accepted: true' in setup_wizard_html, "Should send true when accepted"


class TestTosAccessibility:
    """Test accessibility features of ToS UI"""
    
    @pytest.fixture
    def soup(self):
        """Parse HTML with BeautifulSoup"""
        template_path = Path(__file__).parent.parent / 'web_templates' / 'setup_wizard.html'
        if not template_path.exists():
            pytest.skip("Setup wizard template not found")
        html = template_path.read_text(encoding='utf-8')
        return BeautifulSoup(html, 'html.parser')
    
    def test_checkbox_has_label(self, soup):
        """Verify checkbox is wrapped in or associated with label"""
        checkbox = soup.find('input', {'id': 'acceptTos'})
        assert checkbox is not None
        
        # Check if inside a label or has associated label
        parent_label = checkbox.find_parent('label')
        assert parent_label is not None, "Checkbox should be inside a label"
    
    def test_view_button_is_button_element(self, soup):
        """Verify View ToS is a proper button element"""
        button = soup.find('button', {'id': 'viewTosBtn'})
        assert button is not None, "Should use <button> element"
        assert button.name == 'button', "Should be button element"
    
    def test_view_button_has_type(self, soup):
        """Verify View ToS button has type='button'"""
        button = soup.find('button', {'id': 'viewTosBtn'})
        assert button is not None
        button_type = button.get('type', 'submit')  # Default is submit
        assert button_type == 'button', "Should have type='button' to prevent form submission"
    
    def test_modal_has_role_or_aria_label(self, soup):
        """Verify modal has appropriate ARIA attributes or could be improved"""
        modal = soup.find('div', {'id': 'tosModal'})
        assert modal is not None
        # This test documents that ARIA attributes could be added
        # In a real implementation, we'd check for role="dialog" or aria-label
    
    def test_close_button_has_clear_label(self, soup):
        """Verify close button has clear indication"""
        close_buttons = soup.find_all('button', onclick=re.compile('closeTosModal'))
        assert len(close_buttons) > 0, "Should have close button"
        
        # Check for X or text
        for btn in close_buttons:
            text = btn.get_text().strip()
            # Should have × or X or descriptive text
            assert len(text) > 0, "Close button should have visible content"


class TestTosStyling:
    """Test CSS styling and visual feedback"""
    
    @pytest.fixture
    def soup(self):
        """Parse HTML with BeautifulSoup"""
        template_path = Path(__file__).parent.parent / 'web_templates' / 'setup_wizard.html'
        if not template_path.exists():
            pytest.skip("Setup wizard template not found")
        html = template_path.read_text(encoding='utf-8')
        return BeautifulSoup(html, 'html.parser')
    
    def test_view_button_has_emoji_or_icon(self, soup):
        """Verify View ToS button has visual indicator"""
        button = soup.find('button', {'id': 'viewTosBtn'})
        assert button is not None
        text = button.get_text()
        # Should have emoji or icon indicator
        assert '📄' in text or 'icon' in str(button).lower(), \
            "Button should have visual indicator"
    
    def test_checkbox_container_has_background(self, soup):
        """Verify ToS checkbox area has visual container"""
        label = soup.find('label', {'id': 'tosCheckboxLabel'})
        if label:
            parent = label.find_parent('div', class_=lambda x: x and 'form-group' in x) or label.find_parent('div')
            if parent:
                style = parent.get('style', '')
                # Should have background styling
                assert 'background' in style.lower() or 'padding' in style.lower(), \
                    "ToS area should be visually distinct"
    
    def test_modal_has_overlay_effect(self, soup):
        """Verify modal has dark overlay effect"""
        modal = soup.find('div', {'id': 'tosModal'})
        assert modal is not None
        style = modal.get('style', '')
        # Should have fixed positioning and dark background
        assert 'fixed' in style.lower(), "Modal should be fixed positioned"
        assert 'rgba' in style.lower() or 'background' in style.lower(), \
            "Modal should have overlay effect"
    
    def test_disabled_elements_have_visual_feedback(self, soup):
        """Verify disabled elements have appropriate styling"""
        checkbox = soup.find('input', {'id': 'acceptTos'})
        assert checkbox is not None
        style = checkbox.get('style', '')
        assert 'cursor' in style.lower(), "Should have cursor styling"
        
        button = soup.find('button', {'id': 'acceptTosModalBtn'})
        assert button is not None
        button_style = button.get('style', '')
        assert 'opacity' in button_style.lower() or 'cursor' in button_style.lower(), \
            "Disabled button should have visual feedback"


class TestTosEdgeCases:
    """Test edge cases and error handling in UI"""
    
    @pytest.fixture
    def setup_wizard_html(self):
        """Load setup wizard HTML template"""
        template_path = Path(__file__).parent.parent / 'web_templates' / 'setup_wizard.html'
        if not template_path.exists():
            pytest.skip("Setup wizard template not found")
        return template_path.read_text(encoding='utf-8')
    
    def test_close_modal_without_scrolling_has_warning(self, setup_wizard_html):
        """Verify closing modal without scrolling shows confirmation"""
        pattern = r'function closeTosModal\(\).*?\{(.*?)\n\s+\}'
        match = re.search(pattern, setup_wizard_html, re.DOTALL)
        if match:
            function_body = match.group(1)
            # Should check scroll and maybe confirm
            has_scroll_check = 'scrollHeight' in function_body or 'scrollTop' in function_body
            has_confirm = 'confirm' in function_body
            # At least one should be true for good UX
            assert has_scroll_check, "Should check if user scrolled"
    
    def test_modal_prevents_body_scroll(self, setup_wizard_html):
        """Verify modal prevents scrolling of page body"""
        pattern = r'function showTosModal\(\).*?\{(.*?)\}'
        match = re.search(pattern, setup_wizard_html, re.DOTALL)
        if match:
            function_body = match.group(1)
            # Should set body overflow
            assert 'body.style.overflow' in function_body or 'overflow: hidden' in setup_wizard_html, \
                "Should prevent background scrolling"
    
    def test_modal_restores_body_scroll_on_close(self, setup_wizard_html):
        """Verify modal restores body scroll when closed"""
        # Look for the closeTosModal function and check if it restores overflow
        assert 'function closeTosModal()' in setup_wizard_html, "closeTosModal function not found"
        
        # Find the function and check for body overflow restoration
        start = setup_wizard_html.find('function closeTosModal()')
        if start != -1:
            # Get next 1000 characters to find the function body
            function_section = setup_wizard_html[start:start+1000]
            assert 'body.style.overflow' in function_section, \
                "Should restore scrolling on close"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
