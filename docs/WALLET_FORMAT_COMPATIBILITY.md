## Wallet Format Compatibility with StakeTaxCSV

### Summary
✅ **YES - StakeTaxCSV will be able to read and use the wallets.json format created by Setup.py**

The updated system now supports **both nested and flat wallet formats**, ensuring full compatibility with StakeTaxCSV and backward compatibility with older configurations. Auditor maps symbols (e.g., BTC) to full Blockchair paths (e.g., bitcoin).

---

## Wallet Format Details

### NEW Format (Updated Setup.py) - RECOMMENDED
```json
{
  "ethereum": {
    "addresses": ["0xAddress1", "0xAddress2"]
  },
  "bitcoin": {
    "addresses": ["bc1Address1", "bc1Address2"]
  },
  "solana": {
    "addresses": ["SolanaAddress1"]
  }
}
```

**Advantages:**
- Clear blockchain naming (ethereum, bitcoin, solana)
- Structured hierarchically with explicit "addresses" key
- Matches README examples
- Easy to understand and maintain

### LEGACY Format (Old Setup.py) - STILL SUPPORTED
```json
{
  "ETH": ["0xAddress1", "0xAddress2"],
  "BTC": ["bc1Address1", "bc1Address2"],
  "SOL": "SolanaAddress1"
}
```

**Advantages:**
- Backward compatible with existing wallets.json files
- Simpler flat structure
- No breaking changes for existing users

---

## How StakeTaxCSV Integration Works

1. **Wallet Extraction** (`StakeTaxCSVManager._get_wallets_from_file()`):
   - Reads wallets.json in either format
   - Extracts all wallet addresses
   - Filters out "PASTE_*" placeholders
   - Returns deduplicated list: `["0xAddress1", "bc1Address1", "SolanaAddress1", ...]`

2. **CLI Invocation**:
   ```bash
   staketaxcsv --wallet "0xAddress1,bc1Address1,SolanaAddress1" \
               --protocol "all" \
               --output "inputs/staketax_generated/staking_*.csv"
   ```

3. **CSV Import**:
   - StakeTaxCSV auto-detects wallet types (Ethereum, Bitcoin, Solana, etc.)
   - Generates tax-ready CSV with staking rewards
   - Rewards are imported with deduplication

---

## Wallet Format Conversion (if needed)

### From OLD (Flat) to NEW (Nested)

**Before:**
```json
{
  "ETH": ["0x123abc"],
  "BTC": ["bc1abc"],
  "SOL": "SolanaAddr1"
}
```

**After:**
```json
{
  "ethereum": {"addresses": ["0x123abc"]},
  "bitcoin": {"addresses": ["bc1abc"]},
  "solana": {"addresses": ["SolanaAddr1"]}
}
```

**Migration:** Simply run Setup.py again - it will automatically update your wallets.json to the nested format while preserving existing addresses.

---

## Blockchain Name Mapping

The system includes a built-in mapping to convert blockchain names to coin symbols:

| Blockchain Name | Coin Symbol | Moralis/Blockchair Support |
|---|---|---|
| ethereum | ETH | Moralis ✓ |
| polygon | MATIC | Moralis ✓ |
| binance | BNB | Moralis ✓ |
| solana | SOL | Moralis ✓ |
| bitcoin | BTC | Blockchair ✓ |
| litecoin | LTC | Blockchair ✓ |
| dogecoin | DOGE | Blockchair ✓ |
| avalanche | AVAX | Moralis ✓ |
| fantom | FTM | Moralis ✓ |
| arbitrum | ARBITRUM | Moralis ✓ |
| optimism | OPTIMISM | Moralis ✓ |
| base | BASE | Moralis ✓ |

*(and 10+ more supported chains)*

---

## Compatibility Testing

All wallet extraction scenarios have been tested:

✓ Nested format (new Setup.py)
✓ Flat format (legacy)  
✓ Mixed nested and flat (hybrid)
✓ Single string addresses
✓ Multiple addresses per blockchain
✓ PASTE_ placeholder filtering
✓ Metadata field skipping (_INSTRUCTIONS)

---

## Configuration

When running StakeTaxCSV auto-import via Auto_Runner.py:

```json
{
  "staking": {
    "enabled": true,
    "protocols_to_sync": ["all"]
  }
}
```

The system will:
1. Read wallets.json (any format)
2. Extract all wallet addresses
3. Pass them to staketaxcsv CLI
4. Import generated CSV with deduplication
5. Archive processed CSV

---

## Conclusion

✅ **StakeTaxCSV is fully compatible with both wallet formats**
✅ **Setup.py now creates the cleaner nested format**
✅ **Backward compatibility with old flat format is maintained**
✅ **Automatic blockchain name to symbol conversion included**
