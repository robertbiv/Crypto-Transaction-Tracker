"""
================================================================================
ToS ACCEPTANCE CHECKER
================================================================================

Module for managing Terms of Service acceptance and enforcement.

Stores acceptance state in a local marker file to ensure users explicitly
accept the ToS before running the engine.

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

import os
import sys
from pathlib import Path


# Resolve paths relative to project root to avoid cwd issues in containers
BASE_DIR = Path(__file__).resolve().parents[2]
TOS_MARKER_FILE = BASE_DIR / "configs" / ".tos_accepted"
TOS_FILE = BASE_DIR / "TERMS_OF_SERVICE.md"


def read_tos():
    """Read the Terms of Service file."""
    try:
        with open(TOS_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"ERROR: {TOS_FILE} not found.")
        return None


def tos_accepted():
    """Check if user has accepted the ToS."""
    return TOS_MARKER_FILE.exists()


def mark_tos_accepted():
    """Create marker file to record ToS acceptance."""
    TOS_MARKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOS_MARKER_FILE.touch()


def reset_tos_acceptance():
    """Clear ToS acceptance marker (for testing or re-acceptance)."""
    if TOS_MARKER_FILE.exists():
        TOS_MARKER_FILE.unlink()


def prompt_tos_acceptance():
    """
    Display ToS to user and prompt for acceptance.
    
    Returns:
        True if user accepts, False/exits if user declines.
    """
    tos_content = read_tos()
    if not tos_content:
        print("Cannot display ToS. Exiting.")
        sys.exit(1)
    
    print("\n" + "="*80)
    print("TERMS OF SERVICE - PLEASE READ CAREFULLY")
    print("="*80 + "\n")
    
    # Display ToS (could paginate for long content)
    print(tos_content)
    
    print("\n" + "="*80)
    print("ACCEPTANCE REQUIRED")
    print("="*80 + "\n")
    
    while True:
        response = input(
            "Do you accept these Terms of Service? (type 'yes' to accept, 'no' to exit): "
        ).strip().lower()
        
        if response == 'yes':
            mark_tos_accepted()
            print("\n✓ Terms of Service accepted. You may now use the Program.")
            return True
        elif response == 'no':
            print("\n✗ You have declined the Terms of Service. Exiting.")
            sys.exit(0)
        else:
            print("Please enter 'yes' or 'no'.")


def check_and_prompt_tos():
    """
    Check if ToS has been accepted; if not, prompt user.
    
    Call this early in main entry points (CLI, web UI, auto runner).
    
    Skips prompting if running under pytest.
    """
    # Skip ToS check during pytest runs to avoid stdin capture issues
    if 'pytest' in sys.modules:
        return
    
    if not tos_accepted():
        prompt_tos_acceptance()
