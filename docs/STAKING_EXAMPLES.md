# Staking Examples - Real-World Scenarios

Ready-to-use configurations for common staking setups. Copy and adapt to your situation.

---

## Scenario 1: Basic Ethereum Staker (Solo)

**Your Setup:**
- Ethereum mainnet, solo staking via wallet
- Want to track staking rewards only
- Single wallet address

**Files to Create:**

### `wallets.json`
```json
{
  "ethereum": {
    "addresses": ["0x742d35Cc6634C0532925a3b844Bc9e7595f42fbE"]
  }
}
```

### `config.json`
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

**Run:**
```bash
python Auto_Runner.py --year 2024
```

**Expected Output:**
```
Checking ETH...
  ✓ Wallet balance: 35.247 ETH
  ✓ Staking rewards: 156 transactions
  ✓ 2024 Income: 2.891 ETH @ $2,150 avg = $6,215.65
```

**Tax Impact:**
- Report $6,215.65 as cryptocurrency income on Schedule 1
- When you sell any ETH, it has $2,150 cost basis (average)

---

## Scenario 2: Multi-Validator Solana Staker

**Your Setup:**
- Stake with multiple validators (Jito, Marinade, etc.)
- Multiple wallet accounts
- Want reward tracking per validator

**Files to Create:**

### `wallets.json` (multiple addresses)
```json
{
  "solana": {
    "addresses": [
      "9B5X3cG7NZ6rK8hJ2pL9vQ1mR3sT5uV7wX9y1aB3cD",
      "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U",
      "BetaValidator123456789abcdefghij123456789"
    ]
  }
}
```

### `config.json`
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
    "api_timeout_seconds": 45
  }
}
```

**Expected Output:**
```
Checking SOL...
  ✓ Wallet 1 balance: 125.3 SOL
  ✓ Staking rewards: 52 transactions
  ✓ Wallet 2 balance: 89.7 SOL
  ✓ Staking rewards: 38 transactions
  ✓ Total 2024 Income: 8.392 SOL @ $25.50 avg = $214.00
```

**Tax Impact:**
- Report all SOL staking as one income line: $214.00
- System automatically de-duplicates rewards across validators
- Each reward gets correct date and price

---

## Scenario 3: Cardano Delegation + Staking Pools

**Your Setup:**
- Delegated to multiple stake pools
- Cardano mainnet via wallet
- Multiple accounts

**Files to Create:**

### `wallets.json`
```json
{
  "cardano": {
    "addresses": [
      "addr1qy2n2xhtmwhsqv3f8fqn7f3s8n5n8n8n8n8n8n8n8n8n8n8n8n",
      "addr1q9xd8f7cg8qw5v6r3t2u9z1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o"
    ]
  }
}
```

### `config.json`
```json
{
  "general": {
    "run_audit": true
  },
  "accounting": {
    "method": "FIFO"
  }
}
```

**Expected Output:**
```
Checking ADA...
  ✓ Wallet 1 balance: 5,000 ADA
  ✓ Delegation rewards: 18 epochs
  ✓ Wallet 2 balance: 3,500 ADA
  ✓ Delegation rewards: 18 epochs
  ✓ Total 2024 Income: 145.2 ADA @ $0.85 avg = $123.42
```

---

## Scenario 4: Multi-Chain Staker (Diversified)

**Your Setup:**
- Ethereum staking
- Solana staking
- Cardano delegation
- Polygon validator stake
- All via wallet

**Files to Create:**

### `wallets.json` (comprehensive)
```json
{
  "ethereum": {
    "addresses": ["0x742d35Cc6634C0532925a3b844Bc9e7595f42fbE"]
  },
  "solana": {
    "addresses": ["9B5X3cG7NZ6rK8hJ2pL9vQ1mR3sT5uV7wX9y1aB3cD"]
  },
  "cardano": {
    "addresses": ["addr1qy2n2xhtmwhsqv3f8fqn7f3s8n5n8n8n8n8n8n8n8n8n8n8n8n"]
  },
  "polygon": {
    "addresses": ["0x1234567890abcdef1234567890abcdef12345678"]
  },
  "avalanche": {
    "addresses": ["X-avax1234567890abcdef1234567890abcdef12345678"]
  }
}
```

### `config.json`
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
    "api_timeout_seconds": 60
  }
}
```

**Expected Output:**
```
--- 4. RUNNING AUDIT ---
   Checking ETH...
     ✓ Balance: 35.247 ETH
     ✓ 2024 Income: 2.891 ETH = $6,215.65
   Checking SOL...
     ✓ Balance: 125.3 SOL
     ✓ 2024 Income: 8.392 SOL = $214.00
   Checking ADA...
     ✓ Balance: 5,000 ADA
     ✓ 2024 Income: 145.2 ADA = $123.42
   Checking MATIC...
     ✓ Balance: 50,000 MATIC
     ✓ 2024 Income: 125.5 MATIC = $75.30
   Checking AVAX...
     ✓ Balance: 50 AVAX
     ✓ 2024 Income: 2.5 AVAX = $100.00
--- AUDIT COMPLETE ---

TOTAL 2024 STAKING INCOME: $6,728.37
```

**Tax Report:**
```
Schedule 1, Line 8: Cryptocurrency Staking Income
  Ethereum: $6,215.65
  Solana: $214.00
  Cardano: $123.42
  Polygon: $75.30
  Avalanche: $100.00
  ────────────────
  TOTAL: $6,728.37
```

---

## Scenario 5: Wallet + Manual Exchange Imports

**Your Setup:**
- Staking rewards via wallet (auto-detect)
- Exchange trades via CSV imports (Binance, Kraken, etc.)
- Want combined tax report

**Files to Create:**

### `wallets.json` (staking only)
```json
{
  "ethereum": {"addresses": ["0x..."]},
  "solana": {"addresses": ["..."]},
  "cardano": {"addresses": ["addr..."]},
  "bitcoin": {"addresses": ["bc1..."]}
}
```

### `config.json`
```json
{
  "general": {
    "run_audit": true,
    "create_db_backups": true
  },
  "accounting": {
    "method": "FIFO"
  }
}
```

### `inputs/manual_transactions.csv` (exchange trades)
```csv
date,coin,action,amount,price_usd,fee,source
2024-01-15,BTC,BUY,0.5,42000,10,KRAKEN
2024-02-20,ETH,BUY,5.0,2100,25,BINANCE
2024-03-15,SOL,BUY,100,25.50,50,KRAKEN
2024-06-10,BTC,SELL,0.25,65000,15,BINANCE
2024-09-20,ETH,SELL,2.5,2500,20,KRAKEN
```

**Run:**
```bash
python Auto_Runner.py --year 2024
```

**Expected Output:**
```
--- 1. IMPORTING MANUAL CSV ---
  ✓ Imported 5 transactions from manual_transactions.csv

--- 2. EXCHANGE INTEGRATION SKIPPED ---

--- 3. PROCESSING ---
  ✓ 5 buys processed
  ✓ 2 sells processed
  ✓ Realized gains: $2,547.50

--- 4. RUNNING AUDIT ---
  ✓ ETH staking: 2.891 ETH = $6,215.65 income
  ✓ SOL staking: 8.392 SOL = $214.00 income
  ✓ BTC staking: 0.15 BTC = $9,750.00 income

--- 5. TAX REPORT ---
  Total Income: $16,179.65
  Capital Gains: $2,547.50
```

---

## Scenario 6: High-Volume Staker (20+ Validators)

**Your Setup:**
- Professional staking operation
- Many wallet accounts
- Multiple chains
- High-frequency rewards

**Files to Create:**

### `wallets.json` (extensive)
```json
{
  "ethereum": {
    "addresses": [
      "0x742d35Cc6634C0532925a3b844Bc9e7595f42fbE",
      "0xabcd1234567890abcdef1234567890abcdef1234",
      "0xdef567890abcdef1234567890abcdef12345678"
    ]
  },
  "solana": {
    "addresses": [
      "9B5X3cG7NZ6rK8hJ2pL9vQ1mR3sT5uV7wX9y1aB3cD",
      "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U",
      "BetaValidator123456789abcdefghij123456789",
      "C5d6E7f8G9h0I1j2K3l4M5n6O7p8Q9r0S1t2U3v4W"
    ]
  },
  "cardano": {
    "addresses": [
      "addr1qy2n2xhtmwhsqv3f8fqn7f3s8n5n8n8n8n8n8n8n8n8n8n8n8n",
      "addr1q9xd8f7cg8qw5v6r3t2u9z1a2b3c4d5e6f7g8h9i0j1k2l3m4n5o",
      "addr1qyxb3l8t4d2h5j9k7m1n3p5q7r9s1u3v5w7x9z1a3b5c7d9e1f3g"
    ]
  }
}
```

### `config.json` (optimized for performance)
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
    "respect_free_tier_limits": false,
    "api_timeout_seconds": 60,
    "batch_size": 10
  }
}
```

**Note:** With many addresses, consider upgrading to paid API tiers:
- Moralis Paid: $49/month
- Blockchair Paid: $9/month

**Expected Results:**
- All staking income automatically categorized
- Multi-year history maintained
- Ready for CPA audit

---

## Testing Your Setup

### Before Full Run:

**Test API Keys:**
```bash
# Verify Moralis works
curl -X GET "https://api.moralis.io/api/v2/0x..." \
  -H "X-API-Key: YOUR_MORALIS_KEY"

# Verify Blockchair works  
curl "https://api.blockchair.com/bitcoin/..." \
  -H "X-API-Key: YOUR_BLOCKCHAIR_KEY"
```

**Test Single Chain:**
```bash
# Run just Ethereum first
# Comment out other blockchains in wallets.json temporarily
python Auto_Runner.py --year 2024
```

**Validate Results:**
1. Check outputs/Year_2024/INCOME_REPORT.csv
2. Verify dates match your wallet app
3. Verify amounts (within 0.0001 tolerance)

---

## Troubleshooting by Scenario

### "Ethereum staking rewards not found"
**Check:**
- Address is correct (0x + 40 hex chars)
- Address has actual staking rewards (check etherscan.io)
- Moralis API key valid and has sufficient credits
- Network is mainnet (not testnet)

### "Solana rewards incomplete"
**Check:**
- Address format correct (43-44 alphanumeric)
- Address has stake delegations
- Run with extended timeout: `api_timeout_seconds: 60`
- Check solscan.io for transaction history

### "Cardano showing wrong balance"
**Check:**
- Address is in your wallet app (copy exactly)
- Cardano blockchain explorer confirms balance
- Run `--year 2024` to limit to current year
- Try with `api_timeout_seconds: 90`

### "Multi-chain staker timing out"
**Solution:**
```json
{
  "performance": {
    "respect_free_tier_limits": true,
    "api_timeout_seconds": 90,
    "batch_size": 5
  }
}
```

Or upgrade to paid API tier.

---

## Final Tax Checklist

After running any scenario:

- [ ] ✅ Check INCOME_REPORT.csv for all staking rewards
- [ ] ✅ Verify dates match your wallet app history
- [ ] ✅ Verify amounts match blockchain explorer
- [ ] ✅ Check GENERIC_TAX_CAP_GAINS.csv for sold rewards (capital gains)
- [ ] ✅ Review WALLET_AUDIT.csv (current balances correct?)
- [ ] ✅ Run for all relevant tax years
- [ ] ✅ Keep all outputs as backup (7 years for IRS)

**Ready to file:**
- ✅ INCOME_REPORT.csv → Schedule 1 (Other Income)
- ✅ GENERIC_TAX_CAP_GAINS.csv → Form 8949 (Capital Gains)
- ✅ WALLET_AUDIT.csv → FBAR filing (if >$10k in foreign accounts)
