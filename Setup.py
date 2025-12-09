import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = Path.cwd()
REQUIRED_DIRS = [BASE_DIR/'inputs', BASE_DIR/'processed_archive', BASE_DIR/'outputs', BASE_DIR/'outputs'/'logs']
KEYS_FILE = BASE_DIR/'api_keys.json'
WALLETS_FILE = BASE_DIR/'wallets.json'
CONFIG_FILE = BASE_DIR/'config.json'
REQUIRED_SCRIPTS = ["Crypto_Tax_Master_V20.py", "auto_runner.py"] 
REQUIRED_PACKAGES = {"pandas":"pandas", "ccxt":"ccxt", "yfinance":"yfinance", "requests":"requests"}

class DualLogger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log_file = None
    def start(self):
        log_dir = BASE_DIR/'outputs'/'logs'
        if not log_dir.exists(): log_dir.mkdir(parents=True)
        self.log_file = open(log_dir/f"Setup_Log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt", "a", encoding='utf-8')
    def write(self, m):
        self.terminal.write(m)
        if self.log_file: self.log_file.write(m)
    def flush(self): self.terminal.flush()

sys.stdout = DualLogger()

def check_dependencies():
    print("1. Dependencies...")
    missing = []
    for lib, pip in REQUIRED_PACKAGES.items():
        try: __import__(lib)
        except: missing.append(pip)
    if missing:
        print(f"   [MISSING] Run: pip install {' '.join(missing)}")
        sys.exit(1)

def check_folders():
    print("\n2. Folders...")
    for d in REQUIRED_DIRS:
        if not d.exists(): d.mkdir(parents=True); print(f"   [CREATED] {d.name}/")
    sys.stdout.start()

def validate_json(fp, default):
    if fp.exists():
        try: 
            with open(fp) as f: json.load(f)
            return
        except: shutil.move(str(fp), str(fp.parent/f"{fp.stem}_CORRUPT.json"))
    with open(fp, 'w') as f: json.dump(default, f, indent=4)
    print(f"   [CREATED] {fp.name}")

def main():
    print("--- SETUP (V20) ---")
    check_dependencies()
    check_folders()
    
    # 1. API Keys
    api_data = {
        "_INSTRUCTIONS": "Enter Read-Only keys. Keys with 'PASTE_' are ignored. NOTE: TokenView Key is REQUIRED if 'run_audit' is True in config.json.",
        "coinbase": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "kraken": {"apiKey": "PASTE_KEY", "secret": "PASTE_PRIVATE_KEY"},
        "tokenview": {"apiKey": "PASTE_YOUR_TOKENVIEW_KEY_HERE"}
    }
    validate_json(KEYS_FILE, api_data)

    # 2. Wallets
    wallet_data = {
        "_INSTRUCTIONS": "Paste PUBLIC addresses to audit. Supports 100+ chains via TokenView.",
        "BTC": ["PASTE_BTC_ADDRESS"],
        "ETH": ["PASTE_ETH_ADDRESS"],
        "SOL": ["PASTE_SOL_ADDRESS"]
    }
    validate_json(WALLETS_FILE, wallet_data)

    # 3. User Config (NEW)
    config_data = {
        "_INSTRUCTIONS": "If 'run_audit' is true, you MUST provide a TokenView key in api_keys.json.",
        "general": {
            "run_audit": True,
            "create_db_backups": True
        },
        "performance": {
            "respect_free_tier_limits": True,
            "api_timeout_seconds": 30
        }
    }
    validate_json(CONFIG_FILE, config_data)
    
    print("\n[DONE] Configuration files created. You can edit 'config.json' to change settings.")
    input("\nPress Enter...")

if __name__ == "__main__":
    main()