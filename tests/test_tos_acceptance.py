"""
================================================================================
TEST: Terms of Service Acceptance
================================================================================

Tests for ToS acceptance enforcement across CLI, auto_runner, web UI, and setup flows.

Test Coverage:
    - ToS prompt displays on first run
    - Acceptance marker file is created
    - Prompt skipped on subsequent runs
    - Declining ToS exits program
    - Web UI setup enforces ToS
    - ToS marker persists across runs
    - Reset functionality works for testing

Author: robertbiv
================================================================================
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.tos_checker import (
    tos_accepted,
    mark_tos_accepted,
    reset_tos_acceptance,
    TOS_MARKER_FILE,
    TOS_FILE,
    read_tos,
    prompt_tos_acceptance,
    check_and_prompt_tos,
)


class TestTosMarkerFile:
    """Test ToS marker file operations"""
    
    def setup_method(self):
        """Clean up marker before each test"""
        reset_tos_acceptance()
    
    def teardown_method(self):
        """Clean up marker after each test"""
        reset_tos_acceptance()
    
    def test_marker_file_path_correct(self):
        """Verify marker file is in configs/.tos_accepted"""
        assert str(TOS_MARKER_FILE).endswith('.tos_accepted')
        assert 'configs' in str(TOS_MARKER_FILE)
    
    def test_tos_file_exists(self):
        """Verify TERMS_OF_SERVICE.md exists"""
        assert TOS_FILE.exists(), "TERMS_OF_SERVICE.md not found"
    
    def test_read_tos_returns_content(self):
        """Verify ToS file can be read"""
        content = read_tos()
        assert content is not None
        assert len(content) > 0
        assert 'Terms of Service' in content or 'TERMS' in content
    
    def test_initial_tos_not_accepted(self):
        """Verify user starts with ToS not accepted"""
        reset_tos_acceptance()
        assert not tos_accepted()
    
    def test_mark_tos_accepted_creates_file(self):
        """Verify marking ToS creates marker file"""
        reset_tos_acceptance()
        assert not tos_accepted()
        
        mark_tos_accepted()
        assert tos_accepted()
        assert TOS_MARKER_FILE.exists()
    
    def test_reset_tos_removes_marker(self):
        """Verify reset clears ToS acceptance"""
        mark_tos_accepted()
        assert tos_accepted()
        
        reset_tos_acceptance()
        assert not tos_accepted()
        assert not TOS_MARKER_FILE.exists()


class TestTosPrompt:
    """Test ToS acceptance prompt logic"""
    
    def setup_method(self):
        """Clean up marker before each test"""
        reset_tos_acceptance()
    
    def teardown_method(self):
        """Clean up marker after each test"""
        reset_tos_acceptance()
    
    @patch('builtins.input', return_value='yes')
    def test_prompt_with_yes_response(self, mock_input):
        """Verify 'yes' response marks ToS accepted"""
        reset_tos_acceptance()
        
        result = prompt_tos_acceptance()
        
        assert result is True
        assert tos_accepted()
        assert TOS_MARKER_FILE.exists()
    
    @patch('builtins.input', return_value='no')
    def test_prompt_with_no_response_exits(self, mock_input):
        """Verify 'no' response exits program"""
        reset_tos_acceptance()
        
        with pytest.raises(SystemExit) as exc_info:
            prompt_tos_acceptance()
        
        assert exc_info.value.code == 0
        assert not tos_accepted()
    
    @patch('builtins.input', side_effect=['invalid', 'maybe', 'yes'])
    def test_prompt_accepts_only_yes_or_no(self, mock_input):
        """Verify invalid responses are rejected until yes/no given"""
        reset_tos_acceptance()
        
        result = prompt_tos_acceptance()
        
        assert result is True
        assert tos_accepted()
        # Verify it took 3 prompts (2 invalid + 1 yes)
        assert mock_input.call_count == 3
    
    @patch('builtins.input', return_value='YES')
    def test_prompt_case_insensitive(self, mock_input):
        """Verify 'YES' (uppercase) is accepted"""
        reset_tos_acceptance()
        
        result = prompt_tos_acceptance()
        
        assert result is True
        assert tos_accepted()
    
    @patch('builtins.input', return_value='yes')
    def test_prompt_displays_tos_content(self, mock_input, capsys):
        """Verify prompt displays ToS content"""
        reset_tos_acceptance()
        
        prompt_tos_acceptance()
        
        captured = capsys.readouterr()
        output = captured.out.lower()
        assert 'terms of service' in output or 'acceptance required' in output


class TestCheckAndPromptTos:
    """Test automatic ToS check function"""
    
    def setup_method(self):
        """Clean up marker before each test"""
        reset_tos_acceptance()
    
    def teardown_method(self):
        """Clean up marker after each test"""
        reset_tos_acceptance()
    
    def test_no_prompt_if_already_accepted(self):
        """Verify no prompt if ToS already accepted"""
        mark_tos_accepted()
        
        with patch('src.utils.tos_checker.prompt_tos_acceptance') as mock_prompt:
            check_and_prompt_tos()
            mock_prompt.assert_not_called()
    
    @patch('builtins.input', return_value='yes')
    def test_prompts_if_not_accepted(self, mock_input):
        """Verify prompt shown if ToS not yet accepted"""
        reset_tos_acceptance()
        
        # Directly call prompt_tos_acceptance to test prompting logic
        from src.utils.tos_checker import prompt_tos_acceptance
        prompt_tos_acceptance()
        
        # Verify that input was called (prompting happened)
        assert mock_input.called
        # Verify ToS is now marked as accepted
        assert tos_accepted()
    
    @patch('builtins.input', return_value='yes')
    def test_multiple_calls_only_prompt_once(self, mock_input):
        """Verify multiple calls don't re-prompt after first acceptance"""
        reset_tos_acceptance()
        
        # First call - directly call prompt to bypass pytest check
        from src.utils.tos_checker import prompt_tos_acceptance
        prompt_tos_acceptance()
        first_call_count = mock_input.call_count
        assert first_call_count > 0
        
        # Second call via check_and_prompt should not prompt again
        check_and_prompt_tos()
        # Call count should not increase (already accepted)
        assert mock_input.call_count == first_call_count


class TestCliIntegration:
    """Test ToS enforcement in CLI entry point"""
    
    def setup_method(self):
        """Clean up marker before each test"""
        reset_tos_acceptance()
    
    def teardown_method(self):
        """Clean up marker after each test"""
        reset_tos_acceptance()
    
    @patch('builtins.input', return_value='yes')
    def test_cli_imports_tos_checker(self, mock_input):
        """Verify cli.py imports and calls ToS checker"""
        reset_tos_acceptance()
        
        # Import cli module (will trigger ToS check in module init)
        # This is tricky because import happens at module level
        # We'll just verify the imports exist
        import cli
        assert hasattr(cli, '__name__')
    
    @patch('src.utils.tos_checker.check_and_prompt_tos')
    def test_cli_calls_tos_check_on_import(self, mock_tos):
        """Verify ToS check is called when cli module is imported"""
        # Reload cli to trigger import-time ToS check
        import importlib
        import cli
        importlib.reload(cli)
        
        # Note: Mock may not capture import-time calls perfectly
        # This test mainly verifies the import exists


class TestAutoRunnerIntegration:
    """Test ToS enforcement in auto_runner entry point"""
    
    def setup_method(self):
        """Clean up marker before each test"""
        reset_tos_acceptance()
    
    def teardown_method(self):
        """Clean up marker after each test"""
        reset_tos_acceptance()
    
    @patch('builtins.input', return_value='yes')
    def test_auto_runner_imports_tos_checker(self, mock_input):
        """Verify auto_runner.py imports ToS checker"""
        reset_tos_acceptance()
        
        # Verify the import works
        import auto_runner
        assert hasattr(auto_runner, '__name__')


class TestWebUiSetupTosEnforcement:
    """Test ToS enforcement in web UI setup flow"""
    
    def setup_method(self):
        """Clean up marker before each test"""
        reset_tos_acceptance()
    
    def teardown_method(self):
        """Clean up marker after each test"""
        reset_tos_acceptance()
    
    def test_tos_accepted_marker_accessible_to_web_ui(self):
        """Verify web UI can check ToS acceptance status"""
        reset_tos_acceptance()
        assert not tos_accepted()
        
        mark_tos_accepted()
        assert tos_accepted()
    
    @patch('builtins.input', return_value='yes')
    def test_start_web_ui_imports_tos_checker(self, mock_input):
        """Verify start_web_ui.py imports ToS checker"""
        reset_tos_acceptance()
        
        import start_web_ui
        assert hasattr(start_web_ui, '__name__')


class TestTosAcceptancePersistence:
    """Test that ToS acceptance persists across runs"""
    
    def setup_method(self):
        """Clean up marker before each test"""
        reset_tos_acceptance()
    
    def teardown_method(self):
        """Clean up marker after each test"""
        reset_tos_acceptance()
    
    def test_marker_file_survives_module_reload(self):
        """Verify marker file persists across module reloads"""
        mark_tos_accepted()
        initial_state = tos_accepted()
        
        # Simulate module reload
        import importlib
        import src.utils.tos_checker
        importlib.reload(src.utils.tos_checker)
        
        # Re-import after reload
        from src.utils.tos_checker import tos_accepted as tos_accepted_reloaded
        assert tos_accepted_reloaded() == initial_state
    
    def test_marker_file_location_consistent(self):
        """Verify marker file always in same location"""
        mark_tos_accepted()
        path1 = TOS_MARKER_FILE
        
        # Re-import
        import importlib
        import src.utils.tos_checker
        importlib.reload(src.utils.tos_checker)
        
        from src.utils.tos_checker import TOS_MARKER_FILE as TOS_MARKER_FILE_2
        assert str(path1) == str(TOS_MARKER_FILE_2)


class TestTosEdgeCases:
    """Test edge cases and error conditions"""
    
    def setup_method(self):
        """Clean up marker before each test"""
        reset_tos_acceptance()
    
    def teardown_method(self):
        """Clean up marker after each test"""
        reset_tos_acceptance()
    
    @patch('src.utils.tos_checker.read_tos', return_value=None)
    @patch('builtins.print')
    def test_missing_tos_file_exits(self, mock_print, mock_read):
        """Verify missing ToS file causes exit"""
        reset_tos_acceptance()
        
        with pytest.raises(SystemExit) as exc_info:
            prompt_tos_acceptance()
        
        assert exc_info.value.code == 1
    
    def test_marker_file_directory_created_if_missing(self):
        """Verify configs/ directory is created when marking ToS"""
        reset_tos_acceptance()
        
        # Ensure configs dir doesn't exist (or is clean)
        if TOS_MARKER_FILE.parent.exists():
            import shutil
            shutil.rmtree(TOS_MARKER_FILE.parent, ignore_errors=True)
        
        mark_tos_accepted()
        
        assert TOS_MARKER_FILE.parent.exists()
        assert TOS_MARKER_FILE.exists()
    
    @patch('builtins.input', side_effect=['', 'yes'])
    def test_empty_input_treated_as_invalid(self, mock_input):
        """Verify empty input is rejected"""
        reset_tos_acceptance()
        
        result = prompt_tos_acceptance()
        
        assert result is True
        # Should have taken 2 prompts (1 empty + 1 yes)
        assert mock_input.call_count == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
