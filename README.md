# **🛡️ Crypto Tax Automation Engine (V30)**

A professional-grade, self-hosted Python system for tracking cryptocurrency taxes. It is designed to be **US Tax Law Compliant** (IRS Pub 544), featuring robust handling of Capital Gains, Wash Sales, Loss Carryovers, and FBAR reporting.

**Privacy First:** This software runs entirely on your local machine. No financial data is sent to the developer.

## **🌟 Key Features**

### **🇺🇸 US Tax Compliance**

* **FIFO/HIFO Accounting:** Uses FIFO by default, with optional HIFO. HIFO sorts lots by highest price for sells.  
* **Wash Sale Rule:** Detects buys within 30 days before and after a loss sale. Disallows the proportional loss and flags affected TT rows.  
* **Annual Loss Limit:** Caps net capital loss deductions at **$3,000** against ordinary income.  
* **Auto-Carryover:** Imports prior-year carryovers and computes next-year carryover fields.  
* **Holding Periods:** Distinguishes between **Short-Term** (< 1 year) and **Long-Term** (> 1 year) capital gains.
* **Collectibles Reporting:** Splits long-term collectibles (28%) in loss analysis.

### **💼 Advanced Reporting**

* **FBAR Report:** Tracks the **maximum USD value** held on foreign exchanges (e.g., Binance, KuCoin) at any point in the year to assist with FinCEN Form 114 filing.  
* **Income Classification:** Separates Mining, Staking, Airdrops, Gifts (IN) and Hard Forks as **Ordinary Income** (not Capital Gains). Constructive receipt toggle supported.  
* **Multi-Coin Fees:** Supports `fee_coin` field for transfers with fees in different coins (e.g., ERC-20 token transfers with ETH gas fees). Backward compatible with legacy single-coin fees.
* **1099 Reconciliation:** Aggregates proceeds, basis, net gain, and transaction counts per source/coin. Detailed CSV includes unmatched and wash placeholders.
* **Snapshots:** Exports per-source holdings with a `Holdings` column and minimal `TAX_REPORT.csv` marker.
* **Manual Review Assistant:** Automatic heuristic-based scan that flags potential audit risks including:
  - NFTs without collectible prefixes (28% tax rate risk)
  - Substantially identical wash sales (BTC/WBTC)
  - Potential constructive sales patterns
  - Complex DeFi/LP transactions needing verification
  - Missing prices or unmatched sells

### **🛡️ System Resilience**

* **Chaos Tested:** Validated against 1,000+ random high-volatility trade simulations.  
* **Crash Proof:** Handles power outages or crashes mid-write by restoring from .bak files.  
* **Network Resilience:** Implements exponential backoff retries for spotty internet connections.  
* **Data Integrity:** Automatically detects database corruption and rebuilds from raw inputs if necessary.

## **⚠️ Weaknesses & Limitations**

While robust, this engine is software, not a CPA. Be aware of these limitations:

1. **Constructive Sales:** The engine does **not** detect "Constructive Sales" (e.g., shorting-against-the-box). If you hold a long position and open an offsetting short position to lock in gains without selling, this software will not trigger a tax event.  
2. **Specific Identification:** The engine assumes **FIFO** (or HIFO if configured). It does not support "Specific Identification" of lots (picking exactly which Bitcoin utxo to sell) unless you manually manipulate the input data.  
3. **Complex DeFi (LP Tokens):** Liquidity Pool (LP) tokens are generally treated as DEPOSIT (non-taxable) or SWAP depending on the CSV input. It does not automatically calculate "Impermanent Loss" unless you explicitly record the exit as a sale.  
4. **NFTs:** Non-Fungible Tokens are treated as generic assets. It does not handle complex NFT minting gas logic automatically unless imported as a standard trade.  
5. **Gift Basis:** For received gifts, the engine relies on **you** entering the correct "Donor's Basis" in the manual CSV. If you enter the market price instead, your tax liability may be calculated incorrectly.

## **⚠️ Important Note on HIFO Accounting**

The engine supports **HIFO** (Highest-In, First-Out) via configuration, but be warned:

* **Audit Risk:** To use HIFO legally, the IRS requires "Specific Identification" of the units sold. This means you must have a record showing exactly *which* lot (date and price) you sold.  
* **Compliance:** While this software generates logs that *can* serve as these records, relying on HIFO is riskier than FIFO. If you cannot produce the specific logs during an audit, the IRS may force you to recalculate everything using FIFO, potentially leading to back taxes and penalties.  
* **Default:** We strongly recommend sticking to the default **FIFO** method unless you are an advanced user prepared to maintain detailed records.

## **⚠️ Compliance Controls & Non‑Recommended Options**

Certain configuration options can increase audit risk or create mismatches with broker 1099‑DA reporting. The engine will warn at runtime when these are enabled:

- **strict_broker_mode (Recommended=True):** When disabled, the engine may borrow cost basis across wallets to satisfy sales from custodial sources (e.g., Coinbase). This can cause Form 8949 to diverge from broker‑issued Form 1099‑DA. Keep this enabled for 2025+ compliance. When enabled, unmatched sells are flagged in the detailed reconciliation CSV.
- **staking_taxable_on_receipt (Recommended=True):** Setting this to False applies a “constructive receipt” deferral for staking/mining rewards (no income recorded until sale). This is an aggressive position and may be challenged by the IRS under Rev. Rul. 2023‑14. Use only if you understand the risks.
- **HIFO (Not Recommended):** While supported, HIFO increases audit friction unless you maintain specific identification records. FIFO remains the safest default.

See `config.json` for detailed instructions. The setup script annotates non‑recommended options and the engine logs a warning when they are enabled.

## **📂 The Ecosystem**

The script automatically builds and maintains this structure:

```
/My_Crypto_Tax_Folder
│
├── README.md                      # [DOCS] This manual
├── requirements.txt               # [DOCS] Python dependencies list
├── .gitignore                     # [DOCS] Git ignore file (Crucial for security)
│
├── Setup.py                       # [USER] Run once to initialize folders/files
├── docs/                          # [DOCS] Supporting documentation
│   ├── Supported Blockchains.md   # [DOCS] List of supported chains
│   ├── Supported Exchanges.md     # [DOCS] List of supported exchanges
│   ├── WALLET_FORMAT_COMPATIBILITY.md # [DOCS] Wallet format reference
│   ├── KNOWN_LIMITATIONS.md       # [DOCS] Architectural limitations & workarounds
│   ├── STAKING_SETUP.md           # [DOCS] Staking rewards tax reporting guide
│   ├── STAKING_QUICK_START.md     # [DOCS] 10-minute quick setup
│   └── STAKING_EXAMPLES.md        # [DOCS] Real-world staking scenarios
├── tests/                         # [USER] Test suite & documentation
│   ├── unit_test.py               # [USER] Verification suite (148 tests, 45 test classes)
│   ├── test_wallet_compatibility.py # [USER] Wallet format compatibility tests
│   ├── TEST_COVERAGE_SUMMARY.md   # [DOCS] Detailed test coverage breakdown
│   └── FINAL_STATUS.md            # [DOCS] Executive summary & checklist
│
├── Auto_Runner.py                 # [USER] Run this to sync & update taxes
├── Crypto_Tax_Engine.py           # [CORE] The logic engine (do not delete)
├── Tax_Reviewer.py                # [CORE] Manual review assistant (heuristic audit scanner)
├── Migration_2025.py              # [TOOL] Safe-harbor allocator for per-wallet basis
│
├── api_keys.json                  # [USER] Your Exchange & Audit Keys
├── wallets.json                   # [USER] Your Public Addresses (For Audit)
├── config.json                    # [USER] Settings (Enable/Disable Audit, Backups, HIFO)
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
         ├── TURBOTAX_CAP_GAINS.csv
         ├── INCOME_REPORT.csv
         ├── US_TAX_LOSS_ANALYSIS.csv
         ├── WASH_SALE_REPORT.csv
         ├── 1099_RECONCILIATION.csv
         ├── 1099_RECONCILIATION_DETAILED.csv
         ├── CURRENT_HOLDINGS_DRAFT.csv
         ├── EOY_HOLDINGS_SNAPSHOT.csv
         ├── TAX_REPORT.csv
         ├── REVIEW_WARNINGS.csv        # [AUTO] High-priority audit risks
         └── REVIEW_SUGGESTIONS.csv     # [AUTO] Medium/low-priority items for review
```

## **🔗 APIs Used & Privacy Policies**

This program sends no telemetry data. All network traffic consists of direct requests from your computer to the following services:

1. **CCXT** (Used to sync exchange trades and ledgers)  
   * **Why:** CCXT is a unified library that connects to 100+ exchanges (Binance, Kraken, Coinbase, etc.) to fetch your trading history and staking ledgers.  
   * [Privacy Policy](https://docs.ccxt.com/en/latest/manual/exchanges.html)  
2. **StakeTaxCSV** (Used to auto-generate and import staking rewards)  
   * **Why:** StakeTaxCSV is a tool that connects to 20+ staking protocols (Lido, Aave, Compound, exchange staking, etc.) to automatically fetch your staking rewards and generate tax-ready CSVs.  
   * **Install:** `pip install staketaxcsv`  
   * [GitHub Repository](https://github.com/macrominerd/staketaxcsv)  
   * [Privacy Policy](https://github.com/macrominerd/staketaxcsv#privacy)  
3. **Moralis** (Used for auditing EVM & Solana chains)  
   * **Why:** To fetch real-time token balances and verify your portfolio matches the tax engine's calculations.  
   * [Privacy Policy](https://www.google.com/search?q=https://moralis.com/privacy-policy)  
4. **Blockchair** (Used for auditing Bitcoin & UTXO chains)  
   * **Why:** To fetch balances for non-EVM chains like Bitcoin, Litecoin, and Dogecoin.  
   * [Privacy Policy](https://blockchair.com/privacy)  
5. **CoinGecko** (Used to identify stablecoin tickers)  
   * **Why:** To download a list of stablecoins (USDC, USDT, DAI) so the engine knows to value them strictly at $1.00 USD.  
   * [Privacy Policy](https://www.coingecko.com/en/privacy)  
6. **Yahoo Finance** (Used to backfill historical prices)  
   * **Why:** To fetch historical prices when current exchange data is incomplete.  
   * [Privacy Policy](https://finance.yahoo.com/privacy)

## **🚀 Quick Start**

### **1. Install Requirements**

Install all Python dependencies from requirements.txt:

```bash
pip install -r requirements.txt
```

Or install core dependencies manually:

```bash
pip install pandas ccxt yfinance requests
```

**Optional:** For staking rewards auto-import, also install StakeTaxCSV:

```bash
pip install staketaxcsv
```

### **2. Initialize**

Run the setup script to generate the folder structure and configuration files:

```bash
python Setup.py
```

### **3. Configure**

* **api_keys.json:** Add Read-Only keys for exchanges. Add a **Moralis** key for EVM/Solana audits.  
* **wallets.json:** Add public addresses for on-chain audits. To add multiple wallets for the same coin, use a JSON array of addresses. Example:

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

* **config.json:** (Optional) Configure staking rewards auto-import and other settings:
  - `accounting.method`: Switch to "HIFO" if desired (Defaults to "FIFO")
  - `staking.enabled`: Enable/disable StakeTaxCSV auto-import (requires StakeTaxCSV installed)
  - `staking.protocols_to_sync`: Which protocols to sync (e.g., `["lido", "aave"]` or `["all"]`)

### **4. Run**

To sync data, calculate taxes, and generate reports:

```bash
python Auto_Runner.py
```

### **5. Verify (Unit Tests)**

The current release passes 197 tests covering accounting, compliance, auditor, ingestor, and reporting.

```bash
pytest -q
```

To run the comprehensive test suite and verify the math is perfect before filing:

```bash
python tests/unit_test.py
```

This runs **148 test methods** across **45 test classes** including edge cases, random scenarios, US tax compliance verification, and graceful error handling.

**For detailed test coverage information**, see:
- `tests/TEST_COVERAGE_SUMMARY.md` - Comprehensive breakdown of all 148 tests by component and tax rule
- `tests/FINAL_STATUS.md` - Executive summary and production readiness checklist

## **📂 Output Files (outputs/Year_YYYY/)**

| File Name | Description |
| :---- | :---- |
| **TURBOTAX_CAP_GAINS.csv** | The primary report for Schedule D. Includes Proceeds, Cost Basis, and Gain/Loss. |
| **INCOME_REPORT.csv** | Total value of Staking, Mining, Forks, and Airdrops (Ordinary Income). |
| **US_TAX_LOSS_ANALYSIS.csv** | Summary of Net Short/Long positions, Allowable Deduction ($3k), and Carryovers. |
| **WASH_SALE_REPORT.csv** | Detailed list of losses disallowed due to the Wash Sale rule. |
| **FBAR_MAX_VALUE_REPORT.csv** | Shows the peak USD balance for every exchange to help with FBAR filing. |
| **REVIEW_WARNINGS.csv** | High-priority audit risks (NFTs, missing prices, unmatched sells). |
| **REVIEW_SUGGESTIONS.csv** | Medium/low-priority items (DeFi complexity, wash sale variants, hedging). |
| **EOY_HOLDINGS_SNAPSHOT.csv** | Your closing portfolio balance on Dec 31st. |

## **🔍 Manual Review Assistant (Heuristic Scanner)**

After generating tax reports, the system automatically runs a **heuristic-based manual review** that flags potential audit risks. This helps catch issues that automated tax software might miss.

### **What It Detects**

The reviewer scans for:

1. **NFTs Without Collectible Prefixes** (🚨 HIGH)
   - Finds assets like "BAYC#1234" or "CRYPTOPUNK" that aren't marked with NFT- prefix
   - **Risk:** Long-term NFT gains should be taxed at 28% (collectibles rate), not 20%
   - **Action:** Rename assets with NFT- prefix or add to config.json collectible list

2. **Substantially Identical Wash Sales** (⚠️ MEDIUM)
   - Detects trades between wrapped assets (BTC → WBTC, ETH → WETH) within 30-day window
   - **Risk:** IRS may treat BTC/WBTC as "substantially identical" even with different tickers
   - **Action:** Review these trades; consider adjusting cost basis if selling at loss

3. **Potential Constructive Sales** (💡 LOW)
   - Flags same-day offsetting trades (buy + sell) that could be hedging strategies
   - **Risk:** "Shorting against the box" triggers immediate taxation under IRC § 1259
   - **Action:** Rare for most users; review if you use advanced trading strategies

4. **DeFi/LP Token Complexity** (💡 MEDIUM)
   - Identifies liquidity pool tokens (UNI-V2, CURVE-LP) and DeFi protocol tokens
   - **Risk:** LP deposits may be taxable swaps; impermanent loss not auto-calculated
   - **Action:** Verify deposits/withdrawals; ensure yield is marked as INCOME

5. **Missing Prices or Unmatched Sells** (🚨 HIGH)
   - Finds transactions with zero USD prices or sells without sufficient basis
   - **Risk:** Incorrect gain calculations; broker mismatch in strict mode
   - **Action:** Run Auto_Runner to fetch prices; check for missing import data

### **How to Use**

The review runs automatically when you execute:

```bash
python Auto_Runner.py
```

Or when running the main engine directly:

```bash
python Crypto_Tax_Engine.py
```

**Review output appears:**
- **Console:** Formatted report with warnings, suggestions, and recommended actions
- **CSV Files:** `REVIEW_WARNINGS.csv` and `REVIEW_SUGGESTIONS.csv` in your Year_XXXX folder

### **Example Review Output**

```
================================================================================
TAX REVIEW REPORT - MANUAL VERIFICATION REQUIRED
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
COLLECTIBLE-. If these are collectibles, they should be taxed at 28% long-term
rate (not 20%).

📋 Sample Items:
   1. BAYC#1234 (bought 06/15/2024)
   2. CRYPTOPUNK#5822 (sold 08/20/2024)
   3. AZUKI#9999 (transferred 11/01/2024)

✅ RECOMMENDED ACTION:
Review these assets. If they are NFTs:
  1. Edit your CSV to rename them with NFT- prefix (e.g., "BAYC#1234" → "NFT-BAYC#1234")
  2. Or add them to config.json "collectible_tokens" list
  3. Re-run the tax calculation
```

## **⚖️ Disclaimer**

I am a script, not a tax professional.  
This software is provided "as is". Cryptocurrency tax laws (e.g., IRC § 1091 Wash Sales) are subject to interpretation and change. You are solely responsible for reviewing these reports and consulting with a qualified CPA or tax attorney before filing with the IRS.

## **💰 Staking Rewards (StakeTaxCSV Integration)**

The engine integrates with **StakeTaxCSV** to automatically import staking rewards from all major protocols. This feature is **optional** and requires the StakeTaxCSV CLI.

### **Supported Staking Protocols**

| Protocol | Type | Examples |
| :---- | :---- | :---- |
| **Liquid Staking (LSD)** | Ethereum, Polygon, Solana | Lido, Rocket Pool, StakeWise |
| **Exchange Staking** | Centralized Exchange | Binance, Coinbase, Kraken, OKX, KuCoin, ByBit |
| **DeFi Lending** | Automated Market Makers | Aave, Compound, dYdX, Curve |
| **Proof-of-Stake** | L1/L2 Chains | Ethereum 2.0 Staking, Solana Staking, Avalanche |
| **Legacy Protocols** | Older/Niche Staking | Tezos (XTZ), Polkadot (DOT), Cosmos (ATOM) |

### **Setup & Configuration**

#### **1. Install StakeTaxCSV**

StakeTaxCSV is a separate Python package. Install it alongside the main engine:

```bash
pip install staketaxcsv
```

#### **2. Enable in config.json**

Edit your `config.json` file and enable the staking section. Wallet addresses are **automatically pulled** from your `wallets.json` file:

```json
{
  "staking": {
    "enabled": true,
    "protocols_to_sync": ["all"]
  }
}
```

**Configuration Fields:**
- `enabled` (bool): Enable/disable StakeTaxCSV auto-import
- `protocols_to_sync` (array): Which protocols to sync. Use `["all"]` for all protocols, or specify specific ones like `["lido", "aave", "compound"]`

**Note:** Wallet addresses are automatically read from `wallets.json` — no separate configuration needed!

#### **3. Run Auto_Runner.py**

The StakeTaxCSV manager runs automatically:

```bash
python Auto_Runner.py
```

**Output:**
- Staking CSV is generated in `inputs/staketax_generated/`
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
* **Taxable Income:** 0.5 × $2,500 = **$1,250** (ordinary income)

When you later sell that 0.5 ETH, the cost basis is $2,500, and any gain/loss is treated as a **Capital Gain/Loss**.

### **Supported Wallet Types**

* **Ethereum Addresses:** `0x...` (EVM-compatible)
* **Solana Addresses:** Standard Solana pubkeys
* **Bitcoin Addresses:** `bc1...` (Segwit) or `1...` (Legacy)
* **Multi-Chain:** StakeTaxCSV auto-detects wallet types

### **Manual Fallback for Unsupported Staking Services**

If your staking service (e.g., custom validators, or niche protocols) is not automatically detected by StakeTaxCSV, you can manually import staking rewards via CSV.

#### **Why Use Manual Import?**

* StakeTaxCSV doesn't support your specific staking service
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
4. Run `python Auto_Runner.py`
5. The rewards are imported with deduplication (same as StakeTaxCSV)

#### **Tax Treatment**

Manual staking imports are treated identically to StakeTaxCSV imports:
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
