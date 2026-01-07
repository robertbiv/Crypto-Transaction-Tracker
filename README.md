# **🛡️ Crypto Transaction Tracker**

Personal, self-hosted tooling to aggregate and review your crypto activity with a strong focus on privacy, safety, and rich visibility. It runs locally, ships with a modern web UI, and includes ML/AI helpers for smarter descriptions and anomaly spotting. Use it to centralize trades, transfers, staking rewards, and holdings across exchanges and chains.

**Privacy & Safety First:** Local-only by design—do **not** expose it to the internet. No telemetry. API keys and wallet data are stored encrypted at rest, but host security, access control, and backups are your responsibility.

## **🐳 Docker Deployment (NAS Ready)**

**NEW:** Multi-architecture Docker support for NAS devices!
- 🏗️ **Multi-Platform**: Supports both ARM64 (aarch64) and x86_64 (AMD64)
- 📦 **Easy Deploy**: One-command setup with docker-compose
- 🔄 **Auto-Restart**: Container automatically restarts on failure
- 💾 **Persistent Data**: All configs and outputs saved to volumes
- 🏥 **Health Checks**: Built-in monitoring and health endpoints
- 🎯 **NAS Optimized**: Works on Synology, QNAP, Asustor, **UGREEN**, and more

**Quick Start (Docker):**

Create `docker-compose.yml`:
```yaml
version: '3.8'
services:
  crypto-tracker:
    image: robertbiv/crypto-tracker:latest
    container_name: crypto-transaction-tracker
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - ./crypto-configs:/app/configs
      - ./crypto-inputs:/app/inputs
      - ./crypto-outputs:/app/outputs
      - ./crypto-archive:/app/processed_archive
      - ./crypto-certs:/app/certs
    environment:
      - TZ=UTC
      - PYTHONUNBUFFERED=1
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
```

Then run:
```bash
docker-compose up -d
# Access at https://YOUR_NAS_IP:5000
```

**NAS Deployment Guides:**
- 🟠 **UGREEN, Synology, QNAP & More** → [docs/NAS_DEPLOYMENT.md](docs/NAS_DEPLOYMENT.md)

Or see [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md) for general Docker setup.

**Supported Platforms:**
- **ARM**: Synology DS220+/920+, QNAP TS-x53D, Raspberry Pi 4/5
- **x86**: Most Intel/AMD NAS devices (Synology, QNAP, Asustor)

See [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md) for 5-minute setup or [DOCKER.md](DOCKER.md) for complete documentation.

## **🌐 Web UI**

**NEW:** Self-hosted web interface with Material Design 3!
- 🔐 **Secure**: HTTPS with self-signed certificates
- 🔒 **Encrypted**: All API operations encrypted end-to-end
- 🛡️ **Protected**: CSRF protection and request signing
- 🏠 **Local-Only**: Intended for localhost/LAN; do not expose publicly
- 📱 **Mobile-Ready**: Responsive design for all devices
- 🎨 **Modern UI**: Google Material Design 3

**Quick Start (Web UI):**
```bash
pip install -r requirements.txt
python Setup.py                # Creates configs/, wallets, api keys placeholders
python start_web_ui.py         # Launches HTTPS web UI + first-time setup wizard
```

Access at **https://localhost:5000**. On first launch you will:
- Create the admin account (stored locally)
- Review and accept the Terms of Service in-app
- Optionally add API keys and wallets (read-only keys only)

See [docs/CLI_GUIDE.md](docs/CLI_GUIDE.md) for command-line usage; the Web UI includes inline help and onboarding.

## **🧭 CLI Parity**

- Full feature parity with the web interface: transactions (list/add/update/delete/upload/reprocess), reports/warnings/stats, config + wallets + API keys, backups/restores, logs, diagnostics/health, scheduling, and accuracy/ML controls.
- Colorized output and friendly errors; everything scriptable for automation or CI.
- Start here for automation: [docs/CLI_GUIDE.md](docs/CLI_GUIDE.md)

## **🌟 What It’s Good At**

- **Full Transaction Tracking:** Ingest trades, transfers, staking rewards, and holdings across exchanges and wallets; consolidate into a single view with audit-friendly CSVs.
- **Modern Web UI:** Material Design 3, mobile-friendly, HTTPS (self-signed), request signing, CSRF protection, onboarding wizard, download safety prompts.
- **ML / AI Helpers:** Optional classifiers and description generators to make transaction labels clearer; anomaly detection to highlight unusual patterns. (Install `requirements-ml.txt` for these.)
- **Privacy by Default:** Local-only, no telemetry, keys encrypted at rest. You own your data; keep it on machines you control.
- **Safety Rails:** Backup-before-write patterns, rate limiting, request signing, and reminders to use read-only API keys. Designed for localhost/LAN—never expose to the public internet.

### **Reporting & Analysis**
- Unified CSV exports for transactions, holdings snapshots, and review warnings.
- Wallet/API health checks and basic reconciliation aids.
- Optional FBAR-style max-balance view and wash-sale/warning heuristics for review.

### **Basic Transaction Outputs (Small Footprint)**
- Provides FIFO/HIFO cost basis options and produces CSVs compatible with common Transaction workflows.
- Aligned loosely to 2025 US guidance but **not guaranteed accurate or complete**. Treat results as a starting point and validate with a qualified tax professional.

## **⚠️ Limitations & Responsibilities**

- Not a CPA or Transaction authority. All outputs (including any Transaction-oriented CSVs) must be reviewed and validated by you and a qualified professional.
- Complex edge cases (constructive sales, nuanced DeFi/NFT flows, specific-ID lot selection) are not fully automated; manual review is required.
- ML/AI features can misclassify—treat suggestions as hints, not truth.
- Data safety still depends on your host: enforce OS-level access controls, backups, and network isolation. Do not expose the app to the public internet.

### **HIFO Note (Optional, Higher Risk)**
- FIFO is the safer default. HIFO is available but requires specific identification records. If you cannot produce them, Transaction recalculation risk increases.

## **⚠️ Risky Settings & Warnings**

The app flags settings that raise reconciliation or audit risk. Use defaults unless you know why you’re changing them:

- **strict_broker_mode (keep enabled):** Prevents cross-wallet basis borrowing that can create broker mismatches.
- **staking_transactionable_on_receipt (keep enabled):** Turning off defers recognition and increases Transaction-position risk.
- **HIFO (optional, riskier):** Needs specific-ID evidence; otherwise FIFO is safer.

See `config.json` for inline notes. The setup wizard and engine emit warnings when risky options are enabled.

## **📂 The Ecosystem**

The repo layout (post-setup) looks like this:

```
/Crypto Transactions
│
├── README.md                       # Project overview and operations guide
├── requirements.txt                # Python dependencies
├── Setup.py                        # Initialize folders/files
├── cli.py                          # CLI entry point for common tasks
├── auto_runner.py                  # Sync, process, and generate Transaction reports
├── start_web_ui.py                 # Launch self-hosted web UI
├── web_server.py                   # Legacy web server entrypoint
├── Crypto_Transaction_Engine.py            # Core Transaction engine (imported by scripts)
├── Transaction_Reviewer.py                 # Manual review assistant entrypoint
├── docs/
│   ├── CLI_GUIDE.md                # Command-line usage guide
│   └── CODING_STANDARDS.md         # Project-wide documentation/header standards
├── api_keys_encrypted.json         # Encrypted exchange/API credentials
├── wallets_encrypted.json          # Encrypted wallet/address book
├── stablecoins_cache.json          # Cached stablecoin list
├── configs/
│   ├── config.json                 # User settings
│   ├── cached_token_addresses.json # Token metadata cache
│   └── stablecoins_cache.json      # Stablecoin list cache
├── inputs/                         # Drop manual CSVs here
├── outputs/
│   ├── logs/                       # Run logs
│   ├── Year_2024/                  # Year-specific reports
│   └── Year_2025/
├── processed_archive/              # Archived processed inputs
├── src/
│   ├── core/                       # Engine, database, encryption, reviewer
│   ├── tools/                      # Setup and review fixer utilities
│   ├── utils/                      # Config, logger, constants
│   └── web/                        # Web server components
├── tests/
│   ├── conftest.py                 # Pytest session config
│   ├── generate_stress_test_data.py# Stress-test data generator
│   ├── verify_stress_test.py       # Stress-test verification runner
│   ├── split_tests.py              # Legacy splitter utility
│   ├── test_comprehensive_scenarios.py # Full end-to-end scenarios
│   └── ... focused test modules (compliance, ingest, UI, etc.)
├── web_static/                     # Static assets for web UI
└── web_templates/                  # HTML templates for web UI
```

## **🔗 APIs Used & Privacy Policies**

This program sends no telemetry data. All network traffic consists of direct requests from your computer to the following services:

1. **CCXT** (Used to sync exchange trades and ledgers)  
   * **Why:** CCXT is a unified library that connects to 100+ exchanges (Binance, Kraken, Coinbase, etc.) to fetch your trading history and staking ledgers.  
   * [Privacy Policy](https://docs.ccxt.com/en/latest/manual/exchanges.html)  
2. **staketaxcsv** (Used to auto-generate and import staking rewards)  
   * **Why:** staketaxcsv is a tool that connects to 20+ staking protocols (Lido, Aave, Compound, exchange staking, etc.) to automatically fetch your staking rewards and generate transaction-ready CSVs.  
   * **Install:** `pip install staketaxcsv`  
   * [GitHub Repository](https://github.com/macrominerd/staketaxcsv)  
   * [Privacy Policy](https://github.com/macrominerd/staketaxcsv#privacy)  
3. **Moralis** (Used for auditing EVM & Solana chains)  
   * **Why:** To fetch real-time token balances and verify your portfolio matches the Transaction engine's calculations.  
   * [Privacy Policy](https://www.google.com/search?q=https://moralis.com/privacy-policy)  
4. **Blockchair** (Used for auditing Bitcoin & UTXO chains)  
   * **Why:** To fetch balances for non-EVM chains like Bitcoin, Litecoin, and Dogecoin.  
   * [Privacy Policy](https://blockchair.com/privacy)  
5. **CoinGecko** (Used to identify stablecoins and fetch token contract addresses)  
   * **Why:** To download a list of stablecoins (USDC, USDT, DAI) so the engine knows to value them strictly at $1.00 USD. Also used to automatically fetch ERC-20 token contract addresses for on-chain price lookups.  
   * [Privacy Policy](https://www.coingecko.com/en/privacy)  
6. **Yahoo Finance** (Used to backfill historical prices)  
   * **Why:** To fetch historical prices when current exchange data is incomplete.  
   * [Privacy Policy](https://finance.yahoo.com/privacy)

## **⚠️ Critical Disclaimer (Read First)**

- Designed to follow 2025 US tax guidelines but **not warranted accurate or complete**. Results can be wrong; always review with a qualified tax professional.
- I have **no Transaction training**. This was built for my own simple transaction tracking.
- **No liability** is accepted for errors, omissions, data loss, or compliance outcomes. Use at your own risk.
- Intended for **local use only**. Do not expose the app or APIs to the internet; HTTPS uses self-signed certs and is not hardened for public access.
- Secrets are stored in encrypted files, but you are responsible for host security, key management, and backups.

**Before using the Program, you must accept the [Terms of Service](TERMS_OF_SERVICE.md). Acceptance is required and will be prompted on first run.**

## **🚀 Quick Start**

> ⚠️ **BEFORE YOU FILE:** Review every CSV output with a qualified tax professional. Do not file based solely on this tool's output. Cryptocurrency tax reporting is complex and changing; errors here could result in audit, penalties, or misstatement. **This is your responsibility.**

### **First-Time Setup Wizard (Web UI)**
- Launch `python start_web_ui.py` and go to https://localhost:5000
- Step 1: Create admin account (local only)
- Step 2: Accept the Terms of Service in the modal (required to continue)
- Step 3: Optional backup restore/import
- Step 4/5: Add API keys (read-only) and wallets, then review settings

After setup, you can log in with the admin account and run imports/reports from the UI.

### **1. Install Requirements**

Install core Python dependencies:

```bash
pip install -r requirements.txt
```

**Optional - ML/AI Features:** If you want to use ML-based transaction classification and Accuracy Mode, install the optional ML dependencies:

```bash
pip install -r requirements-ml.txt
```

This installs PyTorch, Transformers, and related ML libraries. These are only needed if you enable AI/ML features in the configuration. The system works fine without them - they're completely optional.

**Optional - Staking Rewards:** For automatic staking rewards import, also install staketaxcsv:

```bash
pip install staketaxcsv
```

### **2. Initialize**

Run the setup script to generate the folder structure and configuration files:

```bash
python Setup.py
```

### **3. Configure**

* **api_keys_encrypted.json:** Add Read-Only keys for exchanges. Add a **Moralis** key for EVM/Solana audits.  
* **wallets_encrypted.json:** Add public addresses for on-chain audits. To add multiple wallets for the same coin, use a JSON array of addresses. Example:

```json
{
   "ethereum": {
      "addresses": [
         "0xFirstEthAddressHere",
         "0xSecondEthAddressHere",
         "0xThirdEthAddressHere"
      ]
   },
   "bitcoin": {
      "addresses": [
         "bc1FirstBtcAddressHere",
         "1SecondBtcAddressHere"
      ]
   },
   "solana": {
      "addresses": "SolanaPublicKeyHere"
   }
}
```

**Notes:** Use public addresses only (do NOT paste private keys). For EVM chains prefer checksummed `0x...` addresses when possible.

* **configs/config.json:** (Optional) Configure staking rewards auto-import and other settings:
  - `accounting.method`: Switch to "HIFO" if desired (Defaults to "FIFO")
  - `staking.enabled`: Enable/disable staketaxcsv auto-import (requires staketaxcsv installed)
  - `staking.protocols_to_sync`: Which protocols to sync (e.g., `["lido", "aave"]` or `["all"]`)

### **4. Run**

To sync data, calculate Transactions, and generate reports:

```bash
python auto_runner.py
```

### **5. Verify (Tests)**

Run the full suite:

```bash
pytest -q
```

Useful focused runs:

```bash
# End-to-end scenarios and regressions
python -m pytest -q tests/test_comprehensive_scenarios.py

# Web setup wizard flow
python -m pytest -q tests/test_setup_workflow.py

# Stress harness (generate then verify)
python tests/generate_stress_test_data.py
python tests/verify_stress_test.py
```

## **📂 Output Files (outputs/Year_YYYY/)**

| File Name | Description |
| :---- | :---- |
| **CAP_GAINS_REPORT.csv** | Capital gains detail for Schedule D; generic CSV compatible with Transaction software. |
| **INCOME_REPORT.csv** | Total value of Staking, Mining, Forks, and Airdrops (Ordinary Income). |
| **US_transaction_LOSS_ANALYSIS.csv** | Summary of Net Short/Long positions, Allowable Deduction ($3k), and Carryovers. |
| **WASH_SALE_REPORT.csv** | Detailed list of losses disallowed due to the Wash Sale rule. |
| **FBAR_MAX_VALUE_REPORT.csv** | Shows the peak USD balance for every exchange to help with FBAR filing. |
| **REVIEW_WARNINGS.csv** | High-priority audit risks (NFTs, missing prices, unmatched sells). |
| **REVIEW_SUGGESTIONS.csv** | Medium/low-priority items (DeFi complexity, wash sale variants, hedging). |
| **EOY_HOLDINGS_SNAPSHOT.csv** | Your closing portfolio balance on Dec 31st. |

## **🔍 Manual Review Assistant (Heuristic Scanner)**

After generating Transaction reports, the system automatically runs a **heuristic-based manual review** that flags potential audit risks. These heuristics can miss issues or produce false positives—treat them as prompts to review, not guarantees.

### **What It Detects**

The reviewer scans for:

1. **NFTs Without Collectible Prefixes** (🚨 HIGH)
  - Finds assets like "BAYC#1234" or "CRYPTOPUNK" that aren't marked with NFT- prefix
  - **Risk:** Long-term NFT gains may be treated as collectibles with higher rates
  - **Action:** Rename assets with NFT- prefix or add to config.json collectible list

2. **Substantially Identical Wash Sales** (⚠️ MEDIUM)
   - Detects trades between wrapped assets (BTC → WBTC, ETH → WETH) within 30-day window
   - **Risk:** IRS may treat BTC/WBTC as "substantially identical" even with different tickers
   - **Action:** Review these trades; consider adjusting cost basis if selling at loss

3. **Potential Constructive Sales** (💡 LOW)
  - Flags same-day offsetting trades (buy + sell) that could be hedging strategies
  - **Risk:** "Shorting against the box" can trigger immediate recognition under IRC § 1259
  - **Action:** Rare for most users; review if you use advanced trading strategies

4. **DeFi/LP Token Complexity** (💡 MEDIUM)
   - Identifies liquidity pool tokens (UNI-V2, CURVE-LP) and DeFi protocol tokens
   - **Risk:** LP deposits may be Reportable swaps; impermanent loss not auto-calculated
   - **Action:** Verify deposits/withdrawals; ensure yield is marked as INCOME

5. **Missing Prices or Unmatched Sells** (🚨 HIGH)
   - Finds transactions with zero USD prices or sells without sufficient basis
   - **Risk:** Incorrect gain calculations; broker mismatch in strict mode
  - **Action:** Run auto_runner.py to fetch prices; check for missing import data

### **How to Use**

The review runs automatically when you execute:

```bash
python auto_runner.py
```

Or when running the main engine directly:

```bash
python Crypto_Transaction_Engine.py
```

**Review output appears:**
- **Console:** Formatted report with warnings, suggestions, and recommended actions
- **CSV Files:** `REVIEW_WARNINGS.csv` and `REVIEW_SUGGESTIONS.csv` in your Year_XXXX folder

### **Interactive Review Fixer**

After the Transaction Reviewer detects issues, use the **Interactive Review Fixer** (src/tools/review_fixer.py) to address them through a guided, transaction-by-transaction workflow.

#### **How to Use**

Run the fixer for a specific Transaction year:

```bash
# Direct invocation
python src/tools/review_fixer.py 2024

# Via CLI wrapper
python cli.py fix-review 2024
```

#### **What It Does**

The fixer automatically guides you through **all warnings** in order, processing each transaction individually:

1. **Creates Automatic Backup**: Database backed up before any changes
2. **Guided Flow**: No menus—automatically uses the best fix method for each warning type
3. **Transaction-by-Transaction**: Review and decide on each asset individually
4. **Smart Price Suggestions**: 
   - Automatically fetches token contract addresses from CoinGecko (cached for 7 days)
   - Checks on-chain sources when available
   - Falls back to Yahoo Finance
   - Shows suggested prices with accept/override/skip options
5. **Skip Options**: Skip individual transactions (`'skip'`) or all remaining in category (`'skip-all'`)
6. **Safety**: All changes committed at end; rollback available if needed

#### **Example Workflow**

```
=== INTERACTIVE REVIEW FIXER - Guided Fix Process ===

Found 3 warning(s) requiring attention.
This tool will guide you through fixing each issue automatically.

Ready to start? (yes/no): yes

[✓] Database backup created: trades_backup_before_fix_20251211_143022.db

================================================================================
WARNING 1/3: Missing USD Prices
================================================================================
Category: MISSING_PRICES
Severity: High
Count: 8 issue(s)

--- GUIDED FIX: MISSING PRICES ---
For each transaction, we'll show suggested prices from available sources.

[*] Using cached token addresses (age: 2 days)

  PEPE on 2024-03-15 (amount: 1000000)
    On-chain: no contract found for PEPE
    Yahoo Finance: $0.0000089
    → Suggested: $0.0000089
    (Enter=accept, number=override, 'skip'=skip this, 'skip-all'=skip remaining): ↵
    ✓ Set to $0.0000089

  MATIC on 2024-05-10 (amount: 150)
    On-chain: Found MATIC contract on polygon (0x0d500B1...)
    Yahoo Finance: $0.68
    → Suggested: $0.68
    (Enter=accept, number=override, 'skip'=skip this, 'skip-all'=skip remaining): 0.72
    ✓ Set to $0.72

  [continues for all 8 transactions...]

================================================================================
WARNING 2/3: NFT/Collectible Transactions
================================================================================
Category: NFT_COLLECTIBLES
Severity: Medium
Count: 3 issue(s)

--- GUIDED FIX: NFT/COLLECTIBLES ---
Rename each NFT/collectible for proper tracking.

  Current: Bored Ape #1234 (Date: 2024-02-01, Amount: 1)
    Rename to (Enter=keep as-is, 'skip'=skip all remaining): NFT-BAYC-1234
    ✓ Renamed to 'NFT-BAYC-1234'

  [continues for all 3 NFTs...]

================================================================================
WARNING 3/3: Duplicate Transactions
================================================================================
Category: DUPLICATE_TRANSACTIONS
Severity: High
Count: 2 groups (5 transactions total)

--- GUIDED FIX: DUPLICATES ---
Review each duplicate group and choose which transaction to keep.

  Duplicate group: BTC|2024-03-15|0.5|Coinbase
    1. ID=12345, Source=Coinbase_API, Batch=batch_001
    2. ID=12387, Source=Coinbase_CSV, Batch=batch_002
  Which one to KEEP? (1-2, 'skip'=skip this group, 'skip-all'=skip remaining): 1
    ✓ Deleted: 12387
    ✓ Kept: 12345

  [continues for all duplicate groups...]

=== FIX SUMMARY ===
Applied 15 fixes:
  - 3 renames
  - 8 price updates
  - 4 deletions

✓ All changes saved!
✓ Backup still available at: trades_backup_before_fix_20251211_143022.db

Re-run Transaction calculations to see updated results:
  python auto_runner.py
```

#### **Features**

- **Automatic Token Contract Lookup**: Fetches ERC-20 contract addresses from CoinGecko API
  - Covers top 250 tokens by market cap across Ethereum, Polygon, BSC, Arbitrum, Optimism, Avalanche, Fantom
  - Cached locally for 7 days (refreshes automatically when expired)
  - Session-level caching prevents redundant API calls within same session

- **Smart Price Suggestions**: 
  - Native coin detection (ETH, BTC, MATIC, BNB, etc.)
  - ERC-20 token contract lookups
  - Yahoo Finance fallback for all tokens
  - Shows all available sources and suggests best option

- **Interactive Controls**:
  - `Enter` = Accept suggested price
  - `number` = Override with manual price
  - `'skip'` = Skip current transaction (will reappear next run)
  - `'skip-all'` = Skip all remaining in category

- **Safety Features**:
  - Automatic database backup before any changes
  - Rollback capability if needed
  - All changes previewed before commit
  - Detailed summary of all applied fixes

- **Guided Fix Types**:
  - **Missing Prices**: Shows suggested prices from available sources
  - **NFT/Collectibles**: Rename for proper 28% collectibles Transaction treatment
  - **Duplicates**: Choose which transaction to keep per group
  - **Wash Sales**: Rename coins to distinguish wallets/exchanges
  - **High Fees**: Display details for manual source CSV correction

#### **After Fixing**

Once you've fixed issues, re-run the Transaction calculation:

```bash
python auto_runner.py
```

The reviewer will run again. Successfully fixed items won't appear. Skipped items will reappear for review later.

### **Example Review Output**

```
================================================================================
Transaction REVIEW REPORT - MANUAL VERIFICATION REQUIRED
================================================================================

📊 SUMMARY:
   🚨 High Priority Warnings: 2
   ⚠️  Medium Priority: 1
   💡 Suggestions: 1

================================================================================
🚨 HIGH: Potential NFTs Not Marked as Collectibles
================================================================================
Count: 3 items
Found assets that appear to be NFTs but are not prefixed with NFT-, ART-, or
COLLECTIBLE-. If these are collectibles, they may face higher long-term rates (28%)
rate (not 20%).

📋 Sample Items:
   1. BAYC#1234 (bought 06/15/2024)
   2. CRYPTOPUNK#5822 (sold 08/20/2024)
   3. AZUKI#9999 (transferred 11/01/2024)

✅ RECOMMENDED ACTION:
Review these assets. If they are NFTs:
  1. Edit your CSV to rename them with NFT- prefix (e.g., "BAYC#1234" → "NFT-BAYC#1234")
  2. Or add them to config.json "collectible_tokens" list
  3. Re-run the Transaction calculation
```

## **⚖️ Disclaimer**

I am a script, not a tax professional.  
This software is provided "as is". Cryptocurrency Transaction laws (e.g., IRC § 1091 Wash Sales) are subject to interpretation and change. You are solely responsible for reviewing these reports and consulting with a qualified CPA or Transaction attorney before filing with the IRS.

## **💰 Staking Rewards (staketaxcsv Integration)**

The engine integrates with **staketaxcsv** to automatically import staking rewards from all major protocols. This feature is **optional** and requires the staketaxcsv CLI.

### **Supported Staking Protocols**

| Protocol | Type | Examples |
| :---- | :---- | :---- |
| **Liquid Staking (LSD)** | Ethereum, Polygon, Solana | Lido, Rocket Pool, StakeWise |
| **Exchange Staking** | Centralized Exchange | Binance, Coinbase, Kraken, OKX, KuCoin, ByBit |
| **DeFi Lending** | Automated Market Makers | Aave, Compound, dYdX, Curve |
| **Proof-of-Stake** | L1/L2 Chains | Ethereum 2.0 Staking, Solana Staking, Avalanche |
| **Legacy Protocols** | Older/Niche Staking | Tezos (XTZ), Polkadot (DOT), Cosmos (ATOM) |

### **Setup & Configuration**

#### **1. Install staketaxcsv**

staketaxcsv is a separate Python package. Install it alongside the main engine:

```bash
pip install staketaxcsv
```

#### **2. Enable in config.json**

Edit your `config.json` file and enable the staking section. Wallet addresses are **automatically pulled** from your `wallets_encrypted.json` file:

```json
{
  "staking": {
    "enabled": true,
    "protocols_to_sync": ["all"]
  }
}
```

**Configuration Fields:**
- `enabled` (bool): Enable/disable staketaxcsv auto-import
- `protocols_to_sync` (array): Which protocols to sync. Use `["all"]` for all protocols, or specify specific ones like `["lido", "aave", "compound"]`

**Note:** Wallet addresses are automatically read from `wallets_encrypted.json` — no separate configuration needed!

#### **3. Run auto_runner.py**

The staketaxcsv manager runs automatically:

```bash
python auto_runner.py
```

**Output:**
- Staking CSV is generated in `inputs/staketransaction_generated/`
- Records are imported into the database with **deduplication**
- CSV is archived to `processed_archive/`

### **How Deduplication Works**

To prevent importing the same staking reward multiple times, the engine generates a unique hash for each reward:

```
dedup_hash = SHA256(date + coin + amount + protocol)[:16]
```

If a record with the same hash already exists in the database, it is skipped. This prevents double-counting staking income when you re-run the engine.

### **Staking Income Classification**

Staking rewards are classified as **Ordinary Income** (Form 1040, Line 21) on the day they are received, NOT when you sell them. The value is the **USD price at the time of receipt**.

Example:
* Date: 2024-01-15
* Received: 0.5 ETH from Lido staking
* ETH Price on 2024-01-15: $2,500
* **Reportable Income:** 0.5 × $2,500 = **$1,250** (ordinary income)

When you later sell that 0.5 ETH, the cost basis is $2,500, and any gain/loss is treated as a **Capital Gain/Loss**.

### **Supported Wallet Types**

* **Ethereum Addresses:** `0x...` (EVM-compatible)
* **Solana Addresses:** Standard Solana pubkeys
* **Bitcoin Addresses:** `bc1...` (Segwit) or `1...` (Legacy)
* **Multi-Chain:** staketaxcsv auto-detects wallet types

### **Manual Fallback for Unsupported Staking Services**

If your staking service (e.g., custom validators, or niche protocols) is not automatically detected by staketaxcsv, you can manually import staking rewards via CSV.

#### **Why Use Manual Import?**

* staketaxcsv doesn't support your specific staking service
* You have custom staking arrangements or validator delegations
* You want to audit specific staking transactions

#### **How to Create a Manual Staking CSV**

Create a file named `staking_manual_YYYY.csv` in the `inputs/` folder with these columns:

```csv
date,coin,amount,protocol,usd_value_at_time
2024-01-15,SOL,0.5,custom_validator,150.00
2024-02-10,SOL,0.5,custom_validator,155.00
2024-01-20,ETH,0.01,custom_validator,2500.00
```

**Required Fields:**
- `date` - When the reward was received (YYYY-MM-DD format)
- `coin` - Asset symbol (SOL, ETH, etc.)
- `amount` - Quantity of reward received
- `protocol` - Name of staking service/protocol
- `usd_value_at_time` - USD price per unit on that date (engine will calculate total value)

**Optional Fields:**
- You can also include: `timestamp`, `type` (set to "staking"), `source` (set to "manual_staking")




```csv
date,coin,amount,protocol,usd_value_at_time
```

**Step-by-Step:**
1. Export or calculate your Figment rewards from their dashboard
2. Get the USD price for each date (CoinGecko, Yahoo Finance, etc.)
3. Create `inputs/figment_staking.csv` with the data
4. Run `python auto_runner.py`
5. The rewards are imported with deduplication (same as staketaxcsv)

#### **Transaction Treatment**

Manual staking imports are treated identically to staketaxcsv imports:
- Classified as **Ordinary Income** on receipt date
- Recorded in INCOME_REPORT.csv
- Proper cost basis set for future sales
- Deduplication prevents double-counting on re-runs

#### **Troubleshooting Manual Imports**

| Issue | Solution |
| :---- | :---- |
| CSV not imported | Check `outputs/logs/` for errors. Ensure file is in `inputs/` folder. |
| Price showing as $0 | Verify `usd_value_at_time` is a valid number. Engine will backfill if missing. |
| Duplicate imports | Deduplication uses date + coin + amount + protocol hash. Verify data is identical. |
| Format errors | Check CSV column names match exactly (case-sensitive). Use comma delimiters. |

## **🧪 Development & Testing**

The project includes a comprehensive test suite located in the `tests/` directory.

### **Running Tests**

To run the full test suite (recommended):

## Testing

Comprehensive test coverage ensures CLI and Web UI remain in sync and can be used simultaneously without data corruption.

**Quick Start**:
```bash
python -m pytest tests/test_cli_web_ui_concurrency.py -v
```

**Full Documentation**: See [docs/TESTING.md](docs/TESTING.md)

Key test suites:
- **Concurrency**: `tests/test_cli_web_ui_concurrency.py` (✅ 6 tests, all passing)
- **CLI Parity**: `tests/test_cli_expanded.py` (comprehensive CLI command coverage)
- **Original CLI**: `tests/test_cli.py`

