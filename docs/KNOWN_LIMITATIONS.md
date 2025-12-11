# Known Architectural Limitations

## 1. ✅ FIXED: Fee Currency Assumption

**Status:** ✅ **RESOLVED in v39** (December 2025)

The database schema now supports `fee_coin` field to specify the actual currency of transaction fees, eliminating the previous assumption that fees are always in the same coin being transferred.

### What Changed

- **New Column:** `fee_coin TEXT` in trades table
- **Backward Compatible:** If `fee_coin` is NULL, falls back to transfer coin (old behavior)
- **CSV Support:** Users can now specify `fee_coin` when importing
- **Auto-Migration:** Existing databases automatically upgrade on first run

### How It Works

**Before (Broken):**
```
TRANSFER 100 USDC, fee=0.05 ETH
→ Incorrectly treats 0.05 as USDC disposition
→ Creates phantom USDC loss
```

**After (Fixed):**
```
TRANSFER 100 USDC, fee=0.05, fee_coin='ETH'
→ Correctly treats 0.05 ETH as ETH disposition
→ Matches against ETH cost basis, not USDC
```

### User Guide

**CSV Format:**
```csv
date,action,coin,amount,price_usd,fee,fee_coin,source
2024-02-01,TRANSFER,USDC,100,1.0,0.05,ETH,WALLET
2024-01-15,BUY,USDC,100,1.0,0,NULL,COINBASE
2024-01-10,BUY,ETH,1,2000,0,NULL,COINBASE
```

**Programmatic:**
```python
db.save_trade({
    'action': 'TRANSFER',
    'coin': 'USDC',
    'amount': 100,
    'fee': 0.05,
    'fee_coin': 'ETH',  # ← New field
    'price_usd': 1.0
})
```

### Tax Accuracy Impact
- **Before:** ERC-20 transfers with ETH fees created tiny phantom token losses
- **After:** Gas fees correctly attributed to ETH, not the token
- **Backward Compat:** Existing CSV files without `fee_coin` still work (falls back to old behavior)

### Test Coverage
- ✅ Multi-coin fee scenario (ERC-20 + ETH)
- ✅ Backward compatibility (fee_coin=NULL)
- ✅ Price fetcher correctly retrieves fee_coin price
- ✅ Holdings snapshot reflects correct coin deductions

---

## 2. Stablecoin Price Handling

### Current Behavior
Stablecoins (USDC, USDT, DAI, USD) always return 1.0 for price, regardless of cache or market data.

### Trade-off
- **Benefit:** Eliminates tiny rounding errors from stablecoin price volatility
- **Risk:** If a stablecoin depegs, this won't reflect it (edge case, rare)

---

## 3. Constructive Receipt Toggle Not IRS-Validated

The `staking_taxable_on_receipt` flag treats staking as income at receipt, but:
- ✅ Aligns with IRS Revenue Ruling 2019-24 (current guidance)
- ⚠️ Tax law may change (awaiting final staking guidance)
- 📋 Always consult a CPA for your specific situation

---

## 4. HIFO Sorting Limitations

HIFO (Highest-In, First-Out) support exists but:
- Only sorts by acquisition price, not purchase date
- Does not account for tax loss harvesting rules
- No "avoid wash sale" optimization

**Current:** Sells highest-cost lots first
**Not Supported:** Complex portfolio optimization strategies

---

## Future Enhancements

1. **Advanced HIFO** (Priority: Low)
   - Sort by price *and* date for wash sale avoidance
   - Suggest tax-loss harvesting opportunities

2. **Foreign Staking Tax Rules** (Priority: High)
   - Different countries have different staking tax treatment
   - Currently only US rules implemented

3. **DeFi Yield Protocol Integration** (Priority: Low)
   - Lido, Aave, Curve fee tracking
   - Complex multi-coin LP fee handling

