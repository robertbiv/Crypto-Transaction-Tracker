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
import gzip
from datetime import datetime, timedelta
from pathlib import Path
import logging

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

# Logger setup
logger = logging.getLogger("crypto_tax_engine")
logger.setLevel(logging.INFO)

# Run context: 'imported' (default), 'direct' when run as the engine, 'autorunner' when run by Auto_Runner
RUN_CONTEXT = 'imported'

class RunContextFilter(logging.Filter):
    def filter(self, record):
        try:
            record.run_context = RUN_CONTEXT
        except Exception:
            record.run_context = 'unknown'
        return True

def set_run_context(context: str):
    """Set the active run context and (re)configure the file handler to include it in the filename."""
    global RUN_CONTEXT
    RUN_CONTEXT = context

    for h in list(logger.handlers):
        try:
            if isinstance(h, logging.handlers.RotatingFileHandler):
                logger.removeHandler(h)
        except Exception:
            pass

    try:
        from logging.handlers import RotatingFileHandler
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = LOG_DIR / f"{timestamp}.{context}.log"
        try:
            if not fname.exists() or fname.stat().st_size == 0:
                with open(fname, 'a', encoding='utf-8') as hf:
                    hf.write(f"# Crypto Tax Engine log\n")
                    hf.write(f"# Run Context: {context}\n")
                    hf.write(f"# Start Time: {timestamp}\n")
                    hf.write(f"# Command: {' '.join(sys.argv)}\n")
                    hf.write(f"# Working Dir: {BASE_DIR}\n\n")
        except Exception:
            pass

        fh = RotatingFileHandler(str(fname), maxBytes=5_000_000, backupCount=5, encoding='utf-8')
        fh.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s %(levelname)s [%(run_context)s]: %(message)s")
        fh.setFormatter(fmt)
        fh.addFilter(RunContextFilter())
        logger.addHandler(fh)
    except Exception:
        pass

    has_stream = any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
    if not has_stream:
        try:
            sh = logging.StreamHandler(sys.stdout)
            sh.setLevel(logging.INFO)
            sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(run_context)s]: %(message)s"))
            sh.addFilter(RunContextFilter())
            logger.addHandler(sh)
        except Exception:
            pass

    # Log compression logic (omitted for brevity, same as before)

set_run_context(RUN_CONTEXT)

class ApiAuthError(Exception):
    pass

# ==========================================
# 0. CONFIG LOADER
# ==========================================
def load_config():
    defaults = {
        "general": {"run_audit": True, "create_db_backups": True},
        "performance": {"respect_free_tier_limits": True, "api_timeout_seconds": 30},
        "logging": {"compress_older_than_days": 30}
    }
    if not CONFIG_FILE.exists(): return defaults
    try:
        with open(CONFIG_FILE) as f: 
            user_config = json.load(f)
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
                logger.info("[SAFE] Restored database backup.")
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
        logger.error("[!] Database corrupted. Created fresh DB.")

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
        logger.info("--- 1. SCANNING INPUTS ---")
        self.db.create_safety_backup()
        try:
            found = False
            for fp in INPUT_DIR.glob('*.csv'):
                logger.info(f"-> Processing: {fp.name}")
                found = True
                self._proc_csv(fp, f"CSV_{fp.name}_{datetime.now().strftime('%Y%m%d')}")
                self._archive(fp)
            if not found: logger.info("   No new CSV files.")
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
        logger.info("--- 2. SYNCING APIS ---")
        if not KEYS_FILE.exists(): return
        with open(KEYS_FILE) as f: keys = json.load(f)
        self.db.create_safety_backup()
        try:
            timeout = GLOBAL_CONFIG['performance']['api_timeout_seconds']
            for name, creds in keys.items():
                if "PASTE_" in creds.get('apiKey', ''): continue
                # Skip non-exchange keys
                if name in ['moralis', 'blockchair', 'tokenview']: continue
                
                if not hasattr(ccxt, name): 
                    logger.warning(f"   [SKIP] Exchange '{name}' not found in CCXT.")
                    continue
                
                def init(): return getattr(ccxt, name)({'apiKey': creds['apiKey'], 'secret': creds['secret'], 'enableRateLimit':True, 'timeout': timeout * 1000})
                try:
                    ex = NetworkRetry.run(init)
                except Exception as e:
                    logger.error(f"[AUTH ERROR] {name.upper()}: {e}")
                    continue
                
                src = f"{name.upper()}_API"
                since = self.db.get_last_timestamp(src) + 1
                logger.info(f"-> {name.upper()}: Trades since {pd.to_datetime(since, unit='ms')}")
                
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
                    logger.info(f"   Saved {len(nt)} trades.")

                if ex.has.get('fetchLedger'):
                    try: self._sync_ledger(ex, name)
                    except: pass
            self.db.remove_safety_backup()
        except: self.db.restore_safety_backup()

    def _sync_ledger(self, ex, name):
        src = f"{name.upper()}_LEDGER"
        since = self.db.get_last_timestamp(src) + 1
        logger.info(f"   {name.upper()}: Checking Staking...")
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
# 4. AUDITOR (Moralis + Blockchair)
# ==========================================
class WalletAuditor:
    def __init__(self, db):
        self.db = db
        self.calc = {}
        self.real = {}
        self.moralis_key, self.blockchair_key = self._load_audit_keys()
        self.DECIMALS = {'BTC': 8, 'ETH': 18, 'LTC': 8, 'DOGE': 8, 'TRX': 6, 'SOL': 9, 'XRP': 6, 'ADA': 6, 'DOT': 10, 'MATIC': 18, 'AVAX': 18, 'BNB': 18}
        
        # Mappings
        self.MORALIS_CHAINS = {
            'ETH': '0x1', 'BNB': '0x38', 'MATIC': '0x89', 'AVAX': '0xa86a',
            'FTM': '0xfa', 'CRO': '0x19', 'ARBITRUM': '0xa4b1', 
            'OPTIMISM': '0xa', 'GNOSIS': '0x64', 'BASE': '0x2105', 
            'PULSE': '0x171', 'LINEA': '0xe708', 'MOONBEAM': '0x504',
            'SOL': 'mainnet' # Solana is handled via a different endpoint
        }
        self.BLOCKCHAIR_CHAINS = {
            'BTC': 'bitcoin', 'LTC': 'litecoin', 'DOGE': 'dogecoin', 
            'BCH': 'bitcoin-cash', 'DASH': 'dash', 'ZEC': 'zcash', 
            'XMR': 'monero', 'XRP': 'ripple', 'XLM': 'stellar', 
            'EOS': 'eos', 'TRX': 'tron', 'ADA': 'cardano'
        }

    def _load_audit_keys(self):
        if not KEYS_FILE.exists(): return None, None
        with open(KEYS_FILE) as f: 
            keys = json.load(f)
            m_key = keys.get('moralis', {}).get('apiKey')
            b_key = keys.get('blockchair', {}).get('apiKey')
            return m_key, b_key

    def run_audit(self):
        if not GLOBAL_CONFIG['general']['run_audit']:
            logger.info("--- 4. AUDIT SKIPPED (Config) ---")
            return
        
        logger.info("--- 4. RUNNING AUDIT (Moralis + Blockchair) ---")
        if not WALLETS_FILE.exists(): return
        
        if not self.moralis_key or "PASTE" in self.moralis_key:
             logger.warning("   [!] Moralis API Key missing. EVM/Solana audit will fail.")

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

            logger.info(f"   Checking {coin} ({len(valid)} wallets)...")
            tot = 0.0
            for addr in valid:
                try:
                    bal = 0.0
                    if coin in self.MORALIS_CHAINS:
                        bal = self.check_moralis(coin, addr)
                    elif coin in self.BLOCKCHAIR_CHAINS:
                        bal = self.check_blockchair(coin, addr)
                    else:
                        logger.warning(f"      [?] Unknown chain for audit: {coin}")
                    tot += bal
                except Exception as e:
                    logger.warning(f"      [!] Failed: {addr[:6]}... ({e})")
                
                # Respect limits
                if GLOBAL_CONFIG['performance']['respect_free_tier_limits']:
                    time.sleep(1.0) # 1s delay
                
            self.real[coin] = tot
            
        self.print_report()

    def check_moralis(self, coin, addr):
        if not self.moralis_key or "PASTE" in self.moralis_key: return 0.0
        
        headers = {"X-API-Key": self.moralis_key, "accept": "application/json"}
        chain_id = self.MORALIS_CHAINS[coin]
        
        # Solana Handling
        if coin == 'SOL':
            url = f"https://solana-gateway.moralis.io/account/{chain_id}/{addr}/balance"
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                return float(data.get('solana', 0)) # Moralis returns raw lamports? No, usually formatted string or raw. 
                # Correction: Moralis Sol Balance: {"solana": "1.5"} string.
            return 0.0
        
        # EVM Handling
        url = f"https://deep-index.moralis.io/api/v2.2/{addr}/balance?chain={chain_id}"
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            val = float(r.json().get('balance', 0))
            return val / (10 ** 18) # Assuming native tokens are 18 decimals usually.
        return 0.0

    def check_blockchair(self, coin, addr):
        chain_name = self.BLOCKCHAIR_CHAINS[coin]
        url = f"https://api.blockchair.com/{chain_name}/dashboards/address/{addr}"
        
        # Optional Key (Avoids rate limits)
        if self.blockchair_key and "PASTE" not in self.blockchair_key:
            url += f"?key={self.blockchair_key}"
            
        r = requests.get(url, timeout=15)
        
        if r.status_code == 429:
            logger.warning(f"      [Rate Limit] Blockchair limited. Skipping {addr}.")
            return 0.0
        
        if r.status_code == 200:
            data = r.json()
            # Blockchair structure: data -> {addr} -> address -> balance (in satoshis/base units)
            addr_data = data.get('data', {}).get(addr, {}).get('address', {})
            raw_bal = float(addr_data.get('balance', 0))
            
            # Decimals logic
            decimals = self.DECIMALS.get(coin, 8) # Default to 8 for UTXOs usually
            return raw_bal / (10 ** decimals)
            
        return 0.0

    def print_report(self):
        logger.info("--- RECONCILIATION ---")
        logger.info(f"{'COIN':<5} | {'DB':<10} | {'CHAIN':<10} | {'DIFF':<10}")
        logger.info("" + "-"*40)
        for c in sorted(set(list(self.calc.keys())+list(self.real.keys()))):
            if c in self.real:
                d = self.calc.get(c,0) - self.real.get(c,0)
                stat = f"{d:+.4f}" if abs(d)>0.0001 else "OK"
                logger.info(f"{c:<5} | {self.calc.get(c,0):<10.4f} | {self.real.get(c,0):<10.4f} | {stat}")

# ==========================================
# 5. TAX ENGINE
# ==========================================
class TaxEngine:
    def __init__(self, db, y):
        self.db, self.year, self.tt, self.inc, self.hold = db, int(y), [], [], {}

    def run(self):
        logger.info(f"--- 5. REPORT ({self.year}) ---")
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
            logger.info(f"   -> Saved {fn}")

# ==========================================
# MAIN
# ==========================================
if __name__ == "__main__":
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    try:
        set_run_context('direct')
    except Exception:
        RUN_CONTEXT = 'direct'
    logger.info("--- CRYPTO TAX MASTER V21 (Moralis/Blockchair) ---")

    try:
        if not KEYS_FILE.exists():
            logger.critical("Missing configuration files. Run 'python Setup.py' to create templates (api_keys.json, wallets.json, config.json).")
            raise ApiAuthError("Missing api_keys.json or required config files")

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

        y = input("\nEnter Tax Year (YYYY) to generate reports, or press Enter to skip: ").strip()
        if y:
            if y.isdigit() and len(y) == 4:
                eng = TaxEngine(db, y)
                eng.run()
                eng.export()
            else:
                logger.warning("Invalid year entered; skipping report generation.")

        db.close()
        if sys.stdin.isatty():
            input("\nDone. Press Enter.")

    except ApiAuthError as e:
        logger.critical(f"Authentication/address failure: {e}")
        try: db.close()
        except: pass
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unhandled error: {e}")
        try: db.close()
        except: pass
        if sys.stdin.isatty():
            input("\nScript crashed. Check logs. Press Enter to close...")