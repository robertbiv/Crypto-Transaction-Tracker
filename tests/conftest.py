"""
================================================================================
PYTEST CONFIGURATION
================================================================================

Pytest configuration and shared fixtures for the entire test suite.

Global Fixtures:
    - isolated_test_environment: Copies entire project to temp dir for tests
    - set_test_mode: Automatically sets TEST_MODE=1 for faster API retries
    - cleanup_global_database: Removes crypto_master.db before test session

Test Isolation Strategy:
    All tests run from a complete copy of the project in a temporary directory.
    This ensures zero writes to the real project directories during test runs.

Author: robertbiv
================================================================================
"""
import os
import sys
import pytest
from pathlib import Path
import shutil
import tempfile
import fnmatch

# Ensure project root is on sys.path for legacy module imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Global to track our temp directory
_TEST_PROJECT_DIR = None
_ORIGINAL_CWD = None

def pytest_configure(config):
    """
    Hook called before test collection starts.
    Set up isolated environment BEFORE any test modules are imported.
    Only copies files that would be in git (respects .gitignore).
    """
    global _TEST_PROJECT_DIR, _ORIGINAL_CWD
    
    # Set environment variables immediately
    os.environ['TEST_MODE'] = '1'
    os.environ['PYTEST_RUNNING'] = '1'
    
    # Create temp directory
    _TEST_PROJECT_DIR = Path(tempfile.mkdtemp(prefix="crypto_taxes_test_"))
    
    # Load .gitignore patterns
    gitignore_patterns = set()
    gitignore_file = PROJECT_ROOT / '.gitignore'
    if gitignore_file.exists():
        for line in gitignore_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                gitignore_patterns.add(line)
    
    # Always exclude git metadata and pytest cache
    gitignore_patterns.update({'.git', '.pytest_cache', '.github'})
    
    def should_ignore(path):
        """Check if path matches any gitignore pattern"""
        rel_path = path.relative_to(PROJECT_ROOT)
        path_str = str(rel_path).replace('\\', '/')
        
        for pattern in gitignore_patterns:
            is_dir_only = pattern.endswith('/')
            clean_pattern = pattern.rstrip('/')
            
            # Handle directory-only patterns (e.g. 'inputs/')
            if is_dir_only:
                # Check if any part of the path matches the pattern
                # If it's a parent directory, it's definitely a dir
                for i, part in enumerate(rel_path.parts):
                    if part == clean_pattern or fnmatch.fnmatch(part, clean_pattern):
                        # If it's an intermediate part, it's a directory -> ignore
                        if i < len(rel_path.parts) - 1:
                            return True
                        # If it's the last part, check if it is actually a directory
                        if path.is_dir():
                            return True
                continue

            # Handle file/dir patterns (e.g. 'config.json', '*.pyc', 'node_modules')
            
            # Check exact path match
            if path_str == pattern:
                return True
                
            # Check filename match
            if rel_path.name == pattern:
                return True
                
            # Check wildcard match on path or name
            if '*' in pattern:
                if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(rel_path.name, pattern):
                    return True
            
            # Check if any part matches (e.g. 'node_modules' matches 'src/node_modules')
            for part in rel_path.parts:
                if part == pattern:
                    return True
                if '*' in pattern and fnmatch.fnmatch(part, pattern):
                    return True
                    
        return False
    
    # Copy project files that aren't gitignored
    for item in PROJECT_ROOT.iterdir():
        if should_ignore(item):
            continue
        dest = _TEST_PROJECT_DIR / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dest, ignore=lambda d, files: 
                              [f for f in files if should_ignore(Path(d) / f)])
            else:
                shutil.copy2(item, dest)
        except Exception:
            pass
            
    # Generate default config.json (simulating setup.py)
    # This ensures tests run with a clean, valid config without relying on local files
    config_dir = _TEST_PROJECT_DIR / 'configs'
    config_dir.mkdir(parents=True, exist_ok=True)
    
    default_config = {
        "general": {
            "run_audit": True,
            "create_db_backups": True
        },
        "accounting": {
            "method": "FIFO",
            "include_fees_in_basis": True
        },
        "compliance": {
            "strict_broker_mode": True,
            "broker_sources": ["COINBASE", "KRAKEN", "GEMINI", "BINANCE", "ROBINHOOD", "ETORO"],
            "staking_taxable_on_receipt": True,
            "defi_lp_conservative": True,
            "collectible_prefixes": ["NFT-", "ART-"],
            "collectible_tokens": ["NFT", "PUNK", "BAYC"]
        },
        "api": {
            "retry_attempts": 3,
            "timeout_seconds": 10
        },
        "ui": {
            "download_warnings_enabled": True,
            "_INSTRUCTIONS": "Recommended: keep download_warnings_enabled=True. Consult a tax professional before disabling."
        }
    }
    
    import json
    (config_dir / 'config.json').write_text(json.dumps(default_config, indent=4))
    
    # Change working directory BEFORE test collection
    _ORIGINAL_CWD = os.getcwd()
    os.chdir(_TEST_PROJECT_DIR)
    
    # Update sys.path
    sys.path.insert(0, str(_TEST_PROJECT_DIR))

def pytest_unconfigure(config):
    """
    Hook called after all tests finish.
    Restore original directory and clean up.
    """
    global _TEST_PROJECT_DIR, _ORIGINAL_CWD
    
    # Restore directory
    if _ORIGINAL_CWD:
        os.chdir(_ORIGINAL_CWD)
    
    # Remove from sys.path
    if _TEST_PROJECT_DIR and str(_TEST_PROJECT_DIR) in sys.path:
        sys.path.remove(str(_TEST_PROJECT_DIR))
    
    # Clean up temp directory
    if _TEST_PROJECT_DIR and _TEST_PROJECT_DIR.exists():
        try:
            shutil.rmtree(_TEST_PROJECT_DIR)
        except Exception:
            pass
    
    # Clean up environment
    if 'TEST_MODE' in os.environ:
        del os.environ['TEST_MODE']
    if 'PYTEST_RUNNING' in os.environ:
        del os.environ['PYTEST_RUNNING']



@pytest.fixture(scope="session", autouse=True)
def cleanup_global_database():
    """Remove global database in temp project copy to ensure clean state."""
    # Since we're running from temp copy, clean up there
    global_db = Path.cwd() / 'crypto_master.db'
    if global_db.exists():
        global_db.unlink()
    yield
    if global_db.exists():
        global_db.unlink()

@pytest.fixture(autouse=True)
def ensure_test_directories():
    """
    Ensure required directories exist in the temp project copy.
    Since we're running from a complete temp copy, just ensure basic dirs.
    """
    required_dirs = [
        Path('outputs/logs'),
        Path('outputs/backups'),
        Path('outputs/Year_2023'),
        Path('outputs/Year_2024'),
        Path('outputs/Year_2025'),
        Path('processed_archive'),
        Path('inputs'),
        Path('keys'),
        Path('configs'),
        Path('certs'),
    ]
    
    for d in required_dirs:
        d.mkdir(parents=True, exist_ok=True)
    
    yield


# ---------------------------------------------------------------------------
# TinyLLaMA feature fixtures (accurate mode)
# ---------------------------------------------------------------------------

@pytest.fixture
def fraud_detector():
    from src.advanced_ml_features_accurate import FraudDetectorAccurate
    return FraudDetectorAccurate(fallback_enabled=True)


@pytest.fixture
def smart_description_gen():
    from src.advanced_ml_features_accurate import SmartDescriptionGeneratorAccurate
    return SmartDescriptionGeneratorAccurate(fallback_enabled=True)


@pytest.fixture
def pattern_learner():
    from src.advanced_ml_features_accurate import PatternLearnerAccurate
    return PatternLearnerAccurate(fallback_enabled=True)


@pytest.fixture
def anomaly_detector():
    from src.anomaly_detector import AnomalyDetector
    return AnomalyDetector()


@pytest.fixture
def all_features(fraud_detector, smart_description_gen, pattern_learner, anomaly_detector):
    return {
        'fraud_detector': fraud_detector,
        'description_gen': smart_description_gen,
        'pattern_learner': pattern_learner,
        'anomaly_detector': anomaly_detector,
    }


