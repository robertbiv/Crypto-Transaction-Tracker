import json
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================
BASE_DIR = Path.cwd()

# 1. Folders to Create
REQUIRED_DIRS = [
    BASE_DIR / 'inputs',
    BASE_DIR / 'processed_archive',
    BASE_DIR / 'outputs',
    BASE_DIR / 'outputs' / 'logs'
]

# 2. Config Files to Create
KEYS_FILE = BASE_DIR / 'api_keys.json'
WALLETS_FILE = BASE_DIR / 'wallets.json'

# 3. Scripts to Verify
REQUIRED_SCRIPTS = [
    "Crypto_Tax_Master_V18.py",
    "auto_runner.py"
]

# ==========================================
# LOGGING SYSTEM
# ==========================================
class DualLogger(object):
    def __init__(self):
        self.terminal = sys.stdout
        self.log_file = None
    
    def start(self):
        # Ensure log dir exists before creating log file
        log_dir = BASE_DIR / 'outputs' / 'logs'
        if not log_dir.exists():
            log_dir.mkdir(parents=True)
            
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = open(log_dir / f"Setup_Log_{timestamp}.txt", "a", encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        if self.log_file:
            self.log_file.write(message)
            self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        if self.log_file:
            self.log_file.flush()

# Redirect print statements to our logger
sys.stdout = DualLogger()

# ==========================================
# CORE LOGIC
# ==========================================
def check_folders():
    print("\n1. Checking Directory Structure...")
    # Initialize logger file AFTER verifying/creating output dir
    
    for d in REQUIRED_DIRS:
        if not d.exists():
            d.mkdir(parents=True)
            print(f"   [CREATED] {d.name}/")
        else:
            print(f"   [OK] {d.name}/ exists")
            
    # Now that folders exist, we can start file logging
    sys.stdout.start()

def check_scripts():
    print("\n2. Verifying Core Scripts...")
    missing = []
    for script_name in REQUIRED_SCRIPTS:
        f = BASE_DIR / script_name
        if f.exists():
            print(f"   [OK] Found {script_name}")
        else:
            print(f"   [MISSING] {script_name} NOT FOUND!")
            missing.append(script_name)
    
    if missing:
        print("\n   [CRITICAL WARNING] You are missing core python files.")
        print("   The automation will fail without them.")
        for m in missing: print(f"    - {m}")

def validate_and_create_json(filepath, default_data, name):
    print(f"\n3. Configuration: {name}...")
    
    if filepath.exists():
        # VALIDATION CHECK: Is it valid JSON?
        try:
            with open(filepath, 'r') as f:
                json.load(f)
            print(f"   [OK] '{filepath.name}' exists and is valid JSON. Skipping.")
            return # Safe to exit, file is good
        except json.JSONDecodeError:
            print(f"   [CORRUPT] '{filepath.name}' is corrupted or empty.")
            # Backup corrupt file
            ts = datetime.now().strftime("%Y%m%d%H%M%S")
            backup_name = f"{filepath.stem}_CORRUPT_{ts}.json"
            shutil.move(str(filepath), str(filepath.parent / backup_name))
            print(f"   [ACTION] Moved corrupt file to '{backup_name}'.")
            print(f"   [ACTION] Generating fresh template...")

    # Create Template (If missing or was just moved due to corruption)
    with open(filepath, 'w') as f:
        json.dump(default_data, f, indent=4)
    print(f"   [CREATED] Template '{filepath.name}'. Please edit this file!")

def main():
    print("========================================")
    print("   CRYPTO TAX ENVIRONMENT SETUP")
    print("========================================")
    
    # 1. Folders
    check_folders()
    
    # 2. Scripts
    check_scripts()
    
    # 3. API Keys Template
    api_data = {
        "_INSTRUCTIONS": "1. Enter Read-Only keys. 2. You can leave unused exchanges here; the script will ignore them if they still say 'PASTE_...'.",
        "coinbase": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_API_SECRET_HERE" },
        "kraken": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_PRIVATE_KEY_HERE" },
        "binanceus": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_SECRET_HERE" },
        "gemini": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_SECRET_HERE" },
        "cryptocom": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_SECRET_HERE" },
        "kucoin": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_SECRET_HERE", "password": "PASTE_YOUR_PASSPHRASE_HERE" }
    }
    validate_and_create_json(KEYS_FILE, api_data, "API Keys")

    # 4. Wallet Template
    wallet_data = {
        "_INSTRUCTIONS": "Paste PUBLIC addresses to audit holdings. Separate multiple addresses with commas.",
        "BTC": ["PASTE_BTC_ADDRESS_1", "PASTE_BTC_ADDRESS_2"],
        "ETH": ["PASTE_ETH_ADDRESS_HERE"],
        "SOL": ["PASTE_SOL_ADDRESS_HERE"],
        "ADA": ["PASTE_CARDANO_ADDRESS_HERE"],
        "DOT": ["PASTE_POLKADOT_ADDRESS_HERE"],
        "XRP": ["PASTE_RIPPLE_ADDRESS_HERE"],
        "DOGE": ["PASTE_DOGE_ADDRESS_HERE"],
        "AVAX": ["PASTE_AVALANCHE_ADDRESS_HERE"],
        "MATIC": ["PASTE_POLYGON_ADDRESS_HERE"],
        "LTC": ["PASTE_LITECOIN_ADDRESS_HERE"]
    }
    validate_and_create_json(WALLETS_FILE, wallet_data, "Wallets")
    
    print("\n========================================")
    print("   SETUP COMPLETE")
    print("========================================")
    print(f"Log saved to: outputs/logs/Setup_Log_....txt")
    print("NEXT STEPS:")
    print("1. Open 'api_keys.json' -> Paste Exchange Keys.")
    print("2. Open 'wallets.json'  -> Paste Wallet Addresses.")
    print("3. Run 'auto_runner.py' -> Sit back and relax.")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()