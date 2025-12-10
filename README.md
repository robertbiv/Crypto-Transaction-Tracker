# **🛡️ Crypto Tax Automation Engine (V30)**

A professional-grade, self-hosted Python system for tracking cryptocurrency taxes. It is designed to be **US Tax Law Compliant** (IRS Pub 544), featuring robust handling of Capital Gains, Wash Sales, Loss Carryovers, and FBAR reporting.

**Privacy First:** This software runs entirely on your local machine. No financial data is sent to the developer.

## **🌟 Key Features**

### **🇺🇸 US Tax Compliance**

* **FIFO Accounting:** Uses "First-In, First-Out" as the default cost basis method (IRS default).  
* **Wash Sale Rule:** Automatically detects if you sell at a loss and buy back a "substantially identical" asset within 30 days. Disallows the loss and defers it to the replacement asset.  
* **Annual Loss Limit:** Caps net capital loss deductions at **$3,000** against ordinary income.  
* **Auto-Carryover:** Automatically imports unused losses from the previous year's report to offset current year gains.  
* **Holding Periods:** Distinguishes between **Short-Term** (\< 1 year) and **Long-Term** (\> 1 year) capital gains.

### **💼 Advanced Reporting**

* **FBAR Report:** Tracks the **maximum USD value** held on foreign exchanges (e.g., Binance, KuCoin) at any point in the year to assist with FinCEN Form 114 filing.  
* **Income Classification:** Separates Mining, Staking, Airdrops, and Hard Forks as **Ordinary Income** (not Capital Gains).  
* **Gas Fees:** Treats gas spent on transfers as a taxable disposition of the underlying asset (e.g., selling ETH to pay for a transaction).

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

## **📂 The Ecosystem**

The script automatically builds and maintains this structure:

/My\_Crypto\_Tax\_Folder  
│  
├── README.md                      \# \[DOCS\] This manual  
├── requirements.txt               \# \[DOCS\] Python dependencies list  
├── .gitignore                     \# \[DOCS\] Git ignore file (Crucial for security)  
├── Supported Blockchains.md       \# \[DOCS\] List of supported chains  
├── Supported Exchanges.md         \# \[DOCS\] List of supported exchanges  
│  
├── Setup.py                       \# \[USER\] Run once to initialize folders/files  
├── Auto\_Runner.py                 \# \[USER\] Run this to sync & update taxes  
├── Crypto\_Tax\_Engine.py           \# \[CORE\] The logic engine (do not delete)  
├── test\_suite.py                  \# \[USER\] Verification suite (Chaos/Compliance tests)  
│  
├── api\_keys.json                  \# \[USER\] Your Exchange & Audit Keys  
├── wallets.json                   \# \[USER\] Your Public Addresses (For Audit)  
├── config.json                    \# \[USER\] Settings (Enable/Disable Audit, Backups, HIFO)  
│  
├── crypto\_master.db               \# \[AUTO\] The permanent database  
├── crypto\_master.db.bak           \# \[AUTO\] Safety backup (Last known good state)  
├── stablecoins\_cache.json         \# \[AUTO\] Cached list of stablecoins  
│  
├── inputs/                        \# \[USER\] Drop manual CSVs here (MoonPay, etc.)  
├── processed\_archive/             \# \[AUTO\] Old CSVs move here after processing  
│  
└── outputs/  
    ├── logs/                      \# \[AUTO\] Timestamped text logs of every run  
    ├── Year\_2024/                 \# \[AUTO\] Finalized Tax Reports  
    └── Year\_2025/                 \# \[AUTO\] Live/Draft Tax Reports

## **🔗 APIs Used & Privacy Policies**

This program sends no telemetry data. All network traffic consists of direct requests from your computer to the following services:

1. **Moralis** (Used for auditing EVM & Solana chains)  
   * **Why:** To fetch real-time token balances and verify your portfolio matches the tax engine's calculations.  
   * [Privacy Policy](https://www.google.com/search?q=https://moralis.com/privacy-policy)  
2. **Blockchair** (Used for auditing Bitcoin & UTXO chains)  
   * **Why:** To fetch balances for non-EVM chains like Bitcoin, Litecoin, and Dogecoin.  
   * [Privacy Policy](https://blockchair.com/privacy)  
3. **CoinGecko** (Used to identify stablecoin tickers)  
   * **Why:** To download a list of stablecoins (USDC, USDT, DAI) so the engine knows to value them strictly at $1.00 USD.  
   * [Privacy Policy](https://www.coingecko.com/en/privacy)  
4. **Yahoo Finance** (Used to backfill historical prices)  
   * **Why:** If a CSV import is missing a USD price (e.g., from an old airdrop or mining reward), the engine queries Yahoo Finance for the historical close price on that specific date.  
   * [Privacy Policy](https://legal.yahoo.com/us/en/yahoo/privacy/index.html)  
5. **CCXT / Exchanges** (Binance, Coinbase, Kraken, etc.)  
   * **Why:** To connect directly to your exchange accounts and download trade history, fees, and staking rewards automatically.  
   * **Privacy:** Your API keys are stored locally in api\_keys.json and are **never** sent to any third-party server other than the specific exchange they belong to. Please check the privacy policy of each exchange you use.

## **🚀 Quick Start**

### **1\. Install Requirements**

pip install pandas ccxt yfinance requests

### **2\. Initialize**

Run the setup script to generate the folder structure and configuration files:

python Setup.py

### **3\. Configure**

* **api\_keys.json:** Add Read-Only keys for exchanges. Add a **Moralis** key for EVM/Solana audits.  
* **wallets.json:** Add public addresses for on-chain audits. To add multiple wallets for the same coin, use a JSON array of addresses. Example:

```json
{
   "ETH": [
      "0xFirstEthAddressHere",
      "0xSecondEthAddressHere",
      "0xThirdEthAddressHere"
   ],
   "BTC": [
      "bc1FirstBtcAddressHere",
      "1SecondBtcAddressHere"
   ]
}
```

Notes: Use public addresses only (do NOT paste private keys). For EVM chains prefer checksummed `0x...` addresses when possible.
* **config.json:** (Optional) Switch accounting.method to "HIFO" if desired (Defaults to "FIFO").

### **4\. Run**

To sync data, calculate taxes, and generate reports:

python Auto\_Runner.py

### **5\. Verify (Unit Tests)**

To run the "Chaos Suite" and verify the math is perfect before filing:

python test\_suite.py

## **📂 Output Files (outputs/Year\_YYYY/)**

| File Name | Description |
| :---- | :---- |
| **GENERIC_TAX\_CAP\_GAINS.csv** | The primary report for Schedule D. Includes Proceeds, Cost Basis, and Gain/Loss. |
| **INCOME\_REPORT.csv** | Total value of Staking, Mining, Forks, and Airdrops (Ordinary Income). |
| **US\_TAX\_LOSS\_ANALYSIS.csv** | Summary of Net Short/Long positions, Allowable Deduction ($3k), and Carryovers. |
| **WASH\_SALE\_REPORT.csv** | Detailed list of losses disallowed due to the Wash Sale rule. |
| **FBAR\_MAX\_VALUE\_REPORT.csv** | Shows the peak USD balance for every exchange to help with FBAR filing. |
| **EOY\_HOLDINGS\_SNAPSHOT.csv** | Your closing portfolio balance on Dec 31st. |

## **⚖️ Disclaimer**

I am a script, not a tax professional.  
This software is provided "as is". Cryptocurrency tax laws (e.g., IRC § 1091 Wash Sales) are subject to interpretation and change. You are solely responsible for reviewing these reports and consulting with a qualified CPA or tax attorney before filing with the IRS.