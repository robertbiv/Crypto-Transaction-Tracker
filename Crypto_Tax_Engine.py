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

logger = logging.getLogger("crypto_tax_engine")
logger.setLevel(logging.INFO)
RUN_CONTEXT = 'imported'

class RunContextFilter(logging.Filter):
    def filter(self, record):
        try: record.run_context = RUN_CONTEXT
        except: record.run_context = 'unknown'
        return True

def set_run_context(context: str):
    global RUN_CONTEXT
    RUN_CONTEXT = context
    for h in list(logger.handlers): logger.removeHandler(h)
    try:
        if not LOG_DIR.exists(): 
            try: LOG_DIR.mkdir(parents=True)
            except: pass
        from logging.handlers import RotatingFileHandler
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fname = LOG_DIR / f"{timestamp}.{context}.log"
        fh = RotatingFileHandler(str(fname), maxBytes=5_000_000, backupCount=5, encoding='utf-8')
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(run_context)s]: %(message)s"))
        fh.addFilter(RunContextFilter())
        logger.addHandler(fh)
    except: pass
    if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
        sh = logging.StreamHandler(sys.stdout)
        sh.setLevel(logging.INFO)
        sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(run_context)s]: %(message)s"))
        sh.addFilter(RunContextFilter())
        logger.addHandler(sh)

set_run_context(RUN_CONTEXT)

class ApiAuthError(Exception): pass

def initialize_folders():
    for d in [INPUT_DIR, ARCHIVE_DIR, OUTPUT_DIR, LOG_DIR]:
        if not d.exists(): d.mkdir(parents=True)

def load_config():
    defaults = {"general": {"run_audit": True, "create_db_backups": True}, "performance": {"respect_free_tier_limits": True, "api_timeout_seconds": 30}, "logging": {"compress_older_than_days": 30}}
    if not CONFIG_FILE.exists(): return defaults
    try:
        with open(CONFIG_FILE) as f: 
            user = json.load(f)
            for k, v in defaults.items():
                if k not in user: user[k] = v
                else: 
                    for sk, sv in v.items():
                        if sk not in user[k]: user[k][sk] = sv
            return user
    except: return defaults

GLOBAL_CONFIG = load_config()

class NetworkRetry:
    @staticmethod
    def run(func, retries=5, delay=2, backoff=2, context="Network"):
        for i in range(retries):
            try: return func()
            except Exception as e:
                if i == retries - 1: raise TimeoutError(f"{context} failed: {e}")
                time.sleep(delay * (backoff ** i))

class DatabaseManager:
    def __init__(self):
        initialize_folders()
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
# 2. INGESTOR
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
                self._proc_csv_smart(fp, f"CSV_{fp.name}_{datetime.now().strftime('%Y%m%d')}")
                self._archive(fp)
            if not found: logger.info("   No new CSV files.")
            self.db.remove_safety_backup()
        except: self.db.restore_safety_backup()

    def _proc_csv_smart(self, fp, batch):
        df = pd.read_csv(fp)
        df.columns = [c.lower().strip() for c in df.columns]
        for idx, r in df.iterrows():
            try:
                d = pd.to_datetime(r.get('date', r.get('timestamp', datetime.now())))
                tx_type = str(r.get('type', r.get('kind', 'trade'))).lower()
                sent_c = r.get('sent_coin', r.get('sent_asset', r.get('coin', None)))
                sent_a = float(r.get('sent_amount', r.get('amount', 0)))
                recv_c = r.get('received_coin', r.get('received_asset', None))
                recv_a = float(r.get('received_amount', 0))
                fee = float(r.get('fee', 0))
                
                if any(x in tx_type for x in ['default', 'loss', 'bad_debt', 'stolen', 'hacked', 'liquidation']):
                    if sent_c and sent_a > 0: self.db.save_trade({'id': f"{batch}_{idx}_LOSS", 'date': d.isoformat(), 'source': 'LOSS', 'action': 'LOSS', 'coin': str(sent_c), 'amount': sent_a, 'price_usd': 0.0, 'fee': 0, 'batch_id': batch})
                elif any(x in tx_type for x in ['borrow', 'deposit_collateral']):
                    if recv_c and recv_a > 0: self.db.save_trade({'id': f"{batch}_{idx}_DEP", 'date': d.isoformat(), 'source': 'LOAN', 'action': 'DEPOSIT', 'coin': str(recv_c), 'amount': recv_a, 'price_usd': 0, 'fee': 0, 'batch_id': batch})
                    elif sent_c and sent_a > 0: self.db.save_trade({'id': f"{batch}_{idx}_WIT", 'date': d.isoformat(), 'source': 'LOAN', 'action': 'WITHDRAWAL', 'coin': str(sent_c), 'amount': sent_a, 'price_usd': 0, 'fee': 0, 'batch_id': batch})
                elif 'repay' in tx_type:
                    if sent_c and sent_a > 0: self.db.save_trade({'id': f"{batch}_{idx}_REP", 'date': d.isoformat(), 'source': 'LOAN', 'action': 'WITHDRAWAL', 'coin': str(sent_c), 'amount': sent_a, 'price_usd': 0, 'fee': 0, 'batch_id': batch})
                elif sent_c and recv_c and sent_a > 0 and recv_a > 0:
                    p = float(r.get('usd_value_at_time', 0))
                    if p==0: p = self.fetcher.get_price(str(sent_c), d) * sent_a
                    self.db.save_trade({'id': f"{batch}_{idx}_SELL", 'date': d.isoformat(), 'source': 'SWAP', 'action': 'SELL', 'coin': str(sent_c), 'amount': sent_a, 'price_usd': (p/sent_a) if sent_a else 0, 'fee': fee, 'batch_id': batch})
                    self.db.save_trade({'id': f"{batch}_{idx}_BUY", 'date': d.isoformat(), 'source': 'SWAP', 'action': 'BUY', 'coin': str(recv_c), 'amount': recv_a, 'price_usd': (p/recv_a) if recv_a else 0, 'fee': 0, 'batch_id': batch})
                elif recv_c and recv_a > 0:
                    act = 'INCOME' if any(x in tx_type for x in ['airdrop','staking','reward','gift','promo','interest']) else 'BUY'
                    p = float(r.get('usd_value_at_time', 0))
                    if p==0: p = self.fetcher.get_price(str(recv_c), d)
                    self.db.save_trade({'id': f"{batch}_{idx}_IN", 'date': d.isoformat(), 'source': 'MANUAL', 'action': act, 'coin': str(recv_c), 'amount': recv_a, 'price_usd': p, 'fee': fee, 'batch_id': batch})
                elif sent_c and sent_a > 0:
                    p = float(r.get('usd_value_at_time', 0))
                    if p==0: p = self.fetcher.get_price(str(sent_c), d)
                    self.db.save_trade({'id': f"{batch}_{idx}_OUT", 'date': d.isoformat(), 'source': 'MANUAL', 'action': 'SELL', 'coin': str(sent_c), 'amount': sent_a, 'price_usd': p, 'fee': fee, 'batch_id': batch})
            except Exception as e: logger.warning(f"   [SKIP] Row {idx} failed: {e}")
        self.db.commit()

    def _archive(self, fp):
        try: shutil.move(str(fp), str(ARCHIVE_DIR / f"{fp.stem}_PROC_{datetime.now().strftime('%Y%m%d_%H%M')}{fp.suffix}"))
        except: pass

    def run_api_sync(self):
        logger.info("--- 2. SYNCING APIS ---")
        if not KEYS_FILE.exists(): return
        with open(KEYS_FILE) as f: keys = json.load(f)
        self.db.create_safety_backup()
        try:
            for name, creds in keys.items():
                if "PASTE_" in creds.get('apiKey', '') or not hasattr(ccxt, name): continue
                ex = getattr(ccxt, name)({'apiKey': creds['apiKey'], 'secret': creds['secret'], 'enableRateLimit':True})
                src = f"{name.upper()}_API"
                since = self.db.get_last_timestamp(src) + 1
                nt = []
                while True:
                    try:
                        b = ex.fetch_my_trades(since=since)
                        if not b: break
                        nt.extend(b)
                        since = b[-1]['timestamp'] + 1
                    except: break
                for t in nt:
                    self.db.save_trade({'id':f"{name}_{t['id']}", 'date':t['datetime'], 'source':src, 'action':'BUY' if t['side']=='buy' else 'SELL', 'coin':t['symbol'].split('/')[0], 'amount':float(t['amount']), 'price_usd':float(t['price']), 'fee':t['fee']['cost'] if t['fee'] else 0, 'batch_id':f"API_{name}"})
                self.db.commit()
                if ex.has.get('fetchLedger'): self._sync_ledger(ex, name)
            self.db.remove_safety_backup()
        except: self.db.restore_safety_backup()

    def _sync_ledger(self, ex, name):
        try:
            b = NetworkRetry.run(lambda: ex.fetch_ledger(since=self.db.get_last_timestamp(f"{name.upper()}_LEDGER")+1))
            if b:
                for i in b:
                    t = i.get('type','').lower()
                    if any(x in t for x in ['staking','reward','dividend','airdrop','promo']):
                        self.db.save_trade({'id':f"{name}_{i['id']}", 'date':i['datetime'], 'source':f"{name.upper()}_LEDGER", 'action':'INCOME', 'coin':i['currency'], 'amount':float(i['amount']), 'price_usd':0.0, 'fee':0, 'batch_id':'LEDGER'})
                self.db.commit()
        except: pass

# ==========================================
# 3. PRICE FETCHER
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
            df = NetworkRetry.run(lambda: yf.download(f"{s.upper()}-USD", start=d, end=d+timedelta(days=3), progress=False), retries=3)
            if not df.empty: 
                v=df['Close'].iloc[0]; self.cache[k]=float(v.iloc[0] if isinstance(v,pd.Series) else v)
                return self.cache[k]
        except: pass
        return 0.0

# ==========================================
# 4. AUDITOR
# ==========================================
class WalletAuditor:
    def __init__(self, db):
        self.db = db
        self.calc = {}
        self.real = {}
        self.moralis_key, self.blockchair_key = self._load_audit_keys()
        self.DECIMALS = {'BTC': 8, 'ETH': 18, 'LTC': 8, 'DOGE': 8, 'TRX': 6, 'SOL': 9, 'XRP': 6, 'ADA': 6, 'DOT': 10, 'MATIC': 18, 'AVAX': 18, 'BNB': 18}
        self.MORALIS_CHAINS = {'ETH': '0x1', 'BNB': '0x38', 'MATIC': '0x89', 'AVAX': '0xa86a', 'FTM': '0xfa', 'CRO': '0x19', 'ARBITRUM': '0xa4b1', 'OPTIMISM': '0xa', 'GNOSIS': '0x64', 'BASE': '0x2105', 'PULSE': '0x171', 'LINEA': '0xe708', 'MOONBEAM': '0x504', 'SOL': 'mainnet'}
        self.BLOCKCHAIR_CHAINS = {'BTC': 'bitcoin', 'LTC': 'litecoin', 'DOGE': 'dogecoin', 'BCH': 'bitcoin-cash', 'DASH': 'dash', 'ZEC': 'zcash', 'XMR': 'monero', 'XRP': 'ripple', 'XLM': 'stellar', 'EOS': 'eos', 'TRX': 'tron', 'ADA': 'cardano'}

    def _load_audit_keys(self):
        if not KEYS_FILE.exists(): return None, None
        with open(KEYS_FILE) as f: keys = json.load(f)
        return keys.get('moralis', {}).get('apiKey'), keys.get('blockchair', {}).get('apiKey')

    def run_audit(self):
        if not GLOBAL_CONFIG['general']['run_audit']:
            logger.info("--- 4. AUDIT SKIPPED (Config) ---")
            return
        logger.info("--- 4. RUNNING AUDIT ---")
        if not WALLETS_FILE.exists(): return
        
        df = pd.read_sql_query("SELECT coin, amount, action FROM trades", self.db.conn)
        for _, r in df.iterrows():
            c = r['coin']
            if c not in self.calc: self.calc[c] = 0.0
            if r['action'] in ['BUY','INCOME','DEPOSIT']: self.calc[c] += r['amount']
            elif r['action'] in ['SELL','SPEND','WITHDRAWAL','LOSS']: self.calc[c] -= r['amount']

        with open(WALLETS_FILE) as f: wallets = json.load(f)
        for coin, addrs in wallets.items():
            if coin.startswith("_"): continue
            valid = [a for a in addrs if "PASTE_" not in a]
            if not valid: continue
            logger.info(f"   Checking {coin}...")
            tot = 0.0
            for addr in valid:
                try:
                    if coin in self.MORALIS_CHAINS: tot += self.check_moralis(coin, addr)
                    elif coin in self.BLOCKCHAIR_CHAINS: tot += self.check_blockchair(coin, addr)
                except Exception as e: logger.warning(f"      [!] Failed: {addr[:6]}... ({e})")
                if GLOBAL_CONFIG['performance']['respect_free_tier_limits']: time.sleep(1.0)
            self.real[coin] = tot
        self.print_report()

    def check_moralis(self, coin, addr):
        if not self.moralis_key or "PASTE" in self.moralis_key: return 0.0
        headers = {"X-API-Key": self.moralis_key, "accept": "application/json"}
        chain_id = self.MORALIS_CHAINS[coin]
        if coin == 'SOL':
            url = f"https://solana-gateway.moralis.io/account/{chain_id}/{addr}/balance"
            r = requests.get(url, headers=headers, timeout=10)
            return float(r.json().get('solana', 0)) if r.status_code == 200 else 0.0
        url = f"https://deep-index.moralis.io/api/v2.2/{addr}/balance?chain={chain_id}"
        r = requests.get(url, headers=headers, timeout=10)
        return (float(r.json().get('balance', 0)) / 10**18) if r.status_code == 200 else 0.0

    def check_blockchair(self, coin, addr):
        chain = self.BLOCKCHAIR_CHAINS[coin]
        url = f"https://api.blockchair.com/{chain}/dashboards/address/{addr}"
        if self.blockchair_key and "PASTE" not in self.blockchair_key: url += f"?key={self.blockchair_key}"
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            bal = float(r.json().get('data', {}).get(addr, {}).get('address', {}).get('balance', 0))
            return bal / (10 ** self.DECIMALS.get(coin, 8))
        return 0.0

    def print_report(self):
        logger.info("--- RECONCILIATION ---")
        logger.info(f"{'COIN':<5} | {'DB':<10} | {'CHAIN':<10} | {'DIFF':<10}")
        logger.info("-"*45)
        for c in sorted(set(list(self.calc.keys())+list(self.real.keys()))):
            if c in self.real:
                d = self.calc.get(c,0) - self.real.get(c,0)
                stat = f"{d:+.4f}" if abs(d)>0.0001 else "OK"
                logger.info(f"{c:<5} | {self.calc.get(c,0):<10.4f} | {self.real.get(c,0):<10.4f} | {stat}")

# ==========================================
# 5. TAX ENGINE (V26: Auto-Carryover Import)
# ==========================================
class TaxEngine:
    def __init__(self, db, y):
        self.db, self.year, self.tt, self.inc, self.hold = db, int(y), [], [], {}
        self.us_losses = {'short': 0.0, 'long': 0.0} 
        self.prior_carryover = {'short': 0.0, 'long': 0.0}
        self.wash_sale_log = []
        
        # AUTO IMPORT PRIOR YEAR LOSSES
        self._load_prior_year_data()

    def _load_prior_year_data(self):
        """Looks for previous year's Loss Report and imports Carryover."""
        prior_file = OUTPUT_DIR / f"Year_{self.year - 1}" / "US_TAX_LOSS_ANALYSIS.csv"
        if prior_file.exists():
            try:
                df = pd.read_csv(prior_file)
                # Parse Short Term Carryover
                row_short = df[df['Item'] == 'Short-Term Carryover to Next Year']
                if not row_short.empty:
                    val = float(row_short['Value'].iloc[0])
                    self.prior_carryover['short'] = val
                    self.us_losses['short'] += val # Apply immediately as starting loss
                    logger.info(f"   [INFO] Imported Short-Term Carryover from {self.year-1}: ${val}")

                # Parse Long Term Carryover
                row_long = df[df['Item'] == 'Long-Term Carryover to Next Year']
                if not row_long.empty:
                    val = float(row_long['Value'].iloc[0])
                    self.prior_carryover['long'] = val
                    self.us_losses['long'] += val # Apply immediately
                    logger.info(f"   [INFO] Imported Long-Term Carryover from {self.year-1}: ${val}")
                    
                # Compatibility with V24 (Legacy lumped carryover)
                if row_short.empty and row_long.empty:
                    row_legacy = df[df['Item'] == 'Carryover Loss to Next Year']
                    if not row_legacy.empty:
                        val = float(row_legacy['Value'].iloc[0])
                        self.prior_carryover['long'] += val # Assume Long if unknown
                        self.us_losses['long'] += val
                        logger.info(f"   [INFO] Imported Legacy Carryover from {self.year-1}: ${val}")
            except Exception as e:
                logger.warning(f"   [WARN] Failed to read prior year carryover: {e}")

    def run(self):
        logger.info(f"--- 5. REPORT ({self.year}) ---")
        df = self.db.get_all()
        all_buys = df[df['action'].isin(['BUY', 'INCOME'])]
        all_buys_dict = {}
        for _, r in all_buys.iterrows():
            c = r['coin']
            if c not in all_buys_dict: all_buys_dict[c] = []
            all_buys_dict[c].append(pd.to_datetime(r['date']))

        for _, t in df.iterrows():
            d = pd.to_datetime(t['date'])
            if d.year > self.year: continue
            is_yr = (d.year == self.year)
            
            if t['action'] in ['BUY','INCOME']:
                c = (t['amount']*t['price_usd'])+t['fee']
                self._add(t['coin'], t['amount'], c/t['amount'] if t['amount'] else 0, d)
                if is_yr and t['action']=='INCOME': 
                    self.inc.append({'Date':d.date(),'Coin':t['coin'],'Amt':t['amount'],'USD':round(t['amount']*t['price_usd'],2)})

            elif t['action'] == 'DEPOSIT':
                self._add(t['coin'], t['amount'], 0, d) 

            elif t['action'] in ['SELL','SPEND','LOSS']:
                net = (t['amount']*t['price_usd'])-t['fee']
                if t['action'] == 'LOSS': net = 0.0
                
                b, term, acq = self._sell(t['coin'], t['amount'], d)
                
                gain = net - b
                wash_disallowed = 0.0
                
                if gain < 0:
                    window_start = d - timedelta(days=30)
                    window_end = d + timedelta(days=30)
                    if t['coin'] in all_buys_dict:
                        nearby_buys = [bd for bd in all_buys_dict[t['coin']] if window_start <= bd <= window_end and bd != d]
                        if nearby_buys:
                            wash_disallowed = abs(gain)
                            if is_yr:
                                self.wash_sale_log.append({'Date': d.date(), 'Coin': t['coin'], 'Loss Disallowed': round(wash_disallowed, 2), 'Note': 'Loss disallowed/deferred (Wash Sale).'})
                                logger.warning(f"   [WASH SALE] {t['coin']} loss disallowed.")
                
                final_basis = b
                if wash_disallowed > 0: final_basis = net 
                
                if is_yr: 
                    desc = f"{t['amount']} {t['coin']}" + (" (Fee)" if t['source']=='TRANSFER_FEE' else "")
                    if t['action'] == 'LOSS': desc = f"LOSS: {desc}"
                    if wash_disallowed > 0: desc += " (WASH SALE)"
                    
                    realized_gain = net - final_basis
                    if realized_gain < 0:
                        if term == 'Short': self.us_losses['short'] += abs(realized_gain)
                        else: self.us_losses['long'] += abs(realized_gain)

                    self.tt.append({'Description':desc, 'Date Acquired':acq, 'Date Sold':d.strftime('%m/%d/%Y'), 'Proceeds':round(net,2), 'Cost Basis':round(final_basis,2), 'Term': term})

            elif t['action'] == 'WITHDRAWAL':
                self._sell(t['coin'], t['amount'], d)

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
        term = 'Short'
        if ds:
            earliest = min(ds)
            if (d - earliest).days > 365: term = 'Long'
        return b, term, list(ds)[0].strftime('%m/%d/%Y') if len(ds)==1 else 'VARIOUS'

    def export(self):
        yd = OUTPUT_DIR/f"Year_{self.year}"
        if not yd.exists(): yd.mkdir(parents=True)
        if self.tt: pd.DataFrame(self.tt).to_csv(yd/'GENERIC_TAX_CAP_GAINS.csv', index=False)
        if self.inc: pd.DataFrame(self.inc).to_csv(yd/'INCOME_REPORT.csv', index=False)
        
        # --- US LOSS & CARRYOVER ANALYSIS ---
        short_gain = sum([x['Proceeds']-x['Cost Basis'] for x in self.tt if x['Term']=='Short' and (x['Proceeds']-x['Cost Basis'])>0])
        long_gain = sum([x['Proceeds']-x['Cost Basis'] for x in self.tt if x['Term']=='Long' and (x['Proceeds']-x['Cost Basis'])>0])
        
        # Start with Gains, Subtract Losses (Including Carryover)
        net_short = short_gain - self.us_losses['short']
        net_long = long_gain - self.us_losses['long']
        
        # Combine Nets to determine deduction
        total_net = net_short + net_long
        deduction = 0.0
        carryover_short = 0.0
        carryover_long = 0.0
        
        if total_net < 0:
            deduction = min(abs(total_net), 3000.0)
            remaining_loss = abs(total_net) - deduction
            
            # Attribute remaining loss back to Short/Long for next year
            # Logic: Deduction uses Short Term first, then Long Term.
            # (Simplified attribution for CSV reporting)
            if net_short < 0 and net_long < 0:
                # Both lost. Split remaining proportionally or simply?
                # Precise IRS rules are complex. Here we prioritize Short Term carryover.
                carryover_short = remaining_loss if abs(net_short) > remaining_loss else abs(net_short)
                carryover_long = remaining_loss - carryover_short
            elif net_short < 0:
                carryover_short = remaining_loss
            elif net_long < 0:
                carryover_long = remaining_loss

        loss_report = [
            {'Item': 'Prior Year Short-Term Carryover', 'Value': round(self.prior_carryover['short'], 2)},
            {'Item': 'Prior Year Long-Term Carryover', 'Value': round(self.prior_carryover['long'], 2)},
            {'Item': 'Current Year Net Short-Term', 'Value': round(net_short, 2)},
            {'Item': 'Current Year Net Long-Term', 'Value': round(net_long, 2)},
            {'Item': 'Total Net Capital Gain/Loss', 'Value': round(total_net, 2)},
            {'Item': 'Allowable Deduction (Form 1040)', 'Value': round(deduction * -1, 2)},
            {'Item': 'Short-Term Carryover to Next Year', 'Value': round(carryover_short, 2)},
            {'Item': 'Long-Term Carryover to Next Year', 'Value': round(carryover_long, 2)}
        ]
        pd.DataFrame(loss_report).to_csv(yd/'US_TAX_LOSS_ANALYSIS.csv', index=False)
        
        if self.wash_sale_log: pd.DataFrame(self.wash_sale_log).to_csv(yd/'WASH_SALE_REPORT.csv', index=False)

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
    try: set_run_context('direct')
    except: RUN_CONTEXT = 'direct'
    logger.info("--- CRYPTO TAX MASTER V26 (Auto-Carryover) ---")
    initialize_folders()
    try:
        if not KEYS_FILE.exists():
            logger.critical("Missing config. Run 'python Setup.py' first.")
            raise ApiAuthError("Missing keys")
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
        y = input("\nEnter Tax Year: ")
        if y.isdigit():
            eng = TaxEngine(db, y)
            eng.run()
            eng.export()
        db.close()
    except Exception as e:
        logger.exception(f"Error: {e}")
        try: db.close()
        except: pass
        sys.exit(1)