import sqlite3
import pandas as pd
import ccxt
import json
import time
import shutil
import sys
import os
import random
import requests
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
WALLETS_FILE = BASE_DIR / 'wallets.json'

# Fallback: Ensure folders exist even if setup wasn't run
for d in [INPUT_DIR, ARCHIVE_DIR, OUTPUT_DIR, LOG_DIR]:
    if not d.exists(): d.mkdir(parents=True)

# ==========================================
# 0. SETUP VERIFICATION
# ==========================================
def verify_setup():
    """Checks if configuration files exist and are valid JSON."""
    issues = []

    # Check API Keys
    if not KEYS_FILE.exists():
        issues.append("[MISSING] 'api_keys.json' not found.")
    else:
        try:
            with open(KEYS_FILE, 'r') as f: json.load(f)
        except json.JSONDecodeError:
            issues.append("[CORRUPT] 'api_keys.json' contains invalid JSON.")

    # Check Wallets
    if not WALLETS_FILE.exists():
        issues.append("[MISSING] 'wallets.json' not found.")
    else:
        try:
            with open(WALLETS_FILE, 'r') as f: json.load(f)
        except json.JSONDecodeError:
            issues.append("[CORRUPT] 'wallets.json' contains invalid JSON.")
    
    if issues:
        print("\n" + "!"*60)
        print("   CRITICAL ERROR: CONFIGURATION ISSUES DETECTED")
        print("!"*60)
        for issue in issues:
            print(f"   {issue}")
        print("\n   >>> ACTION REQUIRED: Please re-run 'setup_env.py' to fix these files.")
        print("!"*60 + "\n")
        input("Press Enter to exit...")
        sys.exit(1)

# ==========================================
# 0.5 RESILIENCE UTILS
# ==========================================
class NetworkRetry:
    @staticmethod
    def run(func, retries=5, delay=2, backoff=2, context="Network"):
        for i in range(retries):
            try:
                return func()
            except Exception as e:
                if i == retries - 1:
                    print(f"   [!!!] {context} TIMEOUT/FAIL: {e}")
                    raise TimeoutError(f"{context} failed.")
                time.sleep(delay * (backoff ** i) + random.uniform(0, 1))

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
# 1. DATABASE CORE
# ==========================================
class DatabaseManager:
    def __init__(self):
        self._ensure_integrity()
        self.conn = sqlite3.connect(str(DB_FILE))
        self.cursor = self.conn.cursor()
        self._init_tables()

    def create_safety_backup(self):
        if DB_FILE.exists():
            self.conn.commit() 
            try:
                shutil.copy(DB_FILE, DB_BACKUP)
                print("   [Safety] Overwriting backup ('crypto_master.db.bak')")
            except: pass

    def restore_safety_backup(self):
        if DB_BACKUP.exists():
            print("   [CRITICAL] Restoring database from backup...")
            self.close()
            try:
                shutil.copy(DB_BACKUP, DB_FILE)
                self.conn = sqlite3.connect(str(DB_FILE))
                self.cursor = self.conn.cursor()
                print("   [Success] Database restored.")
            except: print("   [FATAL] Restore failed.")

    def remove_safety_backup(self):
        if DB_BACKUP.exists():
            print("   [Safety] Run successful. Backup retained.")

    def _ensure_integrity(self):
        if not DB_FILE.exists(): return
        try:
            temp_conn = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
            temp_conn.execute("PRAGMA integrity_check")
            temp_conn.close()
        except:
            self._recover_db()

    def _recover_db(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.move(str(DB_FILE), str(BASE_DIR / f"CORRUPT_{ts}_{DB_FILE.name}"))
        print(f"   -> [ALERT] Corrupt DB moved. Created fresh database.")

    def _init_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS trades (id TEXT PRIMARY KEY, date TEXT, source TEXT, action TEXT, coin TEXT, amount REAL, price_usd REAL, fee REAL, batch_id TEXT)''')
        self.conn.commit()

    def get_last_timestamp(self, source):
        try:
            res = self.cursor.execute("SELECT date FROM trades WHERE source=? ORDER BY date DESC LIMIT 1", (source,)).fetchone()
            if res: return int(pd.to_datetime(res[0]).timestamp() * 1000)
        except: pass
        return 1262304000000 

    def save_trade(self, t):
        try: self.cursor.execute("INSERT OR IGNORE INTO trades VALUES (?,?,?,?,?,?,?,?,?)", list(t.values()))
        except: pass

    def commit(self): self.conn.commit()
    def get_all(self): return pd.read_sql_query("SELECT * FROM trades ORDER BY date ASC", self.conn)
    def get_zeros(self): return pd.read_sql_query("SELECT * FROM trades WHERE price_usd=0 AND action='INCOME'", self.conn)
    def update_price(self, uid, p): self.cursor.execute("UPDATE trades SET price_usd=? WHERE id=?", (p, uid))
    def close(self): self.conn.close()

# ==========================================
# 2. INGESTION
# ==========================================
class Ingestor:
    def __init__(self, db):
        self.db = db
        self.fetcher = PriceFetcher()

    def run_csv_scan(self):
        print("\n--- 1. SCANNING INPUTS FOLDER ---")
        self.db.create_safety_backup()
        try:
            found = False
            for fp in INPUT_DIR.glob('*.csv'):
                print(f"-> Processing: {fp.name}")
                found = True
                self._proc_csv(fp, f"CSV_{fp.name}_{datetime.now().strftime('%Y%m%d')}")
                self._archive(fp)
            if not found: print("   No new CSV files found.")
            self.db.remove_safety_backup()
        except: self.db.restore_safety_backup()

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
                if price == 0: 
                    def fetch_p(): return self.fetcher.get_price(coin, d)
                    price = NetworkRetry.run(fetch_p, context=f"Price {coin}")
                self.db.save_trade({'id': f"{src}_{d.strftime('%Y%m%d%H%M')}_{coin}_{amt}", 'date': d.isoformat(), 'source': src, 'action': 'INCOME' if src!='DEFI' else 'BUY', 'coin': coin, 'amount': amt, 'price_usd': price, 'fee': fee, 'batch_id': batch})
            except: pass
        self.db.commit()

    def _archive(self, fp):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try: shutil.move(str(fp), str(ARCHIVE_DIR / f"{fp.stem}_PROCESSED_{ts}{fp.suffix}"))
        except: pass

    def run_api_sync(self):
        print("\n--- 2. SYNCING APIS ---")
        if not KEYS_FILE.exists(): return
        with open(KEYS_FILE) as f: keys = json.load(f)
        self.db.create_safety_backup()
        
        try:
            for name, creds in keys.items():
                if name.startswith("_") or "PASTE_" in creds.get('apiKey', ''): continue
                if not hasattr(ccxt, name): continue
                
                def init_ex(): return getattr(ccxt, name)({'apiKey': creds['apiKey'], 'secret': creds['secret'], 'enableRateLimit': True, 'timeout': 30000})
                ex = NetworkRetry.run(init_ex, context=f"{name} Connect")
                
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
                    try: pd.DataFrame(nt).to_csv(ARCHIVE_DIR / f"{bid}.csv", index=False)
                    except: pass
                    for t in nt:
                        self.db.save_trade({'id':f"{name}_{t['id']}", 'date':t['datetime'], 'source':src, 'action':'BUY' if t['side']=='buy' else 'SELL', 'coin':t['symbol'].split('/')[0], 'amount':float(t['amount']), 'price_usd':float(t['price']), 'fee':t['fee']['cost'] if t['fee'] else 0, 'batch_id':bid})
                    self.db.commit()
                    print(f"   Saved {len(nt)} trades.")

                if ex.has.get('fetchLedger'):
                    self._sync_ledger(ex, name)
            self.db.remove_safety_backup()
        except: self.db.restore_safety_backup()

    def _sync_ledger(self, ex, name):
        src = f"{name.upper()}_LEDGER"
        since = self.db.get_last_timestamp(src) + 1
        print(f"   {name.upper()}: Checking Rewards/Staking...")
        try:
            def fetch_l(): return ex.fetch_ledger(since=since)
            batch = NetworkRetry.run(fetch_l, retries=3, context=f"{name} Ledger")
            if batch:
                c = 0
                for item in batch:
                    if any(x in item.get('type','').lower() for x in ['staking','reward','dividend','interest','airdrop','mining']):
                        self.db.save_trade({'id': f"{name}_LEDGER_{item['id']}", 'date': item['datetime'], 'source': src, 'action': 'INCOME', 'coin': item['currency'], 'amount': float(item['amount']), 'price_usd': 0.0, 'fee': 0, 'batch_id': 'API_SYNC_LEDGER'})
                        c += 1
                self.db.commit()
                if c>0: print(f"   Found {c} rewards.")
        except: pass

# ==========================================
# 3. HELPER: PRICE FETCHER
# ==========================================
class PriceFetcher:
    def __init__(self): 
        self.cache = {}
        self.stablecoins = {'USD', 'USDC', 'USDT', 'DAI', 'BUSD', 'GUSD', 'USDP', 'PYUSD', 'TUSD', 'FRAX'}
        self.cache_file = BASE_DIR / 'stablecoins_cache.json'
        self.cache_is_stale = True
        self.dynamic_list_updated = False
        self._load_local_cache()

    def _load_local_cache(self):
        if self.cache_file.exists():
            try:
                if (datetime.now() - datetime.fromtimestamp(self.cache_file.stat().st_mtime)) < timedelta(days=7):
                    self.cache_is_stale = False
                with open(self.cache_file, 'r') as f: self.stablecoins.update(json.load(f))
            except: pass

    def _fetch_dynamic_stablecoins(self):
        print("   [Net] Updating stablecoin list...")
        try:
            url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&category=stablecoins&per_page=30"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                for coin in resp.json(): self.stablecoins.add(coin['symbol'].upper())
                with open(self.cache_file, 'w') as f: json.dump(list(self.stablecoins), f)
                self.dynamic_list_updated = True
                self.cache_is_stale = False
        except: pass

    def get_price(self, s, d):
        if s.upper() in self.stablecoins: return 1.0
        if self.cache_is_stale and not self.dynamic_list_updated:
            self._fetch_dynamic_stablecoins()
            if s.upper() in self.stablecoins: return 1.0

        try:
            k = f"{s}_{d.date()}"
            if k in self.cache: return self.cache[k]
            def dl_price(): return yf.download(f"{s.upper()}-USD", start=d, end=d+timedelta(days=3), progress=False)
            df = NetworkRetry.run(dl_price, retries=3, delay=1, context=f"Price {s}")
            if not df.empty: 
                v = df['Close'].iloc[0]; self.cache[k] = float(v.iloc[0] if isinstance(v,pd.Series) else v)
                return self.cache[k]
        except: pass
        return 0.0

# ==========================================
# 4. AUDITOR (Wallet Check)
# ==========================================
class WalletAuditor:
    def __init__(self, db):
        self.db = db
        self.calculated_balances = {}
        self.real_balances = {}

    def run_audit(self):
        print("\n--- 4. RUNNING LEDGER AUDIT ---")
        if not WALLETS_FILE.exists(): return

        # 1. Calc DB
        df = pd.read_sql_query("SELECT coin, amount, action FROM trades", self.db.conn)
        for _, row in df.iterrows():
            c = row['coin']
            if c not in self.calculated_balances: self.calculated_balances[c] = 0.0
            if row['action'] in ['BUY', 'INCOME']: self.calculated_balances[c] += row['amount']
            elif row['action'] == 'SELL': self.calculated_balances[c] -= row['amount']

        # 2. Check Chain
        with open(WALLETS_FILE) as f: wallets = json.load(f)
        
        for coin, addresses in wallets.items():
            if coin.startswith("_"): continue 
            valid_addresses = [a for a in addresses if "PASTE_" not in a]
            if not valid_addresses: continue

            print(f"   Checking {coin} blockchain ({len(valid_addresses)} wallets)...")
            total_coin = 0.0
            for addr in valid_addresses:
                print(f"      -> Scanning {addr[:6]}...")
                try:
                    if coin == 'BTC':
                        r = requests.get(f"https://blockchain.info/q/addressbalance/{addr}")
                        if r.status_code == 200: total_coin += int(r.text) / 100000000
                except: pass
                time.sleep(0.5)
            self.real_balances[coin] = total_coin
            
        # 3. Compare
        print("\n   --- RECONCILIATION REPORT ---")
        print(f"   {'COIN':<5} | {'DB SAYS':<12} | {'CHAIN SAYS':<12} | {'VARIANCE':<12}")
        print("   " + "-"*50)
        
        all_coins = set(list(self.calculated_balances.keys()) + list(self.real_balances.keys()))
        for coin in sorted(all_coins):
            db_bal = self.calculated_balances.get(coin, 0.0)
            real_bal = self.real_balances.get(coin, 0.0)
            if coin in self.real_balances:
                diff = db_bal - real_bal
                status = "OK"
                if abs(diff) > 0.0001: status = f"MISMATCH ({diff:+.5f})"
                print(f"   {coin:<5} | {db_bal:<12.5f} | {real_bal:<12.5f} | {status}")

# ==========================================
# 5. TAX ENGINE
# ==========================================
class TaxEngine:
    def __init__(self, db, year):
        self.db, self.year, self.tt_rows, self.inc_rows, self.holdings = db, int(year), [], [], {}

    def run(self):
        print(f"\n--- 5. GENERATING {self.year} REPORT ---")
        df = self.db.get_all()
        for _, t in df.iterrows():
            try:
                d = pd.to_datetime(t['date'])
                if d.year > self.year: continue
                is_target = (d.year == self.year)

                if t['action'] in ['BUY', 'INCOME']:
                    cost = (t['amount'] * t['price_usd']) + t['fee']
                    eff = cost / t['amount'] if t['amount'] else 0
                    self._add(t['coin'], t['amount'], eff, d)
                    if is_target and t['action'] == 'INCOME':
                        val = t['amount'] * t['price_usd']
                        self.inc_rows.append({'Date': d.date(), 'Source': t['source'], 'Coin': t['coin'], 'Amount': t['amount'], 'USD Value': round(val,2)})

                elif t['action'] == 'SELL':
                    net_proc = (t['amount'] * t['price_usd']) - t['fee']
                    basis, term, acq = self._sell(t['coin'], t['amount'], d)
                    if is_target:
                        self.tt_rows.append({'Description': f"{t['amount']} {t['coin']}", 'Date Acquired': acq, 'Date Sold': d.strftime('%m/%d/%Y'), 'Proceeds': round(net_proc, 2), 'Cost Basis': round(basis, 2), 'Gain/Loss': round(net_proc - basis, 2)})
            except: pass

    def _add(self, c, a, p, d):
        if c not in self.holdings: self.holdings[c] = []
        self.holdings[c].append({'a': a, 'p': p, 'd': d})

    def _sell(self, c, a, d):
        if c not in self.holdings: self.holdings[c] = []
        rem, b, ds = a, 0, set()
        while rem > 0 and self.holdings[c]:
            l = self.holdings[c][0]; ds.add(l['d'])
            if l['a'] <= rem: b += l['a'] * l['p']; rem -= l['a']; self.holdings[c].pop(0)
            else: b += rem * l['p']; l['a'] -= rem; rem = 0
        term = 'Long' if ds and (d - min(ds)).days > 365 else 'Short'
        acq = list(ds)[0].strftime('%m/%d/%Y') if len(ds)==1 else 'VARIOUS'
        return b, term, acq

    def export(self):
        ydir = OUTPUT_DIR / f"Year_{self.year}"
        if not ydir.exists(): ydir.mkdir(parents=True)
        if self.tt_rows: pd.DataFrame(self.tt_rows).to_csv(ydir / 'GENERIC_TAX_CAP_GAINS.csv', index=False)
        if self.inc_rows: pd.DataFrame(self.inc_rows).to_csv(ydir / 'INCOME_REPORT.csv', index=False)
        
        snapshot = []
        for coin, lots in self.holdings.items():
            total = sum(l['a'] for l in lots)
            if total > 0.000001:
                total_cost = sum(l['a'] * l['p'] for l in lots)
                snapshot.append({'Coin': coin, 'Holdings': round(total, 8), 'Total Cost Basis': round(total_cost, 2), 'Avg Price': round(total_cost/total, 2)})
        
        if snapshot:
            if self.year < datetime.now().year:
                pd.DataFrame(snapshot).to_csv(ydir / 'EOY_HOLDINGS_SNAPSHOT.csv', index=False)
                print(f"   -> [FINALIZED] Saved EOY_HOLDINGS_SNAPSHOT.csv")
            else:
                pd.DataFrame(snapshot).to_csv(ydir / 'CURRENT_HOLDINGS_DRAFT.csv', index=False)
                print(f"\n   [SAFEGUARD] Year {self.year} active. Saved 'CURRENT_HOLDINGS_DRAFT.csv'.")

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    sys.stdout = DualLogger(LOG_DIR / f"Manual_{timestamp}.log")

    print("--- CRYPTO TAX MASTER V18 (Logic Only) ---")
    
    # 0. SETUP VERIFICATION
    verify_setup()

    db = DatabaseManager()
    ingest = Ingestor(db)
    ingest.run_csv_scan()
    ingest.run_api_sync()
    
    bf = PriceFetcher()
    zeros = db.get_zeros()
    if not zeros.empty:
        print(f"\n--- Backfilling {len(zeros)} missing prices ---")
        for _, r in zeros.iterrows():
            p = bf.get_price(r['coin'], pd.to_datetime(r['date']))
            if p > 0: db.update_price(r['id'], p)
        db.commit()

    auditor = WalletAuditor(db)
    auditor.run_audit()

    try:
        y_input = input("\nEnter Tax Year: ")
        if y_input.isdigit():
            eng = TaxEngine(db, y_input)
            eng.run()
            eng.export()
    except Exception as e: print(f"Error: {e}")
    
    db.close()
    input("\nDone. Press Enter.")