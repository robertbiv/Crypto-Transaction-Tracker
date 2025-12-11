"""
Migration_2025.py

Safe Harbor allocator for Jan 1, 2025 transition to per-wallet cost-basis silos.

Usage:
    python Migration_2025.py --year 2024 \
        --targets wallet_allocation_targets_2025.json \
        --output INVENTORY_INIT_2025.json

Inputs:
- Database: crypto_master.db (full history)
- Targets JSON: {"BTC": {"COINBASE": 1.5, "LEDGER": 0.8}, ...}
  (represents real-world balances per wallet/account as of 12/31/2024)

Output:
- INVENTORY_INIT_2025.json with structure {coin: {source: [ {"a": str, "p": str, "d": "YYYY-MM-DD"} ]}}

Algorithm:
- Build a UNIVERSAL lot pool (ignoring source) from full trade history up to Dec 31, 2024.
- Sort lots by highest cost basis first (tax-efficient for planned sells).
- Allocate lots into wallet buckets to satisfy target balances.
- If targets exceed available lots, allocation is truncated and a warning is printed.
"""

import argparse
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

import Crypto_Tax_Engine as app

CUTOFF_DATE = datetime(2024, 12, 31)


def build_universal_lots(db):
    """Recreate a universal FIFO lot pool ignoring source (for 2024 history)."""
    df = db.get_all()
    df['date_dt'] = pd.to_datetime(df['date'])
    df = df[df['date_dt'] <= CUTOFF_DATE].sort_values('date_dt')
    lots = {}
    for _, t in df.iterrows():
        coin = t['coin']
        action = t['action']
        amt = app.to_decimal(t['amount'])
        price = app.to_decimal(t['price_usd'])
        fee = app.to_decimal(t['fee'])
        d = t['date_dt']
        if coin not in lots:
            lots[coin] = []
        if action in ['BUY', 'INCOME', 'GIFT_IN', 'DEPOSIT']:
            basis = price if action != 'DEPOSIT' else Decimal('0')
            lots[coin].append({'a': amt, 'p': basis, 'd': d})
        elif action in ['SELL', 'SPEND', 'LOSS', 'WITHDRAWAL']:
            # reduce using FIFO within universal pool
            rem = amt
            lots[coin].sort(key=lambda x: x['d'])
            while rem > 0 and lots[coin]:
                lot = lots[coin][0]
                take = lot['a'] if lot['a'] <= rem else rem
                lot['a'] -= take
                rem -= take
                if lot['a'] <= Decimal('0.00000001'):
                    lots[coin].pop(0)
        # TRANSFER ignored for universal pool (was non-taxable previously)
    # prune empties
    for c in list(lots.keys()):
        lots[c] = [l for l in lots[c] if l['a'] > Decimal('0.00000001')]
        if not lots[c]:
            lots.pop(c, None)
    return lots


def allocate(lots, targets):
    """Allocate universal lots into per-source buckets based on targets (amount per source)."""
    result = {}
    for coin, coin_lots in lots.items():
        if coin not in targets:
            continue
        # Sort by highest cost basis first (tax-loss-harvest friendly)
        coin_lots = sorted(coin_lots, key=lambda x: x['p'], reverse=True)
        remaining = list(coin_lots)
        result[coin] = {}
        for source, needed in targets[coin].items():
            need = Decimal(str(needed))
            if need <= 0:
                continue
            result[coin][source] = []
            while need > 0 and remaining:
                lot = remaining[0]
                move_amt = lot['a'] if lot['a'] <= need else need
                result[coin][source].append({
                    'a': str(move_amt.quantize(Decimal('0.00000001'))),
                    'p': str(lot['p']),
                    'd': lot['d'].strftime('%Y-%m-%d')
                })
                lot['a'] -= move_amt
                need -= move_amt
                if lot['a'] <= Decimal('0.00000001'):
                    remaining.pop(0)
            if need > 0:
                print(f"[WARN] Unable to fully satisfy {coin} for {source}. Short by {need}.")
    return result


def main():
    parser = argparse.ArgumentParser(description="Safe Harbor allocation for 2025 per-wallet basis")
    parser.add_argument('--year', type=int, default=2024, help='Cutoff year (default 2024)')
    parser.add_argument('--targets', type=str, default='wallet_allocation_targets_2025.json', help='JSON file with per-wallet targets')
    parser.add_argument('--output', type=str, default='INVENTORY_INIT_2025.json', help='Output allocation file')
    args = parser.parse_args()

    global CUTOFF_DATE
    CUTOFF_DATE = datetime(args.year, 12, 31)

    targets_path = Path(args.targets)
    if not targets_path.exists():
        print(f"[ERROR] Targets file not found: {targets_path}")
        return 1

    targets = json.loads(targets_path.read_text())

    db = app.DatabaseManager()
    lots = build_universal_lots(db)
    allocation = allocate(lots, targets)

    out_path = Path(args.output)
    out_path.write_text(json.dumps(allocation, indent=2))
    print(f"[OK] Wrote allocation to {out_path}")
    db.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
