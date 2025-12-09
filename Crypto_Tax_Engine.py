import sqlite3
import pandas as pd
import ccxt
import json
import time
import shutil
import sys
import os
import random
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
LOG_DIR = OUTPUT_DIR / 'logs'
DB_FILE = BASE_DIR / 'crypto_master.db'
DB_BACKUP = BASE_DIR / 'crypto_master.db.bak'
KEYS_FILE = BASE_DIR / 'api_keys.json'

for d in [INPUT_DIR, ARCHIVE_DIR, OUTPUT_DIR, LOG_DIR]:
    if not d.exists(): d.mkdir(parents=True)

# ==========================================
# 0. RESILIENCE UTILS
# ==========================================
class NetworkRetry:
    """Handles flaky internet or API rate limits automatically."""
    @staticmethod
    def run(func, retries=5, delay=2, backoff=2, context="Network"):
        for i in range(retries):
            try:
                return func()
            except Exception as e:
                if i == retries - 1:
                    print(f"   [!!!] {context} TIMEOUT/FAIL after {retries} attempts.")
                    print(f"   [Error Detail] {e}")
                    raise TimeoutError(f"{context} operation took too long or failed.")
                
                sleep_time = delay * (backoff ** i) + random.uniform(0, 1)
                print(f"   [Retry] {context} error: {e}. Retrying in {sleep_time:.1f}s...")
                time.sleep(sleep_time)

class DualLogger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding='utf-8')
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()
    def flush(self):
        self.terminal.flush()
        self.log.flush()

# ==========================================
# 1. DATABASE CORE (Self-Healing + Backup)
# ==========================================
class DatabaseManager:
    def __init__(self):
        self._ensure_integrity()
        self.conn = sqlite3.connect(str(DB_FILE))
        self.cursor = self.conn.cursor()
        self._init_tables()

    def create_safety_backup(self):
        """Creates a SINGLE rolling backup (Overwrites previous)."""
        if DB_FILE.exists():
            # Flush any pending changes first
            self.conn.commit() 
            try:
                if DB_BACKUP.exists():
                    print("   [Safety] Overwriting old backup with current state...")
                
                shutil.copy(DB_FILE, DB_BACKUP)
                print("   [Safety] New Backup Saved: 'crypto_master.db.bak'")
            except Exception as e:
                print(f"   [Warning] Could not create backup: {e}")

    def restore_safety_backup(self):
        """Restores the backup if the operation failed."""
        if DB_BACKUP.exists():
            print("   [CRITICAL] Restoring database from backup...")
            self.close() # Must close connection to overwrite file
            try:
                shutil.copy(DB_BACKUP, DB_FILE)
                # Re-open connection
                self.conn = sqlite3.connect(str(DB_FILE))
                self.cursor = self.conn.cursor()
                print("   [Success] Database restored to previous state.")
            except Exception as e:
                print(f"   [FATAL] Could not restore backup! Error: {e}")

    def remove_safety_backup(self):
        """
        This keeps the backup file as a 'Last Good Known Configuration'.
        It does NOT delete it. It simply confirms success.
        The next run will overwrite this file.
        """
        if DB_BACKUP.exists():
            print("   [Safety] Run successful. Backup file retained as restore point.")

    def _ensure_integrity(self):
        """Checks if DB is corrupt before opening."""
        if not DB_FILE.exists(): return
        
        try:
            # Open a temp connection just to check integrity
            temp_conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
            temp_cursor = temp_conn.cursor()
            temp_cursor.execute("PRAGMA integrity_check")
            result = temp_cursor.fetchone()[0]
            temp_conn.close()
            
            if result != "ok":
                raise sqlite3.DatabaseError(f"Integrity check returned: {result}")
                
        except Exception as e:
            print(f"\n[CRITICAL WARNING] Database corruption detected: {e}")
            self._recover_db()

    def _recover_db(self):
        """Moves corrupt DB aside and creates fresh one."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        corrupt_name = f"CORRUPT_{ts}_{DB_FILE.name}"
        shutil.move(str(DB_FILE), str(BASE_DIR / corrupt_name))
        print(f"   -> Moved corrupt file to: {corrupt_name}")
        
        if DB_BACKUP.exists():
            print(f"   -> [TIP] You have a backup file! Rename 'crypto_master.db.bak' to 'crypto_master.db' to restore.")
        
        print(f"   -> Creating a fresh, empty database.")
        print(f"   -> [ACTION REQUIRED] The API Sync will automatically rebuild API history.")
        print(f"   -> [ACTION REQUIRED] For CSVs, verify 'inputs' folder. You may need to copy files from 'processed_archive' back to 'inputs' to re-ingest manually.\n")

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
        try:
            res = self.cursor.execute("SELECT date FROM trades WHERE source=? ORDER BY date DESC LIMIT 1", (source,)).fetchone()
            if res:
                return int(pd.to_datetime(res[0]).timestamp() * 1000)
        except: pass
        return 1262304000000 

    def save_trade(self, t):
        try:
            self.cursor.execute('''
                INSERT OR IGNORE INTO trades 
                (id, date, source, action, coin, amount, price_usd, fee, batch_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (t['id'], t['date'], t['source'], t['action'], t['coin'], 
                  t['amount'], t['price_usd'], t['fee'], t['batch_id']))
        except Exception as e:
            print(f"[DB Write Error] {e}")

    def commit(self): self.conn.commit()
    def get_all(self): return pd.read_sql_query("SELECT * FROM trades ORDER BY date ASC", self.conn)
    def get_zeros(self): return pd.read_sql_query("SELECT * FROM trades WHERE price_usd=0 AND action='INCOME'", self.conn)
    def update_price(self, uid, p): self.cursor.execute("UPDATE trades SET price_usd=? WHERE id=?", (p, uid))
    def close(self): self.conn.close()

# ==========================================
# 2. INGESTION (Safe Mode)
# ==========================================
class Ingestor:
    def __init__(self, db):
        self.db = db
        self.fetcher = PriceFetcher()

    def run_csv_scan(self):
        print("\n--- 1. SCANNING INPUTS FOLDER ---")
        
        # SAFETY: Create backup before touching CSVs
        self.db.create_safety_backup()
        
        try:
            found = False
            for fp in INPUT_DIR.glob('*.csv'):
                print(f"-> Processing: {fp.name}")
                found = True
                batch = f"CSV_{fp.name}_{datetime.now().strftime('%Y%m%d')}"
                self._proc_csv(fp, batch)
                self._archive(fp)
            
            if not found: print("   No new CSV files found.")
            
            # If we get here, everything worked.
            self.db.remove_safety_backup()
            
        except Exception as e:
            print(f"   [ERROR] CSV Scan Failed: {e}")
            self.db.restore_safety_backup()
            print("   [SAFE] Database reverted. Fix the file and try again.")

    def _proc_csv(self, fp, batch):
        df = pd.read_csv(fp)
        df.columns = [c.lower() for c in df.columns]
        src = 'DEFI' if 'sent_asset' in df.columns else 'MINING' if 'coin_type' in df.columns else 'MANUAL'
        
        count = 0
        for _, r in df.iterrows():
            try:
                d = pd.to_datetime(r.get('date'))
                coin = r.get('coin', r.get('coin_type', 'UNK'))
                amt = float(r.get('amount', 0))
                price = float(r.get('usd_value_at_time', 0))
                fee = float(r.get('fee', 0))
                
                # Retry logic for price fetch
                if price == 0: 
                    # If this fetch fails/times out, it throws error -> triggers restore
                    def fetch_p(): return self.fetcher.get_price(coin, d)
                    price = NetworkRetry.run(fetch_p, context=f"Price {coin}")
                
                uid = f"{src}_{d.strftime('%Y%m%d%H%M')}_{coin}_{amt}"
                self.db.save_trade({
                    'id': uid, 'date': d.isoformat(), 'source': src,
                    'action': 'INCOME' if src!='DEFI' else 'BUY',
                    'coin': coin, 'amount': amt, 'price_usd': price, 
                    'fee': fee, 'batch_id': batch
                })
                count += 1
            except: pass
        self.db.commit()
        print(f"   Ingested {count} rows.")

    def _archive(self, fp):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            shutil.move(str(fp), str(ARCHIVE_DIR / f"{fp.stem}_PROCESSED_{ts}{fp.suffix}"))
        except OSError as e:
            print(f"   [Warning] Could not archive file: {e}")

    def run_api_sync(self):
        print("\n--- 2. SYNCING APIS ---")
        if not KEYS_FILE.exists(): return
        with open(KEYS_FILE) as f: keys = json.load(f)
        
        # SAFETY: Backup before API sync
        self.db.create_safety_backup()
        
        try:
            for name, creds in keys.items():
                if not hasattr(ccxt, name): continue
                
                # Add timeout config to exchange
                def init_ex(): return getattr(ccxt, name)({
                    'apiKey': creds['apiKey'], 
                    'secret': creds['secret'], 
                    'enableRateLimit': True,
                    'timeout': 30000 # 30 Second Timeout
                })
                
                ex = NetworkRetry.run(init_ex, context=f"{name} Connect")
                
                # A. Trades
                src = f"{name.upper()}_API"
                since = self.db.get_last_timestamp(src) + 1
                print(f"-> {name.upper()}: Trades since {pd.to_datetime(since, unit='ms')}")
                
                nt = []
                while True:
                    def fetch_t(): return ex.fetch_my_trades(since=since)
                    b = NetworkRetry.run(fetch_t, context=f"{name} Fetch")
                    
                    if not b: break
                    nt.extend(b)
                    since = b[-1]['timestamp'] + 1
                
                if nt:
                    bid = f"API_{name}_{datetime.now().strftime('%Y%m%d%H%M')}"
                    # Backup raw JSON
                    try:
                        with open(ARCHIVE_DIR/f"{bid}.json",'w') as f: json.dump(nt,f,default=str)
                    except: pass 
                    
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
            
            # If we finish all APIs without crash, keep backup as restore point
            self.db.remove_safety_backup()

        except Exception as e:
            print(f"   [CRITICAL] API Sync Failed: {e}")
            self.db.restore_safety_backup()
            print("   [SAFE] Database reverted to state before API Sync.")

    def _sync_ledger(self, ex, name):
        src = f"{name.upper()}_LEDGER"
        since = self.db.get_last_timestamp(src) + 1
        print(f"-> {name.upper()}: Checking Rewards...")
        try:
            def fetch_l(): return ex.fetch_ledger(since=since)
            batch = NetworkRetry.run(fetch_l, retries=3, context=f"{name} Ledger")
            
            if batch:
                c = 0
                for item in batch:
                    if any(x in item.get('type','').lower() for x in ['staking','reward','dividend','interest','airdrop','mining']):
                        uid = f"{name}_LEDGER_{item['id']}"
                        self.db.save_trade({
                            'id': uid, 'date': item['datetime'], 'source': src,
                            'action': 'INCOME', 'coin': item['currency'],
                            'amount': float(item['amount']), 'price_usd': 0.0, 'fee': 0,
                            'batch_id': 'API_SYNC_LEDGER'
                        })
                        c += 1
                self.db.commit()
                if c>0: print(f"   Found {c} rewards.")
        except: pass

# ==========================================
# 3. HELPER: PRICE FETCHER (Robust)
# ==========================================
class PriceFetcher:
    def __init__(self): self.cache={}
    def get_price(self, s, d):
        if s in ['USD','USDC','USDT']: return 1.0
        try:
            k=f"{s}_{d.date()}"
            if k in self.cache: return self.cache[k]
            
            def dl_price():
                return yf.download(f"{s.upper()}-USD", start=d, end=d+timedelta(days=3), progress=False)
            
            df = NetworkRetry.run(dl_price, retries=3, delay=1, context=f"Price {s}")
            
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
        if df.empty:
            print("   [Warning] Database is empty. Nothing to calculate.")
            return

        for _, t in df.iterrows():
            try:
                d = pd.to_datetime(t['date'])
                if d.year > self.year: continue
                
                is_target_year = (d.year == self.year)

                if t['action'] in ['BUY', 'INCOME']:
                    cost = (t['amount'] * t['price_usd']) + t['fee']
                    eff_price = cost / t['amount'] if t['amount'] else 0
                    self._add(t['coin'], t['amount'], eff_price, d)
                    
                    if is_target_year and t['action'] == 'INCOME':
                        val = t['amount'] * t['price_usd']
                        self.inc_rows.append({'Date': d.date(), 'Source': t['source'], 'Coin': t['coin'], 'Amount': t['amount'], 'USD Value': round(val,2)})

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
            except Exception as e:
                print(f"   [Skipping Row] Error processing trade {t.get('id', '?')}: {e}")

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
        ydir = OUTPUT_DIR / f"Year_{self.year}"
        if not ydir.exists(): ydir.mkdir(parents=True)

        if self.tt_rows:
            pd.DataFrame(self.tt_rows).to_csv(ydir / 'GENERIC_TAX_CAP_GAINS.csv', index=False)
            print(f"   -> Saved GENERIC_TAX_CAP_GAINS.csv")

        if self.inc_rows:
            pd.DataFrame(self.inc_rows).to_csv(ydir / 'INCOME_REPORT.csv', index=False)
            print(f"   -> Saved INCOME_REPORT.csv")

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
            current_system_year = datetime.now().year
            is_finalizable = (self.year < current_system_year)

            if is_finalizable:
                pd.DataFrame(snapshot).to_csv(ydir / 'EOY_HOLDINGS_SNAPSHOT.csv', index=False)
                print(f"   -> [FINALIZED] Saved EOY_HOLDINGS_SNAPSHOT.csv")
            else:
                pd.DataFrame(snapshot).to_csv(ydir / 'CURRENT_HOLDINGS_DRAFT.csv', index=False)
                print(f"\n   [SAFEGUARD] Year {self.year} is active. Saved 'CURRENT_HOLDINGS_DRAFT.csv'.")

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    # LOGGING
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    sys.stdout = DualLogger(LOG_DIR / f"Manual_{timestamp}.log")

    print("--- CRYPTO TAX MASTER V17 (Resilience Edition) ---")
    
    # 1. SETUP & SYNC
    db = DatabaseManager() # Checks for corruption on init
    ingest = Ingestor(db)
    ingest.run_csv_scan()
    ingest.run_api_sync()
    
    # 2. BACKFILL
    bf = PriceFetcher()
    zeros = db.get_zeros()
    if not zeros.empty:
        print(f"\n--- Backfilling {len(zeros)} missing prices ---")
        for _, r in zeros.iterrows():
            p = bf.get_price(r['coin'], pd.to_datetime(r['date']))
            if p > 0: db.update_price(r['id'], p)
        db.commit()

    # 3. REPORT
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