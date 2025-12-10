2. Initial SetupRun the setup script to generate your folder structure and configuration templates:python Setup.py
📂 The EcosystemThe script automatically builds and maintains this structure:/My_Crypto_Tax_Folder
# Crypto Tax Automation Engine (V21)

A self-hosted Python system for tracking cryptocurrency taxes across exchanges, wallets, and DeFi. Features include a resilient database with safety backups, automated ingestion from exchanges and wallets, price backfill, and year-over-year tax reporting (Export-compatible CSVs).

**Privacy Notice:** This tool runs locally and does not send telemetry to the developer. It communicates only with third-party services you configure (exchanges, Moralis, CoinGecko, etc.). Review each provider's privacy policy before use.

## APIs (examples)

- Moralis — EVM & Solana chain indexing (audit)
- Blockchair — Bitcoin & UTXO data
- CoinGecko — token metadata & stablecoin discovery
- Yahoo Finance — historical price backfill
- CCXT (exchanges) — Binance, Coinbase, Kraken, KuCoin, Bybit, OKX, Gate.io, and others

---

## Quick Start

1. Install requirements (Python 3.8+ recommended):

```pwsh
pip install pandas ccxt yfinance requests
```

2. Initialize the project structure and templates:

```pwsh
python Setup.py
```

3. Configure API keys and wallets:

- Edit `api_keys.json` and paste your exchange API keys (use read-only keys).
- Add public wallet addresses to `wallets.json` for the audit feature (Moralis / TokenView).

4. Run the Auto-Pilot (sync + reports):

```pwsh
python Auto_Runner.py
```

---

## Project layout

The runner creates and maintains these files/folders:

```
/My_Crypto_Tax_Folder
│
├── Setup.py                       # [USER] Run once to initialize folders/files
├── Auto_Runner.py                 # [USER] Run this to sync & update taxes
├── Crypto_Tax_Engine.py           # [CORE] The logic engine (do not delete)
│
├── api_keys.json                  # [USER] Your Exchange & Audit Keys
├── wallets.json                   # [USER] Your Public Addresses (For Audit)
├── config.json                    # [USER] Settings (Enable/Disable Audit, Backups)
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
```

---

## How it works (high level)

1. Ingestion → Database

- Reads CSVs from `inputs/` and ingest trades/ledgers via exchange APIs (CCXT).
- Saves records into `crypto_master.db` and archives processed CSVs.

2. Calculation → Reports

- The TaxEngine computes cost basis, gains, and income from the DB and exports:
    - `GENERIC_TAX_CAP_GAINS.csv` (capital gains)
    - `INCOME_REPORT.csv` (income items)
    - `EOY_HOLDINGS_SNAPSHOT.csv` or `CURRENT_HOLDINGS_DRAFT.csv`

3. Year handling

- Current year: Draft reports (updated each run).
- Past years: Finalized EOY snapshots are preserved.

4. Price fetching

- Stablecoins are detected and treated as $1.00.
- Missing historical prices are backfilled via Yahoo Finance.

---

## Inputs

- Automatic (APIs): Configure exchange keys in `api_keys.json`. The engine syncs trades, fees, and ledger entries (staking/rewards) where available.
- Manual (CSV): Drop files in `inputs/` with headers `date, coin, amount, usd_value_at_time, fee` and run the auto-runner.

---

## Outputs

Files are written under `outputs/Year_<YYYY>/`:

- `GENERIC_TAX_CAP_GAINS.csv` — upload to Export (Investments)
- `INCOME_REPORT.csv` — summary of income items
- `EOY_HOLDINGS_SNAPSHOT.csv` — permanent end-of-year snapshot
- `CURRENT_HOLDINGS_DRAFT.csv` — live draft holdings for the current year

Run logs are written to `outputs/logs/` with timestamped filenames and rotated backups. Older run logs are compressed and archived automatically.

---

## Resilience & safety

- Database backups: the engine keeps `.bak` copies before writes.
- Corruption recovery: corrupt DB files are moved to `CORRUPT_<DATE>.db` and a fresh DB is created.
- Network retries: exponential backoff for transient API/network failures.

---

## Troubleshooting

- "Configuration Missing": run `python Setup.py` first.
- "Database Locked": close other programs holding the DB (DB Browser, editors).
- Audit variances:
    - Negative variance: check for missing withdrawals or transfers.
    - Positive variance: may be staking rewards, airdrops, or unrecorded receipts — add a manual CSV if needed.

---

## Disclaimer

This software is provided "as-is" and does not constitute tax or legal advice. Verify all outputs and consult a qualified tax professional when necessary. The developer is not liable for errors or any tax consequences arising from use of this software.

---

If you'd like, I can also add:

- A short `README_QUICK.md` with only the commands and minimal steps,
- A `requirements.txt` file listing pinned package versions,
- Or expand the troubleshooting section with example fixes.
