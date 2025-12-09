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
CONFIG_FILE = BASE_DIR / 'config.json'

for d in [INPUT_DIR, ARCHIVE_DIR, OUTPUT_DIR, LOG_DIR]:
    if not d.exists(): d.mkdir(parents=True)

# ==========================================
# 0. CONFIG LOADER
# ==========================================
def load_config():
    defaults = {
        "general": {"run_audit": True, "create_db_backups": True},
        "performance": {"respect_free_tier_limits": True, "api_timeout_seconds": 30}
    }
    if not CONFIG_FILE.exists(): return defaults
    try:
        with open(CONFIG_FILE) as f: 
            user_config = json.load(f)
            # Merge defaults in case keys are missing
            for section, keys in defaults.items():
                if section not in user_config: user_config[section] = keys
                else:
                    for k, v in keys.items():
                        if k not in user_config[section]: user_config[section][k] = v
            return user_config
    except: return defaults

GLOBAL_CONFIG = load_config()

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
                if i == retries - 1: raise TimeoutError(f"{context} failed: {e}")
                time.sleep(delay * (backoff ** i))

class DualLogger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "a", encoding='utf-8')
    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()
    def flush(self): self.terminal.flush()

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
        if not GLOBAL_CONFIG['general']['create_db_backups']: return
        if DB_FILE.exists():
            self.conn.commit()
            try: shutil.copy(DB_FILE, DB_BACKUP)
            except: pass

    def restore_safety_backup(self):
        if not GLOBAL_CONFIG['general']['create_db_backups']: return
        if DB_BACKUP.exists():
            self.close()
            try:
                shutil.copy(DB_BACKUP, DB_FILE)
                self.conn = sqlite3.connect(str(DB_FILE))
                self.cursor = self.conn.cursor()
                print("   [SAFE] Restored database backup.")
            except: pass

    def remove_safety_backup(self): pass 

    def _ensure_integrity(self):
        if not DB_FILE.exists(): return
        try:
            c = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
            c.execute("PRAGMA integrity_check")
            c.close()
        except: self._recover_db()

    def _recover_db(self):
        ts = datetime.now().strftime("%Y%m%d")
        shutil.move(str(DB_FILE), str(BASE_DIR / f"CORRUPT_{ts}.db"))
        print("   [!] Database corrupted. Created fresh DB.")

    def _init_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS trades (id TEXT PRIMARY KEY, date TEXT, source TEXT, action TEXT, coin TEXT, amount REAL, price_usd REAL, fee REAL, batch_id TEXT)''')
        self.conn.commit()

    def get_last_timestamp(self, source):
        res = self.cursor.execute("SELECT date FROM trades WHERE source=? ORDER BY date DESC LIMIT 1", (source,)).fetchone()
        return int(pd.to_datetime(res[0]).timestamp()*1000) if res else 1262304000000

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
        print("\n--- 1. SCANNING INPUTS ---")
        self.db.create_safety_backup()
        try:
            found = False
            for fp in INPUT_DIR.glob('*.csv'):
                print(f"-> Processing: {fp.name}")
                found = True
                self._proc_csv(fp, f"CSV_{fp.name}_{datetime.now().strftime('%Y%m%d')}")
                self._archive(fp)
            if not found: print("   No new CSV files.")
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
                p = float(r.get('usd_value_at_time', 0))
                f = float(r.get('fee', 0))
                if p == 0: 
                    def gp(): return self.fetcher.get_price(coin, d)
                    p = NetworkRetry.run(gp)
                self.db.save_trade({'id': f"{src}_{d.strftime('%Y%m%d%H%M')}_{coin}_{amt}", 'date': d.isoformat(), 'source': src, 'action': 'INCOME' if src!='DEFI' else 'BUY', 'coin': coin, 'amount': amt, 'price_usd': p, 'fee': f, 'batch_id': batch})
            except: pass
        self.db.commit()

    def _archive(self, fp):
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        try: shutil.move(str(fp), str(ARCHIVE_DIR / f"{fp.stem}_PROC_{ts}{fp.suffix}"))
        except: pass

    def run_api_sync(self):
        print("\n--- 2. SYNCING APIS ---")
        if not KEYS_FILE.exists(): return
        with open(KEYS_FILE) as f: keys = json.load(f)
        self.db.create_safety_backup()
        try:
            timeout = GLOBAL_CONFIG['performance']['api_timeout_seconds']
            for name, creds in keys.items():
                if "PASTE_" in creds.get('apiKey', ''): continue
                if name == 'tokenview': continue
                if not hasattr(ccxt, name): continue
                
                def init(): return getattr(ccxt, name)({'apiKey': creds['apiKey'], 'secret': creds['secret'], 'enableRateLimit':True, 'timeout': timeout * 1000})
                ex = NetworkRetry.run(init)
                
                src = f"{name.upper()}_API"
                since = self.db.get_last_timestamp(src) + 1
                print(f"-> {name.upper()}: Trades since {pd.to_datetime(since, unit='ms')}")
                
                nt = []
                while True:
                    def ft(): return ex.fetch_my_trades(since=since)
                    b = NetworkRetry.run(ft)
                    if not b: break
                    nt.extend(b)
                    since = b[-1]['timestamp'] + 1
                
                if nt:
                    bid = f"API_{name}_{datetime.now().strftime('%Y%m%d')}"
                    try: pd.DataFrame(nt).to_csv(ARCHIVE_DIR/f"{bid}.csv", index=False)
                    except: pass
                    for t in nt:
                        self.db.save_trade({'id':f"{name}_{t['id']}", 'date':t['datetime'], 'source':src, 'action':'BUY' if t['side']=='buy' else 'SELL', 'coin':t['symbol'].split('/')[0], 'amount':float(t['amount']), 'price_usd':float(t['price']), 'fee':t['fee']['cost'] if t['fee'] else 0, 'batch_id':bid})
                    self.db.commit()
                    print(f"   Saved {len(nt)} trades.")

                if ex.has.get('fetchLedger'): self._sync_ledger(ex, name)
            self.db.remove_safety_backup()
        except: self.db.restore_safety_backup()

    def _sync_ledger(self, ex, name):
        src = f"{name.upper()}_LEDGER"
        since = self.db.get_last_timestamp(src) + 1
        print(f"   {name.upper()}: Checking Staking...")
        try:
            b = NetworkRetry.run(lambda: ex.fetch_ledger(since=since))
            if b:
                for i in b:
                    if any(x in i.get('type','').lower() for x in ['staking','reward','dividend']):
                        self.db.save_trade({'id':f"{name}_{i['id']}", 'date':i['datetime'], 'source':src, 'action':'INCOME', 'coin':i['currency'], 'amount':float(i['amount']), 'price_usd':0.0, 'fee':0, 'batch_id':'LEDGER'})
                self.db.commit()
        except: pass

# ==========================================
# 3. HELPER: PRICE FETCHER
# ==========================================
class PriceFetcher:
    def __init__(self): 
        self.cache = {}
        self.stables = {'USD','USDC','USDT','DAI','BUSD','PYUSD','GUSD'}
        self.cache_file = BASE_DIR/'stablecoins_cache.json'
        self._load_cache()

    def _load_cache(self):
        if self.cache_file.exists():
            try:
                if (datetime.now()-datetime.fromtimestamp(self.cache_file.stat().st_mtime)).days < 7:
                    with open(self.cache_file) as f: self.stables.update(json.load(f))
                    return
            except: pass
        self._fetch_api()

    def _fetch_api(self):
        try:
            r = requests.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&category=stablecoins", timeout=5)
            if r.status_code==200:
                for c in r.json(): self.stables.add(c['symbol'].upper())
                with open(self.cache_file,'w') as f: json.dump(list(self.stables),f)
        except: pass

    def get_price(self, s, d):
        if s.upper() in self.stables: return 1.0
        try:
            k = f"{s}_{d.date()}"
            if k in self.cache: return self.cache[k]
            def dp(): return yf.download(f"{s.upper()}-USD", start=d, end=d+timedelta(days=3), progress=False)
            df = NetworkRetry.run(dp, retries=3)
            if not df.empty: 
                v=df['Close'].iloc[0]; self.cache[k]=float(v.iloc[0] if isinstance(v,pd.Series) else v)
                return self.cache[k]
        except: pass
        return 0.0

# ==========================================
# 4. AUDITOR (TokenView Edition)
# ==========================================
class WalletAuditor:
    def __init__(self, db):
        self.db = db
        self.calc = {}
        self.real = {}
        self.api_key = self._load_tokenview_key()
        self.DECIMALS = {'BTC': 8, 'ETH': 18, 'LTC': 8, 'DOGE': 8, 'TRX': 6, 'SOL': 9, 'XRP': 6, 'ADA': 6, 'DOT': 10, 'MATIC': 18, 'AVAX': 18, 'BNB': 18}

    def _load_tokenview_key(self):
        if not KEYS_FILE.exists(): return None
        with open(KEYS_FILE) as f: 
            keys = json.load(f)
            return keys.get('tokenview', {}).get('apiKey')

    def run_audit(self):
        if not GLOBAL_CONFIG['general']['run_audit']:
            print("\n--- 4. AUDIT SKIPPED (Config) ---")
            return

        print("\n--- 4. RUNNING AUDIT (Via TokenView) ---")
        if not WALLETS_FILE.exists(): return
        if not self.api_key or "PASTE" in self.api_key:
            print("   [Skip] No TokenView API Key found.")
            return

        # DB Balances
        df = pd.read_sql_query("SELECT coin, amount, action FROM trades", self.db.conn)
        for _, r in df.iterrows():
            c = r['coin']
            if c not in self.calc: self.calc[c] = 0.0
            if r['action'] in ['BUY','INCOME']: self.calc[c] += r['amount']
            elif r['action'] == 'SELL': self.calc[c] -= r['amount']

        # Chain Balances
        with open(WALLETS_FILE) as f: wallets = json.load(f)
        for coin, addrs in wallets.items():
            if coin.startswith("_"): continue
            valid = [a for a in addrs if "PASTE_" not in a]
            if not valid: continue

            print(f"   Checking {coin} ({len(valid)} wallets)...")
            tot = 0.0
            for addr in valid:
                try:
                    bal = self.check_tokenview(coin, addr)
                    tot += bal
                except Exception as e: print(f"      [!] Failed: {addr[:6]}... ({e})")
                
                # CONFIG CHECK: Wait or Skip?
                if GLOBAL_CONFIG['performance']['respect_free_tier_limits']:
                    print("      [Free Tier] Pausing 2s...")
                    time.sleep(2.0)
                
            self.real[coin] = tot
            
        self.print_report()

    def check_tokenview(self, coin, addr):
        url = f"https://services.tokenview.io/vipapi/addr/b/{coin.lower()}/{addr}?apikey={self.api_key}"
        for attempt in range(3):
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 429: time.sleep(5); continue
                if r.status_code == 200:
                    data = r.json()
                    if data.get('code') != 1: return 0.0
                    return float(data.get('data', 0)) / (10 ** self.DECIMALS.get(coin.upper(), 18))
            except: time.sleep(1)
        return 0.0

    def print_report(self):
        print("\n   --- RECONCILIATION ---")
        print(f"   {'COIN':<5} | {'DB':<10} | {'CHAIN':<10} | {'DIFF':<10}")
        print("   " + "-"*40)
        for c in sorted(set(list(self.calc.keys())+list(self.real.keys()))):
            if c in self.real:
                d = self.calc.get(c,0) - self.real.get(c,0)
                stat = f"{d:+.4f}" if abs(d)>0.0001 else "OK"
                print(f"   {c:<5} | {self.calc.get(c,0):<10.4f} | {self.real.get(c,0):<10.4f} | {stat}")

# ==========================================
# 5. TAX ENGINE
# ==========================================
class TaxEngine:
    def __init__(self, db, y):
        self.db, self.year, self.tt, self.inc, self.hold = db, int(y), [], [], {}

    def run(self):
        print(f"\n--- 5. REPORT ({self.year}) ---")
        df = self.db.get_all()
        for _, t in df.iterrows():
            d = pd.to_datetime(t['date'])
            if d.year > self.year: continue
            is_yr = (d.year == self.year)
            
            if t['action'] in ['BUY','INCOME']:
                c = (t['amount']*t['price_usd'])+t['fee']
                self._add(t['coin'], t['amount'], c/t['amount'] if t['amount'] else 0, d)
                if is_yr and t['action']=='INCOME': self.inc.append({'Date':d.date(),'Coin':t['coin'],'Amt':t['amount'],'USD':round(t['amount']*t['price_usd'],2)})
            
            elif t['action'] == 'SELL':
                net = (t['amount']*t['price_usd'])-t['fee']
                b, term, acq = self._sell(t['coin'], t['amount'], d)
                if is_yr: self.tt.append({'Description':f"{t['amount']} {t['coin']}", 'Date Acquired':acq, 'Date Sold':d.strftime('%m/%d/%Y'), 'Proceeds':round(net,2), 'Cost Basis':round(b,2)})

    def _add(self, c, a, p, d):
        if c not in self.hold: self.hold[c]=[]
        self.hold[c].append({'a':a,'p':p,'d':d})

    def _sell(self, c, a, d):
        if c not in self.hold: self.hold[c]=[]
        rem, b, ds = a, 0, set()
        while rem>0 and self.hold[c]:
            l=self.hold[c][0]; ds.add(l['d'])
            if l['a']<=rem: b+=l['a']*l['p']; rem-=l['a']; self.hold[c].pop(0)
            else: b+=rem*l['p']; l['a']-=rem; rem=0
        return b, 'Long' if ds and (d-min(ds)).days>365 else 'Short', list(ds)[0].strftime('%m/%d/%Y') if len(ds)==1 else 'VARIOUS'

    def export(self):
        yd = OUTPUT_DIR/f"Year_{self.year}"
        if not yd.exists(): yd.mkdir(parents=True)
        if self.tt: pd.DataFrame(self.tt).to_csv(yd/'TURBOTAX_CAP_GAINS.csv', index=False)
        if self.inc: pd.DataFrame(self.inc).to_csv(yd/'INCOME_REPORT.csv', index=False)
        
        snap = []
        for c, ls in self.hold.items():
            t = sum(l['a'] for l in ls)
            if t>0.000001: snap.append({'Coin':c, 'Holdings':round(t,8), 'Value':round(sum(l['a']*l['p'] for l in ls),2)})
        
        if snap:
            fn = 'EOY_HOLDINGS_SNAPSHOT.csv' if self.year < datetime.now().year else 'CURRENT_HOLDINGS_DRAFT.csv'
            pd.DataFrame(snap).to_csv(yd/fn, index=False)
            print(f"   -> Saved {fn}")

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    sys.stdout = DualLogger(LOG_DIR/f"Manual_{ts}.log")
    
    print("--- CRYPTO TAX MASTER V20 (Configurable) ---")
    
    if not KEYS_FILE.exists():
        print("CRITICAL: Missing Config Files. Run 'setup_env.py' first.")
        sys.exit(1)
    
    db = DatabaseManager()
    ingest = Ingestor(db)
    ingest.run_csv_scan()
    ingest.run_api_sync()
    
    bf = PriceFetcher()
    for _, r in db.get_zeros().iterrows():
        p = bf.get_price(r['coin'], pd.to_datetime(r['date']))
        if p>0: db.update_price(r['id'], p)
    db.commit()

    WalletAuditor(db).run_audit()

    try:
        y = input("\nEnter Tax Year: ")
        if y.isdigit():
            eng = TaxEngine(db, y)
            eng.run()
            eng.export()
    except Exception as e: print(f"Error: {e}")
    
    db.close()
    input("\nDone. Press Enter.")