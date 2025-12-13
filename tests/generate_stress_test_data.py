import csv
import random
import os
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

# Configuration
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'stress_test_data')
NUM_TRANSACTIONS = 500
START_DATE = datetime(2023, 1, 1)
END_DATE = datetime(2024, 12, 31)
COINS = ['BTC', 'ETH', 'SOL', 'ADA', 'DOT', 'MATIC', 'AVAX']
FILES = ['binance_history.csv', 'coinbase_pro.csv', 'ledger_live.csv', 'metamask_polygon.csv', 'kraken_sim.csv', 'gemini_sim.csv']

# Mock Price Data (Base prices)
PRICES = {
    'BTC': 20000, 'ETH': 1500, 'SOL': 20, 'ADA': 0.3, 'DOT': 5, 'MATIC': 0.8, 'AVAX': 15,
    'MYSTERY': 100, 'JUNK': 0.0001, 'WASH': 50
}

# Tracking for Expected Output
holdings = {c: Decimal('0') for c in COINS + ['MYSTERY', 'JUNK', 'WASH']}
# fifo_queue = {c: [] for c in COINS + ['MYSTERY', 'JUNK', 'WASH']} # List of (amount, cost_basis_per_unit, date_acquired)

expected_stats = {
    'total_income': Decimal('0'),
    'short_term_gains': Decimal('0'),
    'long_term_gains': Decimal('0'),
    'total_fees': Decimal('0'),
    'transaction_count': 0
}

expected_warnings = []

transactions = []

def get_price(coin, date):
    # Simple price simulation: Base * (1 + 0.001 * days_since_start) + random_noise
    days = (date - START_DATE).days
    base = PRICES.get(coin, 10)
    trend = 1 + (days * 0.0005) # Slight upward trend
    noise = random.uniform(0.9, 1.1)
    return Decimal(str(base * trend * noise)).quantize(Decimal('0.01'))

def add_transaction(tx):
    transactions.append(tx)
    expected_stats['transaction_count'] += 1

def inject_anomalies():
    """Injects specific transactions designed to trigger warnings"""
    
    # 1. Missing Basis (Strict Mode Warning)
    # Sell a coin we never bought
    d_missing = (START_DATE + timedelta(days=10)).replace(microsecond=0)
    tx_missing = {
        'date': d_missing.isoformat(),
        'type': 'SELL',
        'sent_coin': 'MYSTERY',
        'sent_amount': Decimal('10.0'),
        'price_usd': Decimal('100.0'),
        'fee': Decimal('1.0'),
        'fee_coin': 'USD'
    }
    add_transaction(tx_missing)
    expected_warnings.append("MISSING BASIS: 10.0 MYSTERY sold from ... (Strict Mode)")

    # 2. Zero Price (Price Fetcher Warning)
    # Income with 0 price
    d_zero = (START_DATE + timedelta(days=20)).replace(microsecond=0)
    tx_zero = {
        'date': d_zero.isoformat(),
        'type': 'INCOME',
        'received_coin': 'JUNK',
        'received_amount': Decimal('1000.0'),
        'price_usd': Decimal('0'),
        'fee': Decimal('0'),
        'fee_coin': 'USD'
    }
    add_transaction(tx_zero)
    expected_warnings.append("Zero Price: Engine will attempt to fetch price for JUNK")

    # 3. Wash Sale (Tax Event)
    # Buy WASH at 100, Sell at 50 (Loss), Buy again within 30 days
    d1 = (START_DATE + timedelta(days=100)).replace(microsecond=0)
    d2 = (d1 + timedelta(days=5)).replace(microsecond=0)
    d3 = (d2 + timedelta(days=10)).replace(microsecond=0)
    
    # Buy 1
    add_transaction({
        'date': d1.isoformat(), 'type': 'BUY', 'received_coin': 'WASH', 'received_amount': Decimal('1.0'), 'price_usd': Decimal('100.0'), 'fee': Decimal('0'), 'fee_coin': 'USD'
    })
    
    # Sell 1 (Loss of 50)
    add_transaction({
        'date': d2.isoformat(), 'type': 'SELL', 'sent_coin': 'WASH', 'sent_amount': Decimal('1.0'), 'price_usd': Decimal('50.0'), 'fee': Decimal('0'), 'fee_coin': 'USD'
    })
    
    # Buy 2 (Trigger Wash Sale)
    add_transaction({
        'date': d3.isoformat(), 'type': 'BUY', 'received_coin': 'WASH', 'received_amount': Decimal('1.0'), 'price_usd': Decimal('60.0'), 'fee': Decimal('0'), 'fee_coin': 'USD'
    })
    expected_warnings.append("WASH SALE: Loss on WASH sale should be disallowed")

def process_buy(coin, amount, price, date, fee=Decimal('0')):
    # Strip microseconds for consistency
    date = date.replace(microsecond=0)
    
    holdings[coin] += amount
    
    return {
        'date': date.isoformat(),
        'type': 'BUY',
        'received_coin': coin,
        'received_amount': amount,
        'price_usd': price,
        'fee': fee,
        'fee_coin': 'USD'
    }

def process_sell(coin, amount, price, date, fee=Decimal('0')):
    # Strip microseconds for consistency
    date = date.replace(microsecond=0)

    if holdings[coin] < amount:
        return None # Cannot sell what we don't have
    
    holdings[coin] -= amount

    return {
        'date': date.isoformat(),
        'type': 'SELL',
        'sent_coin': coin,
        'sent_amount': amount,
        'price_usd': price,
        'fee': fee,
        'fee_coin': 'USD'
    }

def process_income(coin, amount, price, date, type='STAKING'):
    # Strip microseconds for consistency
    date = date.replace(microsecond=0)

    holdings[coin] += amount

    return {
        'date': date.isoformat(),
        'type': type,
        'received_coin': coin,
        'received_amount': amount,
        'price_usd': price,
        'fee': 0,
        'fee_coin': 'USD'
    }

def calculate_tax_results(txs):
    """
    Re-implements the tax engine logic (FIFO + Wash Sales) to generate accurate expected stats.
    """
    print("Calculating Expected Stats with Tax Logic (FIFO + Wash Sales)...")
    
    # Reset stats
    stats = {
        'total_income': Decimal('0'),
        'short_term_gains': Decimal('0'),
        'long_term_gains': Decimal('0'),
        'total_fees': Decimal('0')
    }
    
    # Sort by date
    txs.sort(key=lambda x: x['date'])
    
    batches = {}  # coin -> list of {amount, cost_per_unit, date}
    wash_sale_adjustments = {} # (coin, date_iso) -> amount_to_add_to_basis

    # Helper to find replacement
    def find_replacement_date(coin, sell_date, loss_amount):
        sell_dt = datetime.fromisoformat(sell_date)
        start = sell_dt - timedelta(days=30)
        end = sell_dt + timedelta(days=30)
        
        for t in txs:
            if t.get('type') in ['BUY', 'INCOME', 'TRADE'] and t.get('received_coin') == coin:
                t_dt = datetime.fromisoformat(t['date'])
                if start <= t_dt <= end and t_dt != sell_dt:
                    return t['date']
        return None

    for t in txs:
        date_iso = t['date']
        date = datetime.fromisoformat(date_iso)
        type = t['type']
        
        # 1. Handle INCOMING (Buy, Income, Receive part of Swap)
        if type in ['BUY', 'INCOME'] or (type == 'TRADE' and 'received_coin' in t):
            coin = t.get('received_coin')
            if not coin: continue
            
            amount = t['received_amount']
            price = t['price_usd']
            
            cost_basis = (amount * price)
            if t.get('fee_coin') == 'USD':
                cost_basis += t['fee']
                stats['total_fees'] += t['fee']
            
            # Check for Wash Sale Adjustments (Future replacements that are now happening)
            adj_key = (coin, date_iso)
            if adj_key in wash_sale_adjustments:
                adjustment = wash_sale_adjustments[adj_key]
                cost_basis += adjustment
            
            cost_per_unit = cost_basis / amount if amount > 0 else Decimal('0')
            
            if coin not in batches: batches[coin] = []
            batches[coin].append({
                'amount': amount,
                'cost': cost_per_unit,
                'date': date
            })
            
            if type == 'INCOME':
                stats['total_income'] += (amount * price)

        # 2. Handle OUTGOING (Sell, Send part of Swap)
        if type in ['SELL'] or (type == 'TRADE' and 'sent_coin' in t):
            coin = t.get('sent_coin')
            if not coin: continue
            
            amount = t['sent_amount']
            price = t['price_usd']
            fee = t['fee'] if t.get('fee_coin') == 'USD' else Decimal('0')
            
            if t.get('fee_coin') == 'USD':
                stats['total_fees'] += t['fee']
            
            # FIFO Consumption
            remaining = amount
            
            if coin not in batches: batches[coin] = []
            
            # Consume batches
            while remaining > 0 and batches[coin]:
                batch = batches[coin][0]
                take = min(remaining, batch['amount'])
                
                cost_chunk = take * batch['cost']
                proceeds_chunk = take * price
                
                # Fee allocation (pro-rated)
                fee_chunk = fee * (take / amount)
                
                gain = proceeds_chunk - cost_chunk - fee_chunk
                
                # Wash Sale Check
                if gain < 0:
                    replacement_date = find_replacement_date(coin, date_iso, abs(gain))
                    if replacement_date:
                        # Disallow loss
                        loss_amount = abs(gain)
                        gain = Decimal('0')
                        
                        # Add to replacement basis
                        rep_key = (coin, replacement_date)
                        if rep_key not in wash_sale_adjustments:
                            wash_sale_adjustments[rep_key] = Decimal('0')
                        wash_sale_adjustments[rep_key] += loss_amount
                        
                        # If replacement is in the PAST (already in batches), update it now
                        rep_dt = datetime.fromisoformat(replacement_date)
                        if rep_dt < date:
                            # Find it in batches
                            for b in batches[coin]:
                                if b['date'] == rep_dt:
                                    # Update cost per unit
                                    # New Total Cost = (Old Cost * Amount) + Adjustment
                                    # New Cost Per Unit = New Total Cost / Amount
                                    total_c = (b['cost'] * b['amount']) + loss_amount
                                    b['cost'] = total_c / b['amount']
                                    break
                
                is_long = (date - batch['date']).days > 365
                if is_long: stats['long_term_gains'] += gain
                else: stats['short_term_gains'] += gain
                
                batch['amount'] -= take
                remaining -= take
                if batch['amount'] <= 0:
                    batches[coin].pop(0)
            
            # If we ran out of batches (Missing Basis)
            if remaining > 0:
                # Treat as 0 cost basis
                proceeds_chunk = remaining * price
                fee_chunk = fee * (remaining / amount)
                gain = proceeds_chunk - fee_chunk
                stats['short_term_gains'] += gain

    return stats

def generate_data():
    current_date = START_DATE
    random.seed(42) # Deterministic
    
    while current_date <= END_DATE:
        # 0-3 transactions per day
        daily_txs = random.randint(0, 3)
        
        for _ in range(daily_txs):
            action = random.choices(['BUY', 'SELL', 'INCOME', 'SWAP'], weights=[0.4, 0.3, 0.2, 0.1])[0]
            coin = random.choice(COINS)
            price = get_price(coin, current_date)
            
            if action == 'BUY':
                amount = Decimal(str(random.uniform(0.1, 2.0))).quantize(Decimal('0.0001'))
                fee = Decimal('1.00')
                tx = process_buy(coin, amount, price, current_date, fee)
                add_transaction(tx)
                
            elif action == 'SELL':
                amount = Decimal(str(random.uniform(0.1, 1.0))).quantize(Decimal('0.0001'))
                fee = Decimal('1.00')
                tx = process_sell(coin, amount, price, current_date, fee)
                if tx: add_transaction(tx)
                
            elif action == 'INCOME':
                amount = Decimal(str(random.uniform(0.01, 0.1))).quantize(Decimal('0.0001'))
                type = random.choice(['STAKING', 'MINING', 'AIRDROP'])
                tx = process_income(coin, amount, price, current_date, type)
                add_transaction(tx)
                
            elif action == 'SWAP':
                # Sell Coin A, Buy Coin B
                coin_sell = coin
                coin_buy = random.choice([c for c in COINS if c != coin_sell])
                price_sell = price
                price_buy = get_price(coin_buy, current_date)
                
                amount_sell = Decimal(str(random.uniform(0.1, 1.0))).quantize(Decimal('0.0001'))
                
                # Check if we have enough
                if holdings[coin_sell] >= amount_sell:
                    # Calculate amount buy based on value
                    val_usd = amount_sell * price_sell
                    amount_buy = (val_usd / price_buy).quantize(Decimal('0.0001'))
                    
                    if amount_buy > 0:
                        # Process Sell side (Taxable)
                        process_sell(coin_sell, amount_sell, price_sell, current_date, fee=Decimal('2.00'))
                        # Process Buy side
                        process_buy(coin_buy, amount_buy, price_buy, current_date)
                        
                        # Record as one row for the CSV (Engine handles sent/recv in one row as swap)
                        tx = {
                            'date': current_date.isoformat(),
                            'type': 'TRADE',
                            'sent_coin': coin_sell,
                            'sent_amount': amount_sell,
                            'received_coin': coin_buy,
                            'received_amount': amount_buy,
                            'fee': Decimal('2.00'), # Swap fee
                            'fee_coin': 'USD',
                            'price_usd': price_sell
                        }
                        add_transaction(tx)

        current_date += timedelta(days=1)

    # Inject Anomalies
    inject_anomalies()

    # Calculate Expected Stats using Tax Logic
    final_stats = calculate_tax_results(transactions)
    expected_stats.update(final_stats)

    # Distribute to files
    file_handles = {f: [] for f in FILES}
    for tx in transactions:
        f = random.choice(FILES)
        file_handles[f].append(tx)
        
    # Write CSVs
    for fname, txs in file_handles.items():
        with open(os.path.join(OUTPUT_DIR, fname), 'w', newline='') as csvfile:
            # Determine headers based on filename to mimic exchanges
            if 'kraken' in fname:
                # Kraken style: time, kind, sent_asset, sent_amount, received_asset, received_amount, fee, fee_asset
                fieldnames = ['time', 'kind', 'sent_asset', 'sent_amount', 'received_asset', 'received_amount', 'fee', 'fee_asset']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for tx in txs:
                    row = {
                        'time': tx.get('date'),
                        'kind': tx.get('type'),
                        'sent_asset': tx.get('sent_coin'),
                        'sent_amount': tx.get('sent_amount'),
                        'received_asset': tx.get('received_coin'),
                        'received_amount': tx.get('received_amount'),
                        'fee': tx.get('fee'),
                        'fee_asset': tx.get('fee_coin')
                    }
                    writer.writerow(row)
            elif 'gemini' in fname:
                # Gemini style: Date, Type, Symbol, Amount, Price
                # Note: This is a simplification as Gemini usually has one amount column.
                # We will use the generic headers but mapped to Gemini-ish names that Ingestor supports
                fieldnames = ['Date', 'Type', 'Symbol', 'Amount', 'Price', 'Received Amount', 'Received Symbol']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for tx in txs:
                    # Map to Gemini-ish
                    symbol = tx.get('sent_coin') if tx.get('sent_coin') else tx.get('received_coin')
                    amount = tx.get('sent_amount') if tx.get('sent_amount') else tx.get('received_amount')
                    row = {
                        'Date': tx.get('date'),
                        'Type': tx.get('type'),
                        'Symbol': symbol,
                        'Amount': amount,
                        'Price': tx.get('price_usd'),
                        'Received Amount': tx.get('received_amount'), # Extra col for Ingestor compatibility
                        'Received Symbol': tx.get('received_coin')    # Extra col for Ingestor compatibility
                    }
                    writer.writerow(row)
            else:
                # Standard Generic
                fieldnames = ['date', 'type', 'sent_coin', 'sent_amount', 'received_coin', 'received_amount', 'fee', 'fee_coin', 'price_usd']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for tx in txs:
                    row = {k: v for k, v in tx.items() if k in fieldnames}
                    writer.writerow(row)

    # Write Expected Output
    with open(os.path.join(OUTPUT_DIR, 'EXPECTED_OUTPUT.txt'), 'w') as f:
        f.write("STRESS TEST EXPECTED RESULTS\n")
        f.write("============================\n")
        f.write(f"Generated Date: {datetime.now().isoformat()}\n")
        f.write(f"Total Transactions: {expected_stats['transaction_count']}\n\n")
        f.write(f"Total Income (Staking/Mining/Airdrop): ${expected_stats['total_income']:,.2f}\n")
        f.write(f"Short Term Capital Gains: ${expected_stats['short_term_gains']:,.2f}\n")
        f.write(f"Long Term Capital Gains: ${expected_stats['long_term_gains']:,.2f}\n")
        f.write(f"Total Fees Paid: ${expected_stats['total_fees']:,.2f}\n")
        f.write("\nEXPECTED WARNINGS / ANOMALIES:\n")
        for w in expected_warnings:
            f.write(f"- {w}\n")
        f.write("\nNote: These values are calculated using strict FIFO method.\n")
        f.write("The engine's output should match these values closely, though small rounding differences may occur.\n")
        
    print("\n=== EXPECTED WARNINGS ===")
    for w in expected_warnings:
        print(f"- {w}")

if __name__ == '__main__':
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    generate_data()
    print(f"Generated stress test data in {OUTPUT_DIR}")
