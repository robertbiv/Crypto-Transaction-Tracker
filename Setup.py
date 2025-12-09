import json
import os
import sys
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================
BASE_DIR = Path.cwd()
INPUT_DIR = BASE_DIR / 'inputs'
ARCHIVE_DIR = BASE_DIR / 'processed_archive'
OUTPUT_DIR = BASE_DIR / 'outputs'
LOG_DIR = OUTPUT_DIR / 'logs'
KEYS_FILE = BASE_DIR / 'api_keys.json'
WALLETS_FILE = BASE_DIR / 'wallets.json'

def create_folders():
    print("1. Creating Directory Structure...")
    folders = [INPUT_DIR, ARCHIVE_DIR, OUTPUT_DIR, LOG_DIR]
    for d in folders:
        if not d.exists():
            d.mkdir(parents=True)
            print(f"   -> Created: {d.name}/")
        else:
            print(f"   -> Exists:  {d.name}/")

def create_api_template():
    print("\n2. Checking API Keys Configuration...")
    if KEYS_FILE.exists():
        print("   -> 'api_keys.json' already exists. Skipping.")
        return

    data = {
        "_INSTRUCTIONS": "1. Enter Read-Only keys. 2. You can leave unused exchanges here; the script will ignore them if they still say 'PASTE_...'.",
        "coinbase": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_API_SECRET_HERE" },
        "kraken": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_PRIVATE_KEY_HERE" },
        "binanceus": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_SECRET_HERE" },
        "gemini": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_SECRET_HERE" },
        "cryptocom": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_SECRET_HERE" },
        "kucoin": { "apiKey": "PASTE_YOUR_API_KEY_HERE", "secret": "PASTE_YOUR_SECRET_HERE", "password": "PASTE_YOUR_PASSPHRASE_HERE" }
    }
    with open(KEYS_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    print("   -> Created template 'api_keys.json'. Please edit this file!")

def create_wallet_template():
    print("\n3. Checking Wallet Configuration...")
    if WALLETS_FILE.exists():
        print("   -> 'wallets.json' already exists. Skipping.")
        return

    data = {
        "_INSTRUCTIONS": "Paste PUBLIC addresses to audit holdings. Separate multiple addresses with commas.",
        "BTC": ["PASTE_BTC_ADDRESS_HERE"],
        "ETH": ["PASTE_ETH_ADDRESS_HERE"],
        "SOL": ["PASTE_SOL_ADDRESS_HERE"],
        "ADA": ["PASTE_CARDANO_ADDRESS_HERE"],
        "DOT": ["PASTE_POLKADOT_ADDRESS_HERE"]
    }
    with open(WALLETS_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    print("   -> Created template 'wallets.json'. Please edit this file!")

def main():
    print("========================================")
    print("   CRYPTO TAX ENVIRONMENT SETUP")
    print("========================================")
    
    create_folders()
    create_api_template()
    create_wallet_template()
    
    print("\n========================================")
    print("   SETUP COMPLETE")
    print("========================================")
    print("NEXT STEPS:")
    print("1. Open 'api_keys.json' and paste your exchange keys.")
    print("2. Open 'wallets.json' and paste your public addresses.")
    print("3. Run 'auto_runner.py' to start syncing.")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()