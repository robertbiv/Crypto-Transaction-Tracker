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
REQUIRED_SCRIPTS = ["Crypto_Tax_Engine.py", "Auto_Runner.py"] 
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
            with open(fp) as f: 
                existing = json.load(f)
            # Merge defaults into existing to ensure new supported keys appear
            updated = False
            for k, v in default.items():
                if k not in existing:
                    existing[k] = v
                    updated = True
            if updated:
                with open(fp, 'w') as f: json.dump(existing, f, indent=4)
                print(f"   [UPDATED] {fp.name} (Added new templates)")
            else:
                print(f"   [EXISTS] {fp.name}")
            return
        except: 
            shutil.move(str(fp), str(fp.parent/f"{fp.stem}_CORRUPT.json"))
            print(f"   [CORRUPT] Moved old {fp.name} to backup.")
            
    with open(fp, 'w') as f: json.dump(default, f, indent=4)
    print(f"   [CREATED] {fp.name}")

def main():
    print("--- SETUP (V21) ---\n")
    check_dependencies()
    check_folders()
    
    # --- 1. API Keys (Full List) ---
    # Includes Moralis (Required for EVM/Solana audit) and Blockchair (Optional)
    # Plus every Certified/Supported Exchange
    api_data = {
        "_INSTRUCTIONS": "Enter Read-Only keys. Moralis is REQUIRED for Audit (EVM/Solana). Blockchair is OPTIONAL (BTC/UTXO).",
        
        # --- AUDIT PROVIDERS ---
        "moralis": {"apiKey": "PASTE_MORALIS_KEY_HERE"},
        "blockchair": {"apiKey": "PASTE_KEY_OPTIONAL_BUT_RECOMMENDED"},

        # --- CERTIFIED EXCHANGES (Pro Tier) ---
        "binance": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "binanceus": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "bybit": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "okx": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET", "password": "PASTE_PASSWORD"},
        "gateio": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "kucoin": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET", "password": "PASTE_PASSWORD"},
        "bitget": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "bitmex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "htx": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "mexc": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "bingx": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "bitmart": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "cryptocom": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "coinex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "hyperliquid": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "woox": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "hashkey": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "phemex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "upbit": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "whitebit": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "deribit": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "kraken": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "coinbase": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "onetrading": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "blofin": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "paradex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "oxfun": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},

        # --- SUPPORTED EXCHANGES (Standard Tier) ---
        "alpaca": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "apex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "ascendex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "bitfinex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "bitflyer": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "bithumb": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "bitstamp": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "bittrex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "bitvavo": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "blockchaincom": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "cex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "coincheck": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "coinmate": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "coinone": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "coinspot": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "dydx": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "gemini": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "hitbtc": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "hollaex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "idex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "independentreserve": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "latoken": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "lbank": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "luno": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "ndax": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "novadax": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "oceanex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "poloniex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "probit": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "timex": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "tokocrypto": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "wavesexchange": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "xt": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "yobit": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "zaif": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"},
        "zonda": {"apiKey": "PASTE_KEY", "secret": "PASTE_SECRET"}
    }
    validate_json(KEYS_FILE, api_data)

    # --- 2. Wallets (All Chains) ---
    wallet_data = {
        "_INSTRUCTIONS": "Paste PUBLIC addresses to audit. Use Moralis (EVM/SOL) and Blockchair (BTC/UTXO).",
        
        # --- UTXO CHAINS (Blockchair) ---
        "BTC": ["PASTE_BTC_ADDRESS"],
        "LTC": ["PASTE_LTC_ADDRESS"],
        "DOGE": ["PASTE_DOGE_ADDRESS"],
        "BCH": ["PASTE_BCH_ADDRESS"],
        "DASH": ["PASTE_DASH_ADDRESS"],
        "ZEC": ["PASTE_ZEC_ADDRESS"],
        "XMR": ["PASTE_XMR_ADDRESS"], # Note: XMR Audit often requires view key, basic explorer might fail
        "XRP": ["PASTE_XRP_ADDRESS"],
        "ADA": ["PASTE_ADA_ADDRESS"],
        "XLM": ["PASTE_XLM_ADDRESS"],
        "EOS": ["PASTE_EOS_ADDRESS"],
        "TRX": ["PASTE_TRX_ADDRESS"],

        # --- EVM CHAINS (Moralis) ---
        "ETH": ["PASTE_ETH_ADDRESS"],
        "MATIC": ["PASTE_MATIC_ADDRESS"],
        "BNB": ["PASTE_BSC_ADDRESS"],
        "AVAX": ["PASTE_AVAX_ADDRESS"],
        "FTM": ["PASTE_FANTOM_ADDRESS"],
        "CRO": ["PASTE_CRONOS_ADDRESS"],
        "ARBITRUM": ["PASTE_ARBITRUM_ADDRESS"],
        "OPTIMISM": ["PASTE_OPTIMISM_ADDRESS"],
        "GNOSIS": ["PASTE_GNOSIS_ADDRESS"],
        "BASE": ["PASTE_BASE_ADDRESS"],
        "PULSE": ["PASTE_PULSE_ADDRESS"],
        "LINEA": ["PASTE_LINEA_ADDRESS"],
        "MOONBEAM": ["PASTE_MOONBEAM_ADDRESS"],

        # --- SOLANA (Moralis) ---
        "SOL": ["PASTE_SOL_ADDRESS"]
    }
    validate_json(WALLETS_FILE, wallet_data)

    # --- 3. User Config ---
    config_data = {
        "_INSTRUCTIONS": "To run Audit, you need a Moralis Key in api_keys.json.",
        "general": {
            "run_audit": True,
            "create_db_backups": True
        },
        "performance": {
            "respect_free_tier_limits": True,
            "api_timeout_seconds": 30
        },
        "logging": {
            "compress_older_than_days": 30
        }
    }
    validate_json(CONFIG_FILE, config_data)
    
    print("\n[DONE] Configuration files updated/created.")
    input("\nPress Enter...")

if __name__ == "__main__":
    main()