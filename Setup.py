"""
================================================================================
SETUP (Legacy Entry Point) - Redirect to Modern Setup Tool
================================================================================

Legacy compatibility wrapper that redirects to the new setup.py location.

This file exists for backward compatibility with old documentation and scripts.
The actual setup wizard is now located at: src/tools/setup.py

Usage:
    python Setup.py          (legacy, still works)
    python src/tools/setup.py (new location)
    python cli.py setup      (recommended)

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

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
CONFIG_FILE = BASE_DIR / 'configs' / 'config.json'
REQUIRED_SCRIPTS = ["Crypto_Transaction_Engine.py", "Auto_Runner.py"] 
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
                elif isinstance(v, dict): # Nested merge for config sections
                    for sk, sv in v.items():
                        if sk not in existing[k]:
                            existing[k][sk] = sv
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
    print("--- SETUP (V30: US Transaction Compliance + HIFO Support) ---\n")
    check_dependencies()
    check_folders()
    
    # ====================================================================================
    # 1. API KEYS
    # ====================================================================================
    api_data = {
        "_INSTRUCTIONS": "Enter Read-Only keys. Moralis is REQUIRED for EVM/Solana audit. Blockchair is OPTIONAL (BTC/UTXO). If you don't have a key, leave as is.",
        
        # Audit Providers
        "moralis": {"apiKey": "PASTE_MORALIS_KEY_HERE"},
        "blockchair": {"apiKey": "PASTE_KEY_OPTIONAL_BUT_RECOMMENDED"},

        # Certified Exchanges (Pro Tier)
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

        # Supported Exchanges (Standard Tier)
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

    # ====================================================================================
    # 2. WALLETS (ALL CHAINS)
    # ====================================================================================
    wallet_data = {
        "_INSTRUCTIONS": "Paste PUBLIC addresses to audit. Use checksummed EVM addresses (0x...) for EVM chains and standard address formats for UTXO chains. To add multiple wallets for the same blockchain, provide a JSON array of addresses. Do NOT paste private keys.",
        
        # UTXO Chains (Blockchair)
        "bitcoin": {"addresses": ["PASTE_BTC_ADDRESS"]},
        "litecoin": {"addresses": ["PASTE_LTC_ADDRESS"]},
        "dogecoin": {"addresses": ["PASTE_DOGE_ADDRESS"]},
        "bitcoincash": {"addresses": ["PASTE_BCH_ADDRESS"]},
        "dash": {"addresses": ["PASTE_DASH_ADDRESS"]},
        "zcash": {"addresses": ["PASTE_ZEC_ADDRESS"]},
        "monero": {"addresses": ["PASTE_XMR_ADDRESS"]},
        "ripple": {"addresses": ["PASTE_XRP_ADDRESS"]},
        "cardano": {"addresses": ["PASTE_ADA_ADDRESS"]},
        "stellar": {"addresses": ["PASTE_XLM_ADDRESS"]},
        "eos": {"addresses": ["PASTE_EOS_ADDRESS"]},
        "tron": {"addresses": ["PASTE_TRX_ADDRESS"]},

        # EVM Chains (Moralis)
        "ethereum": {"addresses": ["PASTE_ETH_ADDRESS"]},
        "polygon": {"addresses": ["PASTE_MATIC_ADDRESS"]},
        "binance": {"addresses": ["PASTE_BSC_ADDRESS"]},
        "avalanche": {"addresses": ["PASTE_AVAX_ADDRESS"]},
        "fantom": {"addresses": ["PASTE_FANTOM_ADDRESS"]},
        "cronos": {"addresses": ["PASTE_CRONOS_ADDRESS"]},
        "arbitrum": {"addresses": ["PASTE_ARBITRUM_ADDRESS"]},
        "optimism": {"addresses": ["PASTE_OPTIMISM_ADDRESS"]},
        "gnosis": {"addresses": ["PASTE_GNOSIS_ADDRESS"]},
        "base": {"addresses": ["PASTE_BASE_ADDRESS"]},
        "pulsechain": {"addresses": ["PASTE_PULSE_ADDRESS"]},
        "linea": {"addresses": ["PASTE_LINEA_ADDRESS"]},
        "moonbeam": {"addresses": ["PASTE_MOONBEAM_ADDRESS"]},

        # Solana (Moralis)
        "solana": {"addresses": ["PASTE_SOL_ADDRESS"]}
    }
    validate_json(WALLETS_FILE, wallet_data)

    # ====================================================================================
    # 3. USER CONFIG (UPDATED FOR V30)
    # ====================================================================================
    config_data = {
        "_INSTRUCTIONS": "General runtime options. 'accounting.method': 'FIFO' (Default) or 'HIFO' (Not Recommended: may cause audit friction). 'general.run_audit using the public wallet keys (Enter in wallets.json)': True/False.",
        "general": {
            "run_audit": True,
            "create_db_backups": True
        },
        "accounting": {
            "method": "FIFO" 
        },
        "performance": {
            "respect_free_tier_limits": True,
            "api_timeout_seconds": 30
        },
        "logging": {
            "compress_older_than_days": 30
        },
        "compliance": {
            "_INSTRUCTIONS": "2025 IRS compliance controls. strict_broker_mode (Recommended=True) prevents basis borrowing across wallets for custodial sources (1099-DA alignment). broker_sources is the list of custodial sources. staking_transactionable_on_receipt (Recommended=True) controls constructive receipt for staking/mining; setting False is aggressive and may be challenged. defi_lp_conservative (Recommended=True) treats LP deposits as Reportable swaps (conservative); setting False marks them as non-Reportable deposits (aggressive, IRS may challenge). collectibles can be flagged via prefixes/tokens.",
            "strict_broker_mode": True,
            "broker_sources": ["COINBASE", "KRAKEN", "GEMINI", "BINANCE", "ROBINHOOD", "ETORO"],
            "staking_transactionable_on_receipt": True,
            "defi_lp_conservative": True,
            "collectible_prefixes": ["NFT-", "ART-"],
            "collectible_tokens": ["NFT", "PUNK", "BAYC"]
        },
        "staking": {
            "_INSTRUCTIONS": "staketaxcsv auto-import. Set enabled=True to auto-generate staking reward CSVs from all wallets in wallets.json, import into DB, and archive. Requires staketaxcsv CLI installed (pip install staketaxcsv). Supports all major staking protocols.",
            "enabled": False,
            "protocols_to_sync": ["all"]
        },
        "ui": {
            "download_warnings_enabled": True,
            "_INSTRUCTIONS": "download_warnings_enabled: Set to True to require users to acknowledge a warning before downloading tax reports. Recommended: True. If set to False, a persistent banner will remind users to always double-check all outputs and consult a tax professional."
        },
        "ml_fallback": {
            "_INSTRUCTIONS": "Optional ML fallback for ambiguous/unclassified transactions. enabled=True activates ML suggestions. model_name: 'shim' (keywords) or 'tinyllama' (real model). confidence_threshold (0.0-1.0): min score to log. auto_shutdown_after_batch: free model memory after processing each batch. batch_size: transactions per batch (lower = less RAM, higher = faster). OPTIMIZED FOR ARM NAS: batch_size=5 recommended for 8GB systems.",
            "enabled": True,
            "model_name": "tinyllama",
            "confidence_threshold": 0.85,
            "auto_shutdown_after_batch": True,
            "batch_size": 5
        },
        "accuracy_mode": {
            "_INSTRUCTIONS": "Enhanced accuracy features using TinyLLaMA model (1.1B parameters). Set enabled=True for context-aware analysis (fraud detection, smart descriptions, pattern learning). NLP search disabled. Set to False to use fast heuristics only. Requires ML enabled above. OPTIMIZED FOR ARM NAS with 8GB RAM (3-4GB available). Specs: ARM CPU / 8GB RAM minimum / runs on CPU.",
            "enabled": True,
            "fraud_detection": True,
            "smart_descriptions": True,
            "pattern_learning": True,
            "natural_language_search": False,
            "fallback_on_error": True,
            "recommended_specs": {
                "cpu": "ARM or x86 processor (4+ cores recommended)",
                "ram": "8GB minimum (3-4GB available for TinyLLaMA after OS/processes)",
                "gpu": "Not required - TinyLLaMA optimized for CPU inference",
                "storage": "2.5GB for TinyLLaMA model cache",
                "execution": "Local - All data stays on your machine - ARM NAS compatible"
            }
        },
        "anomaly_detection": {
            "_INSTRUCTIONS": "Configure anomaly detection sensitivity for AI-powered transaction analysis. Adjust thresholds to tune sensitivity. Higher values = less sensitive (fewer warnings). Lower values = more sensitive (more warnings). Recommended defaults work for most users.",
            "enabled": True,
            "price_error_threshold": 0.20,
            "_price_error_threshold_INFO": "Maximum price deviation (0.0-1.0) from market price before warning. Default: 0.20 (20%). Adjustable range: 0.05 (5% strict) to 0.50 (50% lenient).",
            "extreme_value_threshold": 3.0,
            "_extreme_value_threshold_INFO": "Statistical outlier threshold in standard deviations. Default: 3.0. Adjustable range: 2.0 (stricter) to 5.0 (more lenient).",
            "dust_threshold_usd": 0.10,
            "_dust_threshold_usd_INFO": "Minimum transaction value in USD to flag dust attacks. Default: $0.10. Adjustable range: $0.01 to $1.00.",
            "pattern_deviation_multiplier": 2.5,
            "_pattern_deviation_multiplier_INFO": "Pattern learning sensitivity. How many times above learned patterns triggers alert. Default: 2.5x. Adjustable range: 1.5x (stricter) to 4.0x (more lenient).",
            "min_transactions_for_learning": 20,
            "_min_transactions_for_learning_INFO": "Minimum transactions needed before pattern learning activates. Default: 20. Adjustable range: 10 to 100."
        },
        "audit_enhancements": {
            "_INSTRUCTIONS": "ENTERPRISE AUDIT FEATURES (Priority 2 & 3). Enables real-time monitoring, automatic responses, ML detection, and trend analysis. All features require Flask-Limiter and scikit-learn.",
            "enabled": True,
            "dashboard_widget": {
                "_INSTRUCTIONS": "Real-time audit integrity dashboard widget on web UI. Shows system integrity score, recent anomalies, and status.",
                "enabled": True,
                "refresh_interval_seconds": 30,
                "display_anomaly_count": 10
            },
            "log_rotation": {
                "_INSTRUCTIONS": "Automatic audit log rotation with gzip compression and archival. Prevents unbounded log growth.",
                "enabled": True,
                "max_file_size_mb": 10,
                "max_age_days": 30,
                "retention_days": 365,
                "compress": True,
                "archive_dir": "logs/archives",
                "maintenance_interval_hours": 6
            },
            "baseline_learning": {
                "_INSTRUCTIONS": "Auto-learn normal patterns from historical audit logs. Detects deviations and adapts baselines.",
                "enabled": True,
                "learning_period_days": 30,
                "min_samples_to_train": 100,
                "auto_update_interval_hours": 24,
                "drift_threshold": 0.3
            },
            "rate_limiting": {
                "_INSTRUCTIONS": "Rate limit all audit API endpoints to prevent abuse and DoS attacks.",
                "enabled": True,
                "dashboard_data_limit": "60 per hour",
                "rotation_status_limit": "30 per hour",
                "learn_baseline_limit": "5 per hour",
                "ml_train_limit": "5 per hour",
                "ml_detect_limit": "20 per hour"
            },
            "signature_verification": {
                "_INSTRUCTIONS": "HMAC-SHA256 signature verification on all audit log entries. Detects tampering.",
                "enabled": True,
                "signing_key": "GENERATE_SECURE_KEY_ON_FIRST_RUN",
                "algorithm": "SHA256",
                "verify_on_load": True,
                "dashboard_widget": True
            },
            "ml_anomaly_detection": {
                "_INSTRUCTIONS": "Machine learning-based anomaly detection using Isolation Forest. Requires scikit-learn.",
                "enabled": True,
                "model_type": "IsolationForest",
                "contamination_rate": 0.05,
                "training_threshold": 100,
                "auto_retrain_days": 7,
                "features": ["hour_of_day", "action_code", "user_code", "status", "details_size", "transaction_count", "anomaly_count"]
            },
            "automatic_responses": {
                "_INSTRUCTIONS": "Automatic incident response system. Locks operations on CRITICAL anomalies, creates incidents, escalates alerts.",
                "enabled": True,
                "lock_operations_on_critical": True,
                "default_lock_duration_minutes": 60,
                "create_incident_records": True,
                "escalate_to_admin": True,
                "create_forensic_snapshots": True,
                "severity_levels": {
                    "LOW": "Alert only",
                    "MEDIUM": "Alert + Snapshot",
                    "HIGH": "Alert + Escalate + Snapshot",
                    "CRITICAL": "Lock Operations + Escalate + Admin Notify"
                }
            },
            "comparative_analysis": {
                "_INSTRUCTIONS": "Historical trend analysis and reporting. Tracks integrity, anomalies, risk scores over time.",
                "enabled": True,
                "default_lookback_days": 30,
                "daily_aggregation": True,
                "hourly_aggregation": True,
                "generate_weekly_reports": True,
                "trend_metrics": ["integrity_score", "anomaly_frequency", "activity_correlation", "risk_score"]
            },
            "incident_management": {
                "_INSTRUCTIONS": "Incident recording, tracking, and forensics.",
                "incidents_dir": "outputs/incidents",
                "forensics_dir": "outputs/forensics",
                "reports_dir": "outputs/reports/comparative",
                "auto_cleanup_days": 90,
                "retention_policy": "Archive after 365 days"
            }
        }
    }
    validate_json(CONFIG_FILE, config_data)
    
    print("\n[DONE] Configuration files updated/created.")
    # Only ask for input if not running in wizard mode and is a TTY
    if os.environ.get('SETUP_WIZARD_MODE') != '1':
        try:
            if sys.stdin.isatty():
                input("\nPress Enter...")
        except:
            pass

if __name__ == "__main__":
    main()