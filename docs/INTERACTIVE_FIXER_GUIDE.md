# Interactive Review Fixer - Usage Guide

## Overview

The Interactive Review Fixer is a command-line tool that helps you fix issues detected by the Tax Reviewer. It provides:

- **Guided fixing** - Walk through each issue step-by-step
- **Multiple options** - Choose how to fix each problem
- **Safe operation** - Automatic database backup before any changes
- **Interactive prompts** - You control what gets fixed

## How to Use

### 1. Run Tax Review First

```bash
python Crypto_Tax_Engine.py 2024
```

This will automatically run the Tax Reviewer and generate a report showing any issues.

### 2. Launch Interactive Fixer

```bash
python Interactive_Review_Fixer.py 2024
```

Replace `2024` with your tax year.

### 3. Follow the Prompts

The fixer will:
1. Load the most recent review report
2. Create a database backup
3. Walk you through each warning
4. Present fix options for each issue
5. Apply your chosen fixes
6. Show a summary of changes

## Issue Types & Fix Options

### NFT Collectibles

**Problem:** Assets that look like NFTs but don't have the `NFT-` prefix (may get wrong tax rate)

**Fix Options:**
1. **Auto-rename** - Adds `NFT-` prefix to all flagged assets
2. **Manual rename** - Choose which specific assets to rename
3. **Mark as ignore** - Skip (not recommended)
4. **Skip** - Leave as-is for manual review

**Example:**
```
Asset: BAYC#1234 (ID: nft1, Date: 2024-06-01)
  Rename to 'NFT-BAYC#1234'? (yes/no): yes
  ✓ Renamed: BAYC#1234 -> NFT-BAYC#1234
```

### Wash Sales

**Problem:** Sales followed by purchases of substantially identical assets within 61-day window (BTC→WBTC, ETH→STETH, USDC→USDC.E)

**Fix Options:**
1. **Export detailed report** - Creates report for CPA review
2. **Add note to records** - Flags transactions for attention
3. **Skip** - No database changes

**Note:** Wash sales are tax rule violations that can't be "fixed" - they require professional review.

### Missing Prices

**Problem:** Transactions with zero or missing USD prices (causes incorrect tax calculations)

**Fix Options:**
1. **Guided fix (recommended)**
  - If `wallets.json` exists, it infers chains and tries native-coin on-chain price (requires keys; ERC-20 still needs contract map).
  - Shows on-chain status (or unavailable reason) and Yahoo price side-by-side.
  - Suggests a value; you can accept, override, or skip each item.
2. **Set custom price** - Enter price manually for each transaction
3. **Set all to $0** - Mark as basis-only (no taxable income)
4. **Delete transactions** - Remove if spam/invalid
5. **Skip** - Leave as-is

**Example:**
```
BTC (Date: 2024-01-15, Amount: 1.5)
  Enter USD price: $42000
  ✓ Updated to $42000
```

### Duplicate Transactions

**Problem:** Identical transactions with different IDs (often from importing both API and CSV)

**Fix Options:**
1. **Auto-delete duplicates** - Keeps first occurrence, deletes rest
2. **Review each duplicate** - Choose which one to keep
3. **Skip** - Leave duplicates

**Example:**
```
Duplicate group: 2024-06-01_BTC_1.000000_BUY
  1. ID=api_123, Source=API, Batch=api_import
  2. ID=csv_456, Source=CSV, Batch=csv_import
Which one to KEEP? (1-2) or 'all' to skip: 1
  ✓ Deleted: csv_456
  ✓ Kept: api_123
```

### High Fees

**Problem:** Fees over $100 (possible fat-finger errors)

**Note:** These are in processed tax data and can't be directly modified. You must:
1. Note the transaction details shown
2. Edit your source CSV files
3. Re-import and re-run calculations

## Safety Features

### Automatic Backup

Before any changes, the fixer creates a timestamped backup:

```
✓ Database backup created: crypto_master_BEFORE_FIX_20241211_152030.db
```

### Rollback

To undo changes, simply restore the backup:

```bash
# Stop any running processes
# Replace the database with the backup
copy crypto_master_BEFORE_FIX_20241211_152030.db crypto_master.db
```

### Track Changes

All applied fixes are logged and summarized at the end:

```
FIX SUMMARY
================================================================================
Total fixes applied: 8

Breakdown:
  - rename: 3
  - price_update: 2
  - delete: 3

✓ Backup saved to: crypto_master_BEFORE_FIX_20241211_152030.db

IMPORTANT: Re-run tax calculations to see updated results:
  python Crypto_Tax_Engine.py 2024
```

## After Fixing

**Always re-run your tax calculations** to see the impact of changes:

```bash
python Crypto_Tax_Engine.py 2024
```

This will regenerate reports with your corrected data.

## Tips

1. **Start with obvious fixes** - Fix clear errors (missing prices, duplicates) first
2. **Consult professionals for wash sales** - These have complex tax implications
3. **Test on a copy** - If unsure, work on a copy of your database first
4. **Review the summary** - Check what was changed before re-running calculations
5. **Keep backups** - Don't delete the backup files until you're certain

## Troubleshooting

**Q: The fixer says "No review reports found"**  
A: Run `python Crypto_Tax_Engine.py 2024` first to generate a review report.

**Q: Can I undo changes?**  
A: Yes, restore the backup file created before the fixes.

**Q: Do I need to run the fixer every time?**  
A: No, only when the Tax Reviewer finds warnings you want to fix.

**Q: What if I accidentally fix the wrong thing?**  
A: Restore the backup and try again. The backup file is automatically created.

## Advanced Usage

### Specify Custom Report

Load a specific review report file:

```python
from Interactive_Review_Fixer import InteractiveReviewFixer
from Crypto_Tax_Engine import DatabaseManager

db = DatabaseManager()
fixer = InteractiveReviewFixer(db, 2024)
report = fixer.load_review_report("path/to/tax_review_2024_20241211.json")
```

### Batch Operations

For large-scale fixes, modify the fixer methods to skip prompts and apply fixes automatically.

## See Also

- [Tax Reviewer Documentation](KNOWN_LIMITATIONS.md) - Understanding what gets flagged
- [Main Engine Guide](../README.md) - Running tax calculations
- [Setup Guide](STAKING_SETUP.md) - Initial configuration
