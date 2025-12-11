# Staking Rewards - Tax Reporting Setup Guide

## Overview

This guide explains how to use the Crypto Tax Engine to **automatically detect and report staking rewards** from your wallets across multiple blockchains (Ethereum, Solana, Cardano, Polygon, etc.).

**Key Benefits:**
- ✅ Automatic staking reward detection via blockchain analysis
- ✅ No need to manually track staking transactions
- ✅ IRS-compliant income reporting (staking = taxable income at receipt date)
- ✅ Integration with your wallet addresses
- ✅ Support for 15+ staking blockchains

---

## What Gets Detected

The system uses two blockchain data sources (Moralis + Blockchair) to identify:

1. **Staking Rewards** (INCOME events)
   - Ethereum staking rewards → Treated as taxable income when received
   - Solana staking rewards → Tracked per validator and date
   - Cardano staking rewards → Detected from UTXOs
   - Polygon, Avalanche, Polkadot rewards → All supported

2. **Wallet Balances** (FBAR Reporting)
   - Maximum value of holdings (useful for FinCEN reporting if >$10k foreign)
   - Current holdings validation (ensures your tax calculations match reality)

3. **Transaction Audit**
   - Detects deposits/withdrawals to ensure FIFO matching is accurate
   - Flags missing trades that need manual entry

---

## Step 1: Get API Keys (3-5 minutes)

You need two API keys for blockchain data:

### Option A: Use Free Tiers (Recommended for <100 addresses)

**Moralis Free Tier** (EVM chains: Ethereum, Polygon, Avalanche, etc.)
1. Go to https://moralis.io/
2. Click "Start for Free"
3. Create account with email
4. Go to Admin Dashboard → Settings → Copy API Key
5. Save API Key (you'll need it)

**Blockchair Free Tier** (Bitcoin, Litecoin, Cardano, etc.)
1. Go to https://blockchair.com/api
2. Click "Signup" (free tier available)
3. Verify email
4. Dashboard → Copy API Key
5. Save API Key

### Option B: Paid Tiers (for >100 addresses or advanced queries)
- **Moralis Paid**: $49/month for 10M API credits
- **Blockchair Paid**: $9/month for unlimited requests

---

## Step 2: Configure API Keys

Create or update `api_keys.json` in your project root:

```json
{
  "moralis": {
    "apiKey": "YOUR_MORALIS_API_KEY_HERE"
  },
  "blockchair": {
    "apiKey": "YOUR_BLOCKCHAIR_API_KEY_HERE"
  }
}
```

**Security Note:** This file should be in `.gitignore` to prevent accidental key exposure.

---

## Step 3: Add Your Wallet Addresses to `wallets.json`

### Find Your Wallet Addresses

1. **Open your wallet app**
2. For each coin you've staked:
   - Click on the asset (ETH, SOL, ADA, etc.)
   - Click "Receive"
   - Copy the address (starts with 0x for Ethereum, So... for Solana, addr... for Cardano)

### Format Your wallets.json

**NEW FORMAT (Recommended):**
```json
{
  "ethereum": {
    "addresses": ["0x1234567890abcdef1234567890abcdef12345678"]
  },
  "solana": {
    "addresses": ["9B5X3cG7NZ6rK8hJ2pL9vQ1mR3sT5uV7wX9y1aB3c"]
  },
  "cardano": {
    "addresses": ["addr1qy2n2xhtmwhsqv3f8fqn7f3s8n5n8n8n8n8n8n8n8n8n8n8n8n"]
  },
  "polygon": {
    "addresses": ["0xabcdef1234567890abcdef1234567890abcdef12"]
  },
  "avalanche": {
    "addresses": ["X-avax1234567890abcdef1234567890abcdef1234"]
  }
}
```

**LEGACY FORMAT (Still Works):**
```json
{
  "ETH": ["0x1234567890abcdef1234567890abcdef12345678"],
  "SOL": ["9B5X3cG7NZ6rK8hJ2pL9vQ1mR3sT5uV7wX9y1aB3c"],
  "ADA": ["addr1qy2n2xhtmwhsqv3f8fqn7f3s8n5n8n8n8n8n8n8n8n8n8n8n8n"]
}
```

**Supported Blockchains:**
- EVM Chains (use Moralis): ethereum, polygon, binance, avalanche, fantom, cronos, arbitrum, optimism, gnosis, base, linea, moonbeam
- UTXO Chains (use Blockchair): bitcoin, litecoin, dogecoin, bitcoincash, dash, zcash, monero, ripple, stellar, eos, tron, cardano

---

## Step 4: Enable Wallet Audit in config.json

Update or create `config.json`:

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

**Key Setting:**
- `"run_audit": true` → Enables blockchain wallet analysis
- `"respect_free_tier_limits": true` → Slows down requests to stay within free tier limits

---

## Step 5: Run the Tax Engine

### Option A: Full Run (Imports + Audit)
```bash
python Auto_Runner.py
```

This will:
1. Import trades from your exchange CSVs
2. **Detect staking rewards** from your wallet addresses
3. Generate tax reports
4. Validate that calculated balances match real balances

### Option B: Audit Only (Skip Exchange Import)
```bash
python Crypto_Tax_Engine.py --audit-only
```

---

## What Happens During Audit

When `run_audit: true`, the system:

### 1. Connects to Blockchain APIs
- Moralis for Ethereum, Polygon, BSC, etc.
- Blockchair for Bitcoin, Litecoin, Cardano, etc.

### 2. Scans Your Wallet Address
- Looks for **INCOME transactions** = staking rewards
- Looks for **token transfers in/out** = deposits/withdrawals
- Calculates **current balance**

### 3. Logs Results
Example output:
```
--- 4. RUNNING AUDIT ---
   Checking ETH...
     ✓ Current balance: 32.5 ETH
     ✓ Found 147 staking rewards (2023)
     ✓ Total staking income 2023: 2.847 ETH
   Checking SOL...
     ✓ Current balance: 125.3 SOL
     ✓ Found 52 staking rewards (2023)
     ✓ Total staking income 2023: 8.392 SOL
   Checking ADA...
     ✓ Current balance: 5,000 ADA
     ✓ Found 18 reward epochs (2023)
```

### 4. Validates Against Your Wallet
- **CRITICAL**: If audit shows balance mismatch, check for missing trades
- Discrepancies = missing buys/sells/deposits/withdrawals
- Add missing trades to `inputs/manual_transactions.csv`

---

## Staking Rewards Tax Treatment

### How the System Records Staking Rewards

When staking rewards are detected, the system:

1. **Creates INCOME records** with:
   - `action` = "INCOME"
   - `coin` = the staking coin (ETH, SOL, ADA, etc.)
   - `amount` = reward amount
   - `price_usd` = price on the reward date
   - `date` = when reward was received

2. **Adds to Cost Basis**
   - Staking rewards become part of your tax basis
   - When you later sell, you'll have capital gains/losses

### Example Tax Impact

**Ethereum Staking:**
```
2023-05-15: Receive 0.025 ETH staking reward @ $1,800/ETH
  → $45 of taxable income (need to pay taxes on $45 this year)

2024-06-20: Sell that 0.025 ETH @ $2,500/ETH
  → Proceeds: $62.50
  → Cost Basis: $45
  → Capital Gain: $17.50 (long-term since >365 days)
```

---

## Handling Staking Rewards Manually

If API access isn't working, you can manually add staking rewards:

### Create `inputs/manual_transactions.csv`

```csv
date,coin,action,amount,price_usd,fee,source
2023-05-15,ETH,INCOME,0.025,1800,0,STAKING
2023-05-22,ETH,INCOME,0.025,1850,0,STAKING
2023-06-10,SOL,INCOME,0.5,25.50,0,STAKING
```

**Column Definitions:**
- `date`: When you received the reward (YYYY-MM-DD)
- `coin`: BTC, ETH, SOL, ADA, etc.
- `action`: Always "INCOME" for staking rewards
- `amount`: How much you received (decimals OK: 0.025, 0.5, 0.001)
- `price_usd`: USD price of the coin on that date (e.g., CoinGecko)
- `fee`: Almost always 0 for staking rewards
- `source`: "STAKING" or "REWARDS"

---

## Finding Historical Staking Rewards

### From Your Wallet App

1. Open your wallet application
2. Click on your account (ETH, SOL, etc.)
3. Look for "Rewards" tab or filter by transaction type
4. Export (if available) or manually note down:
   - Date received
   - Amount
   - Your balance at that time

### From Blockchain Explorers

**Ethereum (etherscan.io):**
1. Go to https://etherscan.io
2. Paste your address: `0x...`
3. Look for "ERC-20 Token Transfer Events" or "Staking Withdrawals"
4. Note the dates and amounts

**Solana (solscan.io):**
1. Go to https://solscan.io
2. Paste your address: `Solanaaaa...`
3. Filter by token: "SOL"
4. Look for deposit transactions (these are rewards)

**Cardano (cardanoscan.io):**
1. Go to https://cardanoscan.io
2. Paste your address: `addr1qy...`
3. Look for "Rewards" section
4. Download CSV if available

---

## Troubleshooting

### "API Rate Limit Exceeded"
**Cause:** Free tier limits (Moralis: 50 req/min, Blockchair: 5 req/min)

**Solution:**
```json
{
  "performance": {
    "respect_free_tier_limits": true,
    "api_timeout_seconds": 60
  }
}
```

### "Calculated Balance != Real Balance"
**Cause:** Missing trades in your database

**Solution:**
1. Note the discrepancy from audit output
2. Check your wallet app for missing deposits/withdrawals
3. Add to `inputs/manual_transactions.csv`:
   ```csv
   2023-03-15,ETH,DEPOSIT,5.0,1700,0,WALLET_TRANSFER
   ```

### "Staking Rewards Not Found"
**Cause:** 
- API key invalid
- Wrong address format
- Rewards older than blockchain data (rare)

**Solution:**
- Verify API keys in `api_keys.json`
- Verify address format (0x... for Ethereum, etc.)
- Use manual CSV import as fallback

---

## Supported Staking Blockchains

| Blockchain | Min Stake | Wallet Support | Tax Treatment | Notes |
|-----------|----------|---|---|---|
| **Ethereum (Staking)** | 0.0001 ETH | ✅ Wallets | Income | Rewards on-chain |
| **Solana** | 0.000001 SOL | ✅ Wallets | Income | Tracked per validator |
| **Cardano** | 1 ADA | ✅ Wallets | Income | Rewards per epoch |
| **Polygon** | None (PoS validator) | ✅ Wallets | Income | Requires 1M MATIC min |
| **Avalanche** | None | ✅ Wallets | Income | Delegation rewards |
| **Polkadot** | 1.6 DOT | ✅ Wallets | Income | Nominators + validators |
| **Cosmos** | 1 ATOM | ✅ Wallets | Income | Delegation rewards |
| **Tezos** | 1 XTZ | ✅ Wallets | Income | Baker rewards |

---

## IRS Compliance Notes

**Staking Rewards are INCOME:**
- ✅ Must report in year received (not when sold)
- ✅ Use FMV on date of receipt
- ✅ Subject to ordinary income tax (not capital gains rates initially)
- ✅ If later sold, subject to long/short-term capital gains

**Example for 2024 Tax Filing:**
```
Form 1040, Schedule 1 (Other Income):
  Cryptocurrency Staking Rewards: $1,247

Form 8949 (Capital Gains/Losses):
  Staking rewards sold: $1,500 proceeds, $1,247 cost basis
  Capital gain: $253 (long-term if held >365 days)
```

---

## Next Steps

1. ✅ Get API keys (Moralis + Blockchair)
2. ✅ Add API keys to `api_keys.json`
3. ✅ Add wallet addresses to `wallets.json`
4. ✅ Set `run_audit: true` in `config.json`
5. ✅ Run `python Auto_Runner.py`
6. ✅ Review audit output for missing trades
7. ✅ Generate tax reports (Form 8949 ready)

---

## Questions?

For blockchain-specific issues:
- **Ethereum**: Check etherscan.io for address/transaction format
- **Solana**: Use solscan.io to verify wallet activity
- **Cardano**: Use cardanoscan.io for reward tracking
- **Multi-chain**: Run audit separately for each chain to debug

For tax questions, consult a CPA who understands crypto staking regulations (varies by jurisdiction).
