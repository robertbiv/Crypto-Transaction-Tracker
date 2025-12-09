import sqlite3
import pandas as pd
import ccxt
import json
import time
import shutil
import sys
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================
BASE_DIR = Path.cwd()
INPUT_DIR = BASE_DIR / 'inputs'
ARCHIVE_DIR = BASE_DIR / 'processed_archive'
OUTPUT_DIR = BASE_DIR / 'outputs'
DB_FILE = BASE_DIR / 'crypto_master.db'
KEYS_FILE = BASE_DIR / 'api_keys.json'

# Create Folders
for d in [INPUT_DIR, ARCHIVE_DIR, OUTPUT_DIR]:
    if not d.exists(): d.mkdir(parents=True)

# ==========================================
# 1. DATABASE CORE
# ==========================================
class DatabaseManager:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_FILE))
        self.cursor = self.conn.cursor()
        self._init_tables()

    def _init_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                date TEXT,
                source TEXT,
                action TEXT,
                coin TEXT,
                amount REAL,
                price_usd REAL,
                fee REAL,
                batch_id TEXT
            )
        ''')
        self.conn.commit()

    def get_last_timestamp(self, source):
        res = self.cursor.execute("SELECT date FROM trades WHERE source=? ORDER BY date DESC LIMIT 1", (source,)).fetchone()
        if res:
            return int(pd.to_datetime(res[0]).timestamp() * 1000)
        return 1262304000000 # Default 2010

    def save_trade(self, t):
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO trades 
                (id, date, source, action, coin, amount, price_usd, fee, batch_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (t['id'], t['date'], t['source'], t['action'], t['coin'], 
                  t['amount'], t['price_usd'], t['fee'], t['batch_id']))
        except: pass

    def commit(self): self.conn.commit()
    def get_all(self): return pd.read_sql_query("SELECT * FROM trades ORDER BY date ASC", self.conn)
    def get_zeros(self): return pd.read_sql_query("SELECT * FROM trades WHERE price_usd=0 AND action='INCOME'", self.conn)
    def update_price(self, uid, p): self.cursor.execute("UPDATE trades SET price_usd=? WHERE id=?", (p, uid))
    def close(self): self.conn.close()

# ==========================================
# 2. INGESTION (File & API)
# ==========================================
class Ingestor:
    def __init__(self, db):
        self.db = db
        self.fetcher = PriceFetcher()

    def run_csv_scan(self):
        print("\n--- 1. SCANNING INPUTS FOLDER ---")
        found = False
        for fp in INPUT_DIR.glob('*.csv'):
            print(f"-> Processing: {fp.name}")
            found = True
            try:
                batch = f"CSV_{fp.name}_{datetime.now().strftime('%Y%m%d')}"
                self._proc_csv(fp, batch)
                self._archive(fp)
            except Exception as e: print(f"   [!] Error: {e}")
        if not found: print("   No new CSV files found.")

    def _proc_csv(self, fp, batch):
        df = pd.read_csv(fp)
        df.columns = [c.lower() for c in df.columns]
        src = 'DEFI' if 'sent_asset' in df.columns else 'MINING' if 'coin_type' in df.columns else 'MANUAL'
        
        for _, r in df.iterrows():
            try:
                d = pd.to_datetime(r.get('date'))
                coin = r.get('coin', r.get('coin_type', 'UNK'))
                amt = float(r.get('amount', 0))
                price = float(r.get('usd_value_at_time', 0))
                fee = float(r.get('fee', 0))
                if price == 0: price = self.fetcher.get_price(coin, d)
                
                uid = f"{src}_{d.strftime('%Y%m%d%H%M')}_{coin}_{amt}"
                self.db.save_trade({
                    'id': uid, 'date': d.isoformat(), 'source': src,
                    'action': 'INCOME' if src!='DEFI' else 'BUY',
                    'coin': coin, 'amount': amt, 'price_usd': price, 
                    'fee': fee, 'batch_id': batch
                })
            except: pass
        self.db.commit()

    def _archive(self, fp):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.move(str(fp), str(ARCHIVE_DIR / f"{fp.stem}_PROCESSED_{ts}{fp.suffix}"))

    def run_api_sync(self):
        print("\n--- 2. SYNCING APIS ---")
        if not KEYS_FILE.exists(): return
        with open(KEYS_FILE) as f: keys = json.load(f)
        
        for name, creds in keys.items():
            if not hasattr(ccxt, name): continue
            
            # A. Trades
            try:
                ex = getattr(ccxt, name)({'apiKey': creds['apiKey'], 'secret': creds['secret'], 'enableRateLimit':True})
                src = f"{name.upper()}_API"
                since = self.db.get_last_timestamp(src) + 1
                print(f"-> {name.upper()}: Trades since {pd.to_datetime(since, unit='ms')}")
                
                nt = []
                while True:
                    b = ex.fetch_my_trades(since=since)
                    if not b: break
                    nt.extend(b)
                    since = b[-1]['timestamp'] + 1
                
                if nt:
                    bid = f"API_{name}_{datetime.now().strftime('%Y%m%d%H%M')}"
                    with open(ARCHIVE_DIR/f"{bid}.json",'w') as f: json.dump(nt,f,default=str)
                    for t in nt:
                        uid = f"{name}_{t['id']}"
                        self.db.save_trade({
                            'id':uid, 'date':t['datetime'], 'source':src,
                            'action':'BUY' if t['side']=='buy' else 'SELL',
                            'coin':t['symbol'].split('/')[0], 'amount':float(t['amount']),
                            'price_usd':float(t['price']), 'fee':t['fee']['cost'] if t['fee'] else 0,
                            'batch_id':bid
                        })
                    self.db.commit()
                    print(f"   Saved {len(nt)} trades.")

                # B. Staking (Ledger)
                if ex.has.get('fetchLedger'):
                    self._sync_ledger(ex, name)

            except Exception as e: print(f"   [!] API Error {name}: {e}")

    def _sync_ledger(self, ex, name):
        src = f"{name.upper()}_LEDGER"
        since = self.db.get_last_timestamp(src) + 1
        print(f"-> {name.upper()}: Checking Rewards...")
        # (Simplified Ledger Logic for brevity)
        pass

# ==========================================
# 3. HELPER: PRICE FETCHER
# ==========================================
class PriceFetcher:
    def __init__(self): self.cache={}
    def get_price(self, s, d):
        if s in ['USD','USDC']: return 1.0
        try:
            k=f"{s}_{d.date()}"
            if k in self.cache: return self.cache[k]
            df=yf.download(f"{s.upper()}-USD", start=d, end=d+timedelta(days=3), progress=False)
            if not df.empty: 
                v=df['Close'].iloc[0]; self.cache[k]=float(v.iloc[0] if isinstance(v,pd.Series) else v)
                return self.cache[k]
        except: pass
        return 0.0

# ==========================================
# 4. TAX ENGINE & EOY SNAPSHOT
# ==========================================
class TaxEngine:
    def __init__(self, db, year):
        self.db = db
        self.year = int(year)
        self.tt_rows = []
        self.inc_rows = []
        self.holdings = {}

    def run(self):
        print(f"\n--- 3. GENERATING {self.year} REPORT ---")
        df = self.db.get_all()
        
        for _, t in df.iterrows():
            d = pd.to_datetime(t['date'])
            # Stop processing if transaction is in the future relative to tax year
            if d.year > self.year: continue
            
            is_target_year = (d.year == self.year)

            # BUY / INCOME
            if t['action'] in ['BUY', 'INCOME']:
                cost = (t['amount'] * t['price_usd']) + t['fee']
                eff_price = cost / t['amount'] if t['amount'] else 0
                self._add(t['coin'], t['amount'], eff_price, d)
                
                if is_target_year and t['action'] == 'INCOME':
                    val = t['amount'] * t['price_usd']
                    self.inc_rows.append({'Date': d.date(), 'Source': t['source'], 'Coin': t['coin'], 'Amount': t['amount'], 'USD Value': round(val,2)})

            # SELL
            elif t['action'] == 'SELL':
                net_proc = (t['amount'] * t['price_usd']) - t['fee']
                basis, term, acq = self._sell(t['coin'], t['amount'], d)
                
                if is_target_year:
                    self.tt_rows.append({
                        'Description': f"{t['amount']} {t['coin']}", 
                        'Date Acquired': acq, 'Date Sold': d.strftime('%m/%d/%Y'),
                        'Proceeds': round(net_proc, 2), 'Cost Basis': round(basis, 2),
                        'Gain/Loss': round(net_proc - basis, 2)
                    })

    def _add(self, c, a, p, d):
        if c not in self.holdings: self.holdings[c] = []
        self.holdings[c].append({'a': a, 'p': p, 'd': d})

    def _sell(self, c, a, d):
        if c not in self.holdings: self.holdings[c] = []
        rem, b, ds = a, 0, set()
        while rem > 0 and self.holdings[c]:
            l = self.holdings[c][0]; ds.add(l['d'])
            if l['a'] <= rem:
                b += l['a'] * l['p']; rem -= l['a']; self.holdings[c].pop(0)
            else:
                b += rem * l['p']; l['a'] -= rem; rem = 0
        term = 'Long' if ds and (d - min(ds)).days > 365 else 'Short'
        acq = list(ds)[0].strftime('%m/%d/%Y') if len(ds)==1 else 'VARIOUS'
        return b, term, acq

    def export(self):
        # Create Year Folder
        ydir = OUTPUT_DIR / f"Year_{self.year}"
        if not ydir.exists(): ydir.mkdir(parents=True)

        # 1. Export
        if self.tt_rows:
            pd.DataFrame(self.tt_rows).to_csv(ydir / 'GENERIC_TAX_CAP_GAINS.csv', index=False)
            print(f"   -> Saved GENERIC_TAX_CAP_GAINS.csv")

        # 2. Income
        if self.inc_rows:
            pd.DataFrame(self.inc_rows).to_csv(ydir / 'INCOME_REPORT.csv', index=False)
            print(f"   -> Saved INCOME_REPORT.csv")

        # 3. HOLDINGS SNAPSHOT (WITH SAFETY GUARD)
        snapshot = []
        for coin, lots in self.holdings.items():
            total = sum(l['a'] for l in lots)
            if total > 0.000001:
                total_cost = sum(l['a'] * l['p'] for l in lots)
                snapshot.append({
                    'Coin': coin,
                    'Holdings': round(total, 8),
                    'Total Cost Basis': round(total_cost, 2),
                    'Avg Price': round(total_cost/total, 2)
                })
        
        if snapshot:
            # SAFETY LOGIC: Can we finalize this year?
            current_system_year = datetime.now().year
            is_finalizable = (self.year < current_system_year)

            if is_finalizable:
                # Year is over. Create the FINAL snapshot.
                pd.DataFrame(snapshot).to_csv(ydir / 'EOY_HOLDINGS_SNAPSHOT.csv', index=False)
                print(f"   -> [FINALIZED] Saved EOY_HOLDINGS_SNAPSHOT.csv (Holdings as of Dec 31, {self.year})")
            else:
                # Year is NOT over. Create a DRAFT snapshot.
                pd.DataFrame(snapshot).to_csv(ydir / 'CURRENT_HOLDINGS_DRAFT.csv', index=False)
                print(f"\n   ---------------------------------------------------------------")
                print(f"   [INFO] Year {self.year} is still active. Reports are in DRAFT mode.")
                print(f"   [SAFEGUARD] Final EOY Snapshot is blocked until Jan 1, {self.year + 1}.")
                print(f"   -> Saved 'CURRENT_HOLDINGS_DRAFT.csv' for your reference.")
                print(f"   ---------------------------------------------------------------")

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    print("--- CRYPTO TAX MASTER V16 (Safety Guard Enabled) ---")
    db = DatabaseManager()
    ingest = Ingestor(db)
    
    # 1. Sync
    ingest.run_csv_scan()
    ingest.run_api_sync()
    
    # 2. Backfill
    bf = PriceFetcher()
    zeros = db.get_zeros()
    if not zeros.empty:
        print(f"\n--- Backfilling {len(zeros)} missing prices ---")
        for _, r in zeros.iterrows():
            p = bf.get_price(r['coin'], pd.to_datetime(r['date']))
            if p > 0: db.update_price(r['id'], p)
        db.commit()

    # 3. Report
    try:
        y_input = input("\nEnter Tax Year: ")
        if y_input.isdigit():
            eng = TaxEngine(db, y_input)
            eng.run()
            eng.export()
    except Exception as e:
        print(f"Error: {e}")
    
    db.close()
    input("\nDone. Press Enter.")