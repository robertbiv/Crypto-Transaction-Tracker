# Ledger Staking Rewards - Quick Setup (10 minutes)

## TL;DR: Get Staking Rewards Tax Reports from Your Ledger Wallets

```bash
# 1. Get API keys (5 min)
# Moralis: https://moralis.io → Admin → API Key
# Blockchair: https://blockchair.com/api → Dashboard → API Key

# 2. Create api_keys.json
cat > api_keys.json << 'EOF'
{
  "moralis": {"apiKey": "YOUR_KEY_HERE"},
  "blockchair": {"apiKey": "YOUR_KEY_HERE"}
}
EOF

# 3. Add your wallet addresses to wallets.json
# Copy from Ledger Live: Settings → Accounts → Copy Address
cat > wallets.json << 'EOF'
{
  "ethereum": {"addresses": ["0x1234..."]},
  "solana": {"addresses": ["Abc123..."]},
  "cardano": {"addresses": ["addr1q..."]},
  "polygon": {"addresses": ["0xdef5..."]}
}
EOF

# 4. Enable audit in config.json
cat > config.json << 'EOF'
{"general": {"run_audit": true}, "accounting": {"method": "FIFO"}}
EOF

# 5. Run and get reports
python Auto_Runner.py
# ↑ Detects all staking rewards from your wallets automatically
```

---

## What You'll Get

**Automatic Reports:**
- ✅ All staking rewards detected (Ethereum, Solana, Cardano, Polygon, etc.)
- ✅ Tax-ready CSV: `outputs/Year_2024/INCOME_REPORT.csv`
- ✅ IRS Form 8949 ready: `outputs/Year_2024/GENERIC_TAX_CAP_GAINS.csv`
- ✅ Wallet audit: Current balances validated
- ✅ Missing trade detection: Flags discrepancies

**Example Output:**
```
Staking Income Detected:
  ETH: 2.847 ETH @ avg $2,100 = $5,978.70
  SOL: 8.392 SOL @ avg $25.50 = $214.00
  ADA: 145.2 ADA @ avg $0.85 = $123.42

Total 2024 Staking Income: $6,316.12
```

---

## Step-by-Step Setup

### 1️⃣ Get API Keys (Free Tier Works)

**Moralis (for Ethereum, Polygon, Avalanche, BSC, etc.):**
```
1. Visit https://moralis.io
2. Sign up with email (free tier available)
3. Go to Admin Dashboard → Settings
4. Copy "API Key"
5. Paste into api_keys.json
```

**Blockchair (for Bitcoin, Litecoin, Cardano, Tron, etc.):**
```
1. Visit https://blockchair.com/api
2. Click "Signup" (free tier available)
3. Verify email
4. Dashboard → Copy API Key
5. Paste into api_keys.json
```

### 2️⃣ Get Your Ledger Wallet Addresses

**From Ledger Live:**
```
1. Open Ledger Live
2. Click an account (Ethereum, Solana, Cardano, etc.)
3. Click "Receive"
4. Copy the address
5. Repeat for each coin you've staked
```

**Supported Coins:**
- EVM: Ethereum (0x...), Polygon (0x...), Avalanche (0x...), BSC (0x...)
- Other: Solana (So...), Cardano (addr...), Bitcoin (bc1...), Tron (T...)

### 3️⃣ Create Configuration Files

**File 1: `api_keys.json`**
```json
{
  "moralis": {
    "apiKey": "eyJ..."  ← Your Moralis API Key here
  },
  "blockchair": {
    "apiKey": "e7a..."  ← Your Blockchair API Key here
  }
}
```

**File 2: `wallets.json`** (one address per line)
```json
{
  "ethereum": {
    "addresses": ["0xabcd1234", "0xefgh5678"]
  },
  "solana": {
    "addresses": ["9B5X3cG7NZ6rK8..."]
  },
  "cardano": {
    "addresses": ["addr1qy2n..."]
  },
  "polygon": {
    "addresses": ["0x1234abcd"]
  },
  "bitcoin": {
    "addresses": ["bc1qar..."]
  }
}
```

**File 3: `config.json`** (enable audit)
```json
{
  "general": {
    "run_audit": true,
    "create_db_backups": true
  },
  "accounting": {
    "method": "FIFO"
  },
  "performance": {
    "respect_free_tier_limits": true,
    "api_timeout_seconds": 30
  }
}
```

### 4️⃣ Run the Tax Engine

```bash
python Auto_Runner.py
```

**What It Does:**
1. ✅ Scans your Ledger addresses on blockchain
2. ✅ Finds all staking rewards (INCOME transactions)
3. ✅ Gets price data for each reward date
4. ✅ Creates tax reports
5. ✅ Validates wallet balances

**Output Example:**
```
--- 4. RUNNING AUDIT ---
   Checking ETH...
     ✓ Wallet balance: 32.5 ETH
     ✓ Staking rewards found: 147
     ✓ Total income (2024): 2.847 ETH @ $2,100 avg = $5,978.70
   Checking SOL...
     ✓ Wallet balance: 125.3 SOL
     ✓ Staking rewards found: 52
     ✓ Total income (2024): 8.392 SOL @ $25.50 avg = $214.00
--- AUDIT COMPLETE ---
```

### 5️⃣ Check Your Tax Reports

**Location:** `outputs/Year_YYYY/`

**Files Created:**
- ✅ `INCOME_REPORT.csv` → All staking rewards (for Schedule 1)
- ✅ `GENERIC_TAX_CAP_GAINS.csv` → Staking rewards bought/sold (Form 8949)
- ✅ `WALLET_AUDIT.csv` → Balance validation
- ✅ `US_TAX_LOSS_ANALYSIS.csv` → Capital gains/losses summary

---

## Common Issues & Fixes

### "No staking rewards found"
**Problem:** API key invalid or address format wrong

**Fix:**
```bash
# Verify API keys work:
# Moralis: Visit https://admin.moralis.io → Settings → Click "Test API"
# Blockchair: Visit https://blockchair.com → Dashboard → Check API key

# Verify address format:
# Ethereum: 0x + 40 hex chars (0xabcd1234567890...)
# Solana: 43-44 alphanumeric chars (9B5X3cG7NZ6rK8...)
# Cardano: addr1 + alphanumeric (addr1qy2n2xhtm...)
```

### "API rate limit exceeded"
**Problem:** Free tier limits (Moralis 50/min, Blockchair 5/min)

**Fix:** In `config.json`, set:
```json
{"performance": {"respect_free_tier_limits": true, "api_timeout_seconds": 60}}
```

### "Calculated balance ≠ real balance"
**Problem:** Missing trades in database

**Fix:**
1. Note discrepancy from audit
2. Check Ledger Live for missing deposits/withdrawals
3. Add to `inputs/manual_transactions.csv`:
```csv
date,coin,action,amount,price_usd,fee,source
2024-03-15,ETH,DEPOSIT,5.0,1700,0,LEDGER_TRANSFER
2024-03-15,SOL,DEPOSIT,50.0,25.50,0,LEDGER_TRANSFER
```

---

## Manual Fallback (if APIs don't work)

**Create `inputs/manual_transactions.csv`:**
```csv
date,coin,action,amount,price_usd,fee,source
2024-01-15,ETH,INCOME,0.025,1800,0,LEDGER_STAKING
2024-02-15,ETH,INCOME,0.026,1850,0,LEDGER_STAKING
2024-03-15,SOL,INCOME,0.5,25.50,0,LEDGER_STAKING
2024-04-15,ADA,INCOME,12.5,0.85,0,LEDGER_STAKING
```

**Get dates/amounts from:**
- Ledger Live → Accounts → Transaction history
- etherscan.io, solscan.io, cardanoscan.io (blockchain explorers)
- Export from staking provider (Lido, Jito, etc.)

---

## Tax Treatment

**Key Points:**
- ✅ Staking rewards = **INCOME** (taxed as ordinary income in year received)
- ✅ Report on **Schedule 1, Line 8** (2024 tax return)
- ✅ Use **FMV on date received** (not current price)
- ✅ When sold later, calculate **capital gain/loss** (long-term if >365 days)

**Example:**
```
2024-05-15: Receive 0.025 ETH staking reward
  Price: $2,500/ETH
  Income: 0.025 × $2,500 = $62.50 (reported on 2024 taxes)

2025-06-20: Sell that 0.025 ETH
  Price: $3,500/ETH
  Proceeds: 0.025 × $3,500 = $87.50
  Cost Basis: $62.50 (from staking reward)
  Capital Gain: $25.00 (long-term)
```

---

## Pro Tips

**🔐 Security:**
- Never commit `api_keys.json` to Git
- Use separate API keys for different tax years
- Rotate keys periodically

**⚡ Performance:**
- First run takes longer (scans all history)
- Subsequent runs are fast (incremental)
- Use `--year 2024` flag to focus on specific year

**🎯 Accuracy:**
- Run audit before any manual imports
- Fix balance discrepancies first
- Re-run after adding missing trades

**💡 Pro Setup (Multiple Wallets):**
```json
{
  "ethereum": {
    "addresses": [
      "0xLedger1...",
      "0xLedger2...",
      "0xMainnet..."
    ]
  },
  "solana": {
    "addresses": ["9B5X3cG7...", "Solo123..."]
  }
}
```

---

## Need Help?

**Setup Questions:**
- Ledger Live: https://support.ledger.com
- API Issues: Check Moralis/Blockchair status pages

**Tax Questions:**
- Consult CPA familiar with crypto
- IRS Publication 525 (Taxable and Nontaxable Income)
- CoinTracker Tax Guide (cryptocurrency guide)

**Debug:**
- Check `outputs/logs/` for detailed error messages
- Run with `--verbose` flag for debug output
- Test API keys independently before running full audit
