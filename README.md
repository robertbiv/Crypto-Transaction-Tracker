🛡️ Crypto Tax Automation Engine (V18)
A fully automated, self-hosted Python system for tracking cryptocurrency taxes across exchanges, wallets, and DeFi. It features self-healing databases, network resilience, automated backups, and year-over-year tax reporting (TurboTax compatible). This program sends no telematry data except for anything that the api maintainers collect. 
APIs Used and their Privacy Policies:


🚀 Quick Start
1. Install RequirementsYou need Python installed. Open your terminal or command prompt and run: 

pip install pandas ccxt yfinance requests

2. Initial Setup
Run the setup script to generate your folder structure and configuration templates:python setup_env.py
This will create the inputs, outputs, and logs folders, as well as api_keys.json and wallets.json.

3. Configure Your Keys 
These CANNOT make transactions on your behalf. Use Read-Only just in case of your computer getting compromised.
Open api_keys.json: Paste your Read-Only API keys for Coinbase, Kraken, etc.
Open wallets.json: Paste your public wallet addresses (BTC, ETH, SOL) for the audit feature.

4. Run the Auto-Pilot
To sync your data and generate reports, simply double-click or run:python auto_runner.py

📂 The Ecosystem
The script automatically builds and maintains this structure.

/My_Crypto_Tax_Folder
│
├── setup_env.py                   # [USER] Run once to initialize folders/files
├── auto_runner.py                 # [USER] Run this to sync & update taxes
├── Crypto_Tax_Master_V18.py       # [CORE] The logic engine (do not delete)
│
├── api_keys.json                  # [USER] Your Exchange Keys
├── wallets.json                   # [USER] Your Public Addresses (For Audit)
│
├── crypto_master.db               # [AUTO] The permanent database
├── crypto_master.db.bak           # [AUTO] Safety backup (Last known good state)
├── stablecoins_cache.json         # [AUTO] Cached list of stablecoins
│
├── inputs/                        # [USER] Drop manual CSVs here (MoonPay, etc.)
├── processed_archive/             # [AUTO] Old CSVs move here after processing
│
└── outputs/
    ├── logs/                      # [AUTO] Timestamped text logs of every run
    ├── Year_2024/                 # [AUTO] Finalized Tax Reports
    └── Year_2025/                 # [AUTO] Live/Draft Tax Reports


🧠 How It Works

1. The "Two-Step" Data Flow

Step 1: Ingestion (Files & API) -> Database
The script reads new CSVs from inputs/ and new Trades from APIs.
It saves them to crypto_master.db.
It moves processed CSVs to processed_archive/ so they aren't read twice.

Step 2: Calculation (Database) -> Reports
The Tax Engine calculates taxes by reading only from the Database.
This ensures instant recalculations without re-downloading history.

2. Year-Over-Year "Safety Lock"

The script intelligently handles tax years:
Current Year (e.g. 2025): Runs in Draft Mode. It overwrites the 2025 folder every time you run it to show "Year-to-Date" estimates. It saves CURRENT_HOLDINGS_DRAFT.csv.
Past Year (e.g. 2024): If the current date is Jan 1st, 2025 or later, the script runs the Final Report. It saves EOY_HOLDINGS_SNAPSHOT.csv. This file is your permanent record.

3. Smart Price Fetching

Stablecoins: Automatically detects stablecoins (USDC, DAI, PYUSD) and assigns them $1.00.
Volatile Coins: If a price is missing (e.g., from a staking reward), it queries Yahoo Finance for the historical price on that specific day and saves it to the database.

📥 Inputting Data

Automatic (API)
Supported: Coinbase, Kraken, Binance, Gemini, Crypto.com, KuCoin, Bybit.

How: Add keys to api_keys.json. The script handles Trades and Staking Rewards automatically.

Manual (CSV)
Supported: MoonPay, Ramp, Transak, PayPal, Ledger Live, Trezor.

How: Download the CSV receipt. Rename headers to match: date, coin, amount, usd_value_at_time, fee.

Action: Drop file in inputs/. Run auto_runner.py.

📊 The Outputs

Go to outputs/Year_XXXX/:
File Name
Usage
TURBOTAX_CAP_GAINS.csv

Upload to TurboTax "Investments" section.
INCOME_REPORT.csv
Type the "Total Sum" into "Misc Income" (Schedule 1).
EOY_HOLDINGS_SNAPSHOT.csv
Keep Safe. Your "Bank Statement" for Dec 31st.

MASTER_LEDGER.csv - (Optional) A raw list of every calculated transaction for auditing.

🛡️ Resilience & Safety Features

Self-Healing Database: Before every write operation, the script makes a .bak copy. If the script crashes or the internet dies mid-sync, it keeps the backup as a restore point.

Corruption Recovery: If crypto_master.db becomes unreadable, the script automatically moves it to CORRUPT_DATE.db and creates a fresh database to keep you running.

Network Retry: If an API times out or your internet flickers, the script waits 2s, 4s, then 8s and retries automatically before giving up.

🆘 Troubleshooting

"Configuration Missing": You tried to run auto_runner.py before setup_env.py. Run setup first.
"Database Locked": Close any other programs (like DB Browser) that have the database file open.
"Variance Mismatch" (Audit):
Negative Variance: You spent crypto (or transferred it) and didn't log it. The DB thinks you have it; Blockchain says you don't. Check for missing withdrawals.
Positive Variance: You received a reward/gift/airdrop that the API missed. Add a manual CSV to inputs/.