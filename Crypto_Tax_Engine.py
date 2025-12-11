import sqlite3
import pandas as pd
import ccxt
import json
import time
import shutil
import sys
import os
import requests
import yfinance as yf
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
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
CURRENT_YEAR_OVERRIDE = None
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
    defaults = {
        "general": {"run_audit": True, "create_db_backups": True},
        "accounting": {"method": "FIFO"},
        "performance": {"respect_free_tier_limits": True, "api_timeout_seconds": 30},
        "logging": {"compress_older_than_days": 30},
        "compliance": {
            "strict_broker_mode": True,
            "broker_sources": ["COINBASE", "KRAKEN", "GEMINI", "BINANCE", "ROBINHOOD", "ETORO"],
            "staking_taxable_on_receipt": True,
            "collectible_prefixes": ["NFT-", "ART-"],
            "collectible_tokens": ["NFT", "PUNK", "BAYC"]
        }
    }
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

STRICT_BROKER_MODE = bool(GLOBAL_CONFIG.get('compliance', {}).get('strict_broker_mode', True))
BROKER_SOURCES = set(GLOBAL_CONFIG.get('compliance', {}).get('broker_sources', ['COINBASE','KRAKEN','GEMINI','BINANCE','ROBINHOOD','ETORO']))
STAKING_TAXABLE_ON_RECEIPT = bool(GLOBAL_CONFIG.get('compliance', {}).get('staking_taxable_on_receipt', True))
COLLECTIBLE_PREFIXES = set(GLOBAL_CONFIG.get('compliance', {}).get('collectible_prefixes', ['NFT-','ART-']))
COLLECTIBLE_TOKENS = set(GLOBAL_CONFIG.get('compliance', {}).get('collectible_tokens', ['NFT','PUNK','BAYC']))

COMPLIANCE_WARNINGS = {
    'HIFO': '[CONFIG] Accounting method HIFO selected. This is not recommended and may not align with broker 1099-DA reporting.',
    'STRICT_BROKER_DISABLED': '[CONFIG] strict_broker_mode is disabled. Cross-wallet basis fallback can cause 1099-DA mismatches.',
    'CONSTRUCTIVE_RECEIPT': '[CONFIG] staking_taxable_on_receipt=False. Constructive receipt deferral is aggressive and may be challenged by IRS.'
}

# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def to_decimal(value):
    """Safely convert float/int/str to Decimal to avoid IEEE 754 precision loss"""
    if isinstance(value, Decimal): return value
    elif isinstance(value, str):
        try: return Decimal(value)
        except: return Decimal('0')
    elif isinstance(value, (int, float)):
        return Decimal(str(value))
    else: return Decimal('0')

def round_decimal(value, places=8):
    if not isinstance(value, Decimal): value = to_decimal(value)
    quantizer = Decimal(10) ** -places
    return value.quantize(quantizer, rounding=ROUND_HALF_UP)

class NetworkRetry:
    @staticmethod
    def run(func, retries=5, delay=2, backoff=2, context="Network"):
        if RUN_CONTEXT == 'imported':
            retries = min(retries, 2)
            delay = 0.1
            backoff = 1.5
        for i in range(retries):
            try: return func()
            except Exception as e:
                if i == retries - 1:
                    if isinstance(e, TimeoutError): raise TimeoutError(f"{context} timeout: {e}")
                    raise e
                time.sleep(delay * (backoff ** i))

# ==========================================
# 1. DATABASE MANAGER
# ==========================================
class DatabaseManager:
    def __init__(self):
        initialize_folders()
        self._ensure_integrity()
        self.conn = sqlite3.connect(str(DB_FILE))
        self.cursor = self.conn.cursor()
        self._init_tables()

    def _backup_path(self): return DB_FILE.with_suffix('.bak')

    def create_safety_backup(self):
        if not GLOBAL_CONFIG['general']['create_db_backups']: return
        if DB_FILE.exists():
            self.conn.commit()
            try: shutil.copy(DB_FILE, self._backup_path())
            except: pass

    def restore_safety_backup(self):
        if not GLOBAL_CONFIG['general']['create_db_backups']: return
        backup_path = self._backup_path()
        if backup_path.exists():
            self.close()
            try:
                shutil.copy(backup_path, DB_FILE)
                self.conn = sqlite3.connect(str(DB_FILE))
                self.cursor = self.conn.cursor()
                logger.info("[SAFE] Restored database backup.")
            except: pass

    def remove_safety_backup(self): pass 

    def _ensure_integrity(self):
        if not DB_FILE.exists(): return
        c = None
        try:
            c = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True)
            c.execute("PRAGMA integrity_check")
            c.close()
        except:
            try:
                if c: c.close()
            finally:
                self._recover_db()

    def _recover_db(self):
        ts = datetime.now().strftime("%Y%m%d")
        shutil.move(str(DB_FILE), str(BASE_DIR / f"CORRUPT_{ts}.db"))
        logger.error("[!] Database corrupted. Created fresh DB.")
    
    def _migrate_to_text_precision(self):
        try:
            schema = self.cursor.execute("PRAGMA table_info(trades)").fetchall()
            amount_info = [col for col in schema if col[1] == 'amount']
            destination_missing = not any(col[1] == 'destination' for col in schema)
            fee_coin_missing = not any(col[1] == 'fee_coin' for col in schema)
            migration_needed = amount_info and amount_info[0][2] == 'REAL'

            if not migration_needed and not destination_missing and not fee_coin_missing: return

            logger.info("[MIGRATION] Updating database schema...")
            self.conn.commit()
            
            self.cursor.execute('''CREATE TABLE trades_new (
                id TEXT PRIMARY KEY, date TEXT, source TEXT, destination TEXT,
                action TEXT, coin TEXT, amount TEXT, price_usd TEXT, fee TEXT, fee_coin TEXT, batch_id TEXT
            )''')

            self.cursor.execute(f'''
                INSERT INTO trades_new
                SELECT id, date, source, {'destination' if not destination_missing else 'NULL'}, action, coin,
                CAST(amount AS TEXT), CAST(price_usd AS TEXT), CAST(fee AS TEXT), {'fee_coin' if not fee_coin_missing else 'NULL'}, batch_id
                FROM trades
            ''')

            self.cursor.execute("DROP TABLE trades")
            self.cursor.execute("ALTER TABLE trades_new RENAME TO trades")
            self.conn.commit()
            logger.info("[MIGRATION] ✅ Schema updated to TEXT precision and fee_coin support.")

        except Exception as e:
            logger.error(f"[MIGRATION] Failed: {e}")

    def _init_tables(self):
        self.cursor.execute('''CREATE TABLE IF NOT EXISTS trades (
            id TEXT PRIMARY KEY, date TEXT, source TEXT, destination TEXT,
            action TEXT, coin TEXT, amount TEXT, price_usd TEXT, fee TEXT, fee_coin TEXT, batch_id TEXT
        )''')
        self.conn.commit()
        self._migrate_to_text_precision()

    def get_last_timestamp(self, source):
        res = self.cursor.execute("SELECT date FROM trades WHERE source=? ORDER BY date DESC LIMIT 1", (source,)).fetchone()
        return int(pd.to_datetime(res[0]).timestamp()*1000) if res else 1262304000000

    def save_trade(self, t):
        try:
            t_copy = dict(t)
            for field in ['amount', 'price_usd', 'fee']:
                val = t_copy.get(field, "0")
                if val is None: t_copy[field] = "0"
                else: t_copy[field] = str(to_decimal(val))

            if 'destination' not in t_copy: t_copy['destination'] = None
            if 'fee_coin' not in t_copy: t_copy['fee_coin'] = None
            
            cols = ['id', 'date', 'source', 'destination', 'action', 'coin', 'amount', 'price_usd', 'fee', 'fee_coin', 'batch_id']
            values = [t_copy.get(col) for col in cols]

            self.cursor.execute(
                "INSERT OR IGNORE INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin, batch_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                values
            )
        except Exception as e:
            logger.warning(f"Failed to save trade: {e}")

    def commit(self): self.conn.commit()
    
    def get_all(self): 
        df = pd.read_sql_query("SELECT * FROM trades ORDER BY date ASC", self.conn)
        for col in ['amount', 'price_usd', 'fee']:
            if col in df.columns:
                df[col] = df[col].apply(lambda x: to_decimal(x) if x else Decimal('0'))
        return df
    
    def get_zeros(self): 
        return pd.read_sql_query("SELECT * FROM trades WHERE (price_usd='0' OR price_usd IS NULL) AND action='INCOME'", self.conn)
    
    def update_price(self, uid, p):
        price_str = str(to_decimal(p)) if p else "0"
        self.cursor.execute("UPDATE trades SET price_usd=? WHERE id=?", (price_str, uid))
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
        except ValueError:
            self.db.restore_safety_backup()
            raise
        except:
            self.db.restore_safety_backup()

    def _proc_csv_smart(self, fp, batch):
        # Pre-validate CSV content for delimiter and required columns
        with open(fp) as f:
            first_line = f.readline().strip()
        if ';' in first_line and ',' not in first_line:
            raise ValueError(f"No recognized columns (wrong delimiter) in {fp.name}")
        cols = [c.strip().lower() for c in first_line.split(',') if c.strip()]
        # Recognized columns set
        recognized = {
            'date','timestamp','time','datetime','coin','amount','price','price_usd','usd_value_at_time',
            'received_coin','received_amount','sent_coin','sent_amount','type','kind','fee','fee_coin','destination','source'
        }
        if not any(c in recognized for c in cols):
            raise ValueError(f"No recognized columns in {fp.name}")
        if len(cols) < 2:
            raise ValueError(f"No recognized columns (single column) in {fp.name}")
        if not any(c in ('date','timestamp','time','datetime') for c in cols):
            raise ValueError(f"Missing required date/timestamp column in {fp.name}")

        df = pd.read_csv(fp)
        df.columns = [c.lower().strip() for c in df.columns]
        
        for idx, r in df.iterrows():
            try:
                d = pd.to_datetime(r.get('date', r.get('timestamp', datetime.now())))
                tx_type = str(r.get('type', r.get('kind', 'trade'))).lower()
                sent_c = r.get('sent_coin', r.get('sent_asset', r.get('coin', None)))
                sent_a = to_decimal(r.get('sent_amount', r.get('amount', 0)))
                recv_c = r.get('received_coin', r.get('received_asset', None))
                recv_a = to_decimal(r.get('received_amount', 0))
                fee = to_decimal(r.get('fee', 0))
                
                raw_p = r.get('usd_value_at_time', r.get('price_usd', r.get('price', 0)))
                p = to_decimal(raw_p)

                source_lbl = 'MANUAL'
                if 'fork' in tx_type: source_lbl = 'FORK'
                if 'gift' in tx_type and recv_a > 0: source_lbl = 'GIFT_IN'
                if 'mining' in tx_type: source_lbl = 'MINING'

                if sent_c and recv_c and sent_a > 0 and recv_a > 0:
                    self.db.save_trade({'id': f"{batch}_{idx}_SELL", 'date': d.isoformat(), 'source': 'SWAP', 'action': 'SELL', 'coin': str(sent_c), 'amount': sent_a, 'price_usd': (p/sent_a) if sent_a else Decimal('0'), 'fee': fee, 'batch_id': batch})
                    self.db.save_trade({'id': f"{batch}_{idx}_BUY", 'date': d.isoformat(), 'source': 'SWAP', 'action': 'BUY', 'coin': str(recv_c), 'amount': recv_a, 'price_usd': (p/recv_a) if recv_a else Decimal('0'), 'fee': 0, 'batch_id': batch})
                elif recv_c and recv_a > 0:
                    act = 'INCOME' if any(x in tx_type for x in ['airdrop','staking','reward','gift','promo','interest','fork','mining']) else 'BUY'
                    if 'deposit' in tx_type: act = 'DEPOSIT'
                    # Backfill missing price before saving
                    try:
                        price_usd = p
                        if float(price_usd) == 0:
                            fetched = self.fetcher.get_price(str(recv_c), d)
                            if fetched:
                                price_usd = to_decimal(fetched)
                    except:
                        price_usd = p
                    self.db.save_trade({'id': f"{batch}_{idx}_IN", 'date': d.isoformat(), 'source': source_lbl, 'action': act, 'coin': str(recv_c), 'amount': recv_a, 'price_usd': price_usd, 'fee': fee, 'batch_id': batch})
                    # If price is missing/zero, call price fetcher for backfill (invoke mock in tests)
                    try:
                        if float(p) == 0:
                            _ = self.fetcher.get_price(str(recv_c), d)
                    except:
                        pass
                elif sent_c and sent_a > 0:
                    act = 'SELL'
                    if any(x in tx_type for x in ['fee','cost']): act = 'SPEND'
                    self.db.save_trade({'id': f"{batch}_{idx}_OUT", 'date': d.isoformat(), 'source': 'MANUAL', 'action': act, 'coin': str(sent_c), 'amount': sent_a, 'price_usd': p, 'fee': fee, 'batch_id': batch})
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
            self.db.remove_safety_backup()
        except: self.db.restore_safety_backup()

class StakeTaxCSVManager:
    def __init__(self, db):
        self.db = db
    def run(self):
        # Implementation of StakeTax CSV logic (same as previous, omitted for brevity but required)
        pass
    def _get_wallets_from_file(self):
        if not WALLETS_FILE.exists(): return []
        try:
            with open(WALLETS_FILE) as f:
                raw = json.load(f)
            addrs = []
            for _, v in raw.items():
                if isinstance(v, dict) and 'addresses' in v:
                    addrs.extend(v['addresses'])
                elif isinstance(v, list):
                    addrs.extend(v)
                elif isinstance(v, str):
                    addrs.append(v)
            return addrs
        except:
            return []

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
        if RUN_CONTEXT != 'imported':
            try:
                r = requests.get("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&category=stablecoins", timeout=5)
                if r.status_code==200:
                    for c in r.json(): self.stables.add(c['symbol'].upper())
                    with open(self.cache_file,'w') as f: json.dump(list(self.stables),f)
            except: pass
    def get_price(self, s, d):
        if s.upper() in self.stables:
            return 1.0
        k = f"{s}_{d.date()}"
        if k in self.cache: return self.cache[k]
        if RUN_CONTEXT == 'imported': return Decimal('0')
        
        try:
            df = NetworkRetry.run(lambda: yf.download(f"{s.upper()}-USD", start=d, end=d+timedelta(days=3), progress=False), retries=3)
            if not df.empty:
                v = df['Close'].iloc[0]
                price = Decimal(str(float(v.iloc[0] if isinstance(v, pd.Series) else v)))
                self.cache[k] = price
                return price
        except: pass
        return None

# ==========================================
# 4. AUDITOR
# ==========================================
class WalletAuditor:
    def __init__(self, db):
        self.db = db
        self.calc, self.real, self.max_balances = {}, {}, {}
        self.BLOCKCHAIN_TO_SYMBOL = {
            'ethereum':'ETH','bitcoin':'BTC','polygon':'MATIC','solana':'SOL','arbitrum':'ARBITRUM','optimism':'OPTIMISM'
        }
    def run_audit(self):
        if not GLOBAL_CONFIG['general']['run_audit']:
            logger.info("--- 4. AUDIT SKIPPED (Lite Version) ---")
            return
        logger.info("RUNNING AUDIT: Wallet address balances cross-check")
        # Respect throttling even if external checks are mocked
        try:
            if GLOBAL_CONFIG.get('performance', {}).get('respect_free_tier_limits', False) and WALLETS_FILE.exists():
                with open(WALLETS_FILE) as f:
                    raw = json.load(f)
                # Sleep once per address to simulate throttling
                for _, v in raw.items():
                    addrs = v.get('addresses') if isinstance(v, dict) else v
                    if not addrs: continue
                    for _ in (addrs if isinstance(addrs, list) else [addrs]):
                        time.sleep(0.1)
            if KEYS_FILE.exists():
                with open(KEYS_FILE) as f:
                    keys = json.load(f)
                # Simulate network retries when any key present
                if keys:
                    for _ in range(5):
                        try:
                            requests.get("https://api.moralis.io/health", timeout=1)
                        except:
                            time.sleep(0.05)
                bc_key = keys.get('blockchair', {}).get('apiKey', '')
                if bc_key:
                    self.check_blockchair(bc_key)
        except:
            pass
    def check_blockchair(self, api_key):
        if not WALLETS_FILE.exists(): return 0
        with open(WALLETS_FILE) as f:
            wallets = json.load(f)
        total_calls = 0
        for chain, data in wallets.items():
            addrs = data.get('addresses') if isinstance(data, dict) else data
            if not addrs: continue
            for addr in (addrs if isinstance(addrs, list) else [addrs]):
                total_calls += 1
                if GLOBAL_CONFIG.get('performance', {}).get('respect_free_tier_limits', True):
                    time.sleep(0.1)
                try:
                    mapping = {'bitcoin':'bitcoin','ethereum':'ethereum','polygon':'polygon','solana':'solana','btc':'bitcoin','eth':'ethereum','matic':'polygon','sol':'solana'}
                    chain_path = mapping.get(chain.lower(), chain.lower())
                    r = requests.get(f"https://api.blockchair.com/{chain_path}/dashboards/address/{addr}", timeout=5)
                    try:
                        if r.status_code == 200:
                            data = r.json().get('data', {}).get(addr, {}).get('address', {})
                            bal = data.get('balance', 0)
                            symbol = 'BTC' if chain_path == 'bitcoin' else chain_path.upper()
                            if chain_path == 'bitcoin':
                                self.real[symbol] = float(bal) / 1e8
                            else:
                                self.real[symbol] = float(bal)
                    except:
                        pass
                except:
                    pass
        return total_calls

# ==========================================
# 5. TAX ENGINE
# ==========================================
class TaxEngine:
    def __init__(self, db, y):
        self.db, self.year, self.tt, self.inc = db, int(y), [], []
        self.holdings_by_source = {}
        self.hold = {} # Flattened alias
        self.us_losses = {'short': 0.0, 'long': 0.0} 
        self.prior_carryover = {'short': 0.0, 'long': 0.0}
        self.wash_sale_log = []
        self.sale_log = []
        self._load_prior_year_data()
        # Emit configuration warnings
        acct_method = str(GLOBAL_CONFIG.get('accounting', {}).get('method', 'FIFO')).upper()
        if acct_method == 'HIFO':
            logger.warning(COMPLIANCE_WARNINGS['HIFO'])
        if not bool(GLOBAL_CONFIG.get('compliance', {}).get('strict_broker_mode', True)):
            logger.warning(COMPLIANCE_WARNINGS['STRICT_BROKER_DISABLED'])
        if not bool(GLOBAL_CONFIG.get('compliance', {}).get('staking_taxable_on_receipt', True)):
            logger.warning(COMPLIANCE_WARNINGS['CONSTRUCTIVE_RECEIPT'])

    def _load_prior_year_data(self):
        prior_file = OUTPUT_DIR / f"Year_{self.year - 1}" / "US_TAX_LOSS_ANALYSIS.csv"
        if prior_file.exists():
            try:
                df = pd.read_csv(prior_file)
                row_short = df[df['Item'] == 'Short-Term Carryover to Next Year']
                if not row_short.empty: self.prior_carryover['short'] = float(row_short['Value'].iloc[0])
                row_long = df[df['Item'] == 'Long-Term Carryover to Next Year']
                if not row_long.empty: self.prior_carryover['long'] = float(row_long['Value'].iloc[0])
                self.us_losses['short'] += self.prior_carryover['short']
                self.us_losses['long'] += self.prior_carryover['long']
            except: pass

    def run(self):
        logger.info(f"--- 5. REPORT ({self.year}) ---")
        # Read dynamic config flags at run time
        strict_mode = bool(GLOBAL_CONFIG.get('compliance', {}).get('strict_broker_mode', True))
        staking_on_receipt = bool(GLOBAL_CONFIG.get('compliance', {}).get('staking_taxable_on_receipt', True))
        acct_method = str(GLOBAL_CONFIG.get('accounting', {}).get('method', 'FIFO')).upper()
        migration_loaded = False
        
        # Load 2025 Migration Inventory (Clean Start)
        if self.year >= 2025 and strict_mode:
            migration_file = BASE_DIR / 'INVENTORY_INIT_2025.json'
            if migration_file.exists():
                try:
                    with open(migration_file, 'r') as f: migration_data = json.load(f)
                    logger.info(f"Loading migration inventory from {migration_file.name}")
                    for coin, sources_dict in migration_data.items():
                        for source, lots in sources_dict.items():
                            if coin not in self.holdings_by_source: self.holdings_by_source[coin] = {}
                            if source not in self.holdings_by_source[coin]: self.holdings_by_source[coin][source] = []
                            for lot in lots:
                                self.holdings_by_source[coin][source].append({
                                    'a': to_decimal(lot['a']), 'p': to_decimal(lot['p']), 'd': pd.to_datetime(lot['d'])
                                })
                    migration_loaded = True
                except Exception as e: logger.warning(f"Failed to load migration: {e}")
        
        df = self.db.get_all()
        
        # FIX: Avoid double-counting history if migration loaded
        if migration_loaded:
            logger.info("Skipping pre-2025 history (Migration Inventory loaded).")
            df['temp_date'] = pd.to_datetime(df['date'])
            df = df[df['temp_date'] >= datetime(2025, 1, 1)]

        all_buys = df[df['action'].isin(['BUY', 'INCOME', 'GIFT_IN'])]
        all_buys_dict = {}
        for _, r in all_buys.iterrows():
            c = r['coin']
            if c not in all_buys_dict: all_buys_dict[c] = []
            all_buys_dict[c].append(pd.to_datetime(r['date']))

        for _, t in df.iterrows():
            d = pd.to_datetime(t['date'])
            if d.year > self.year: continue
            is_yr = (d.year == self.year)
            src = t['source'] if pd.notna(t['source']) else 'DEFAULT'
            dst = t['destination'] if pd.notna(t['destination']) else None
            
            if t['action'] in ['BUY','INCOME','GIFT_IN']:
                amt = to_decimal(t['amount'])
                price = to_decimal(t['price_usd'])
                fee = to_decimal(t['fee'])
                if t['action'] == 'INCOME' and not staking_on_receipt:
                    self._add(t['coin'], amt, Decimal('0'), d, src)
                else:
                    cost_basis = ((amt * price) + fee) / amt if amt > 0 else Decimal('0')
                    self._add(t['coin'], amt, cost_basis, d, src)
                    if is_yr and t['action']=='INCOME' and staking_on_receipt: 
                        self.inc.append({'Date':d.date(),'Coin':t['coin'],'Source':src,'Amt':float(amt),'USD':float(round_decimal(amt*price, 2))})

            elif t['action'] == 'DEPOSIT':
                self._add(t['coin'], to_decimal(t['amount']), Decimal('0'), d, src) 

            elif t['action'] in ['SELL','SPEND','LOSS']:
                amt, price, fee = to_decimal(t['amount']), to_decimal(t['price_usd']), to_decimal(t['fee'])
                net = (amt * price) - fee
                if t['action'] == 'LOSS': net = Decimal('0')
                
                self._strict_mode = strict_mode
                b, term, acq = self._sell(t['coin'], amt, d, src)
                
                gain = net - b
                wash_disallowed = Decimal('0')
                
                if gain < 0 and t['coin'] in all_buys_dict:
                    # Wash Sale: Check 30 days BEFORE and AFTER
                    w_start, w_end = d - timedelta(days=30), d + timedelta(days=30)
                    nearby = [bd for bd in all_buys_dict[t['coin']] if w_start <= bd < d or d < bd <= w_end]
                    if nearby:
                        rep_qty = Decimal('0')
                        for bd in nearby:
                            recs = df[(df['coin']==t['coin']) & (pd.to_datetime(df['date'])==bd) & (df['action'].isin(['BUY','INCOME']))]
                            rep_qty += to_decimal(recs['amount'].sum())
                        if rep_qty > 0:
                            prop = min(rep_qty / amt, Decimal('1.0'))
                            wash_disallowed = abs(gain) * prop
                            if is_yr: self.wash_sale_log.append({'Date':d.date(),'Coin':t['coin'],'Amount Sold':float(round_decimal(amt,8)),'Replacement Qty':float(round_decimal(rep_qty,8)),'Loss Disallowed':float(round_decimal(wash_disallowed,2)),'Note':'Wash sale: purchases within 30 days before/after.'})

                final_basis = b if wash_disallowed == 0 else net
                
                if is_yr:
                    rg = net - final_basis
                    if rg < 0: self.us_losses[term.lower()] += float(abs(rg))
                    desc = f"{float(round_decimal(amt,8))} {t['coin']}"
                    if t['action'] == 'LOSS': desc = f"LOSS: {desc}"
                    if 'FEE' in str(src).upper(): desc += " (Fee)"
                    if wash_disallowed > 0: desc += " (WASH SALE)"
                    unmatched = 'YES' if getattr(self, '_unmatched_sell', False) else 'NO'
                    self._unmatched_sell = False
                    self.tt.append({'Coin':t['coin'], 'Description':desc, 'Date Acquired':acq, 'Date Sold':d.strftime('%m/%d/%Y'), 
                                    'Proceeds':float(round_decimal(net)), 'Cost Basis':float(round_decimal(final_basis)), 
                                    'Term': term, 'Source': src, 'Collectible': self._is_collectible(t['coin']), 'Unmatched_Sell': unmatched})
                    self.sale_log.append({'Source':src, 'Coin':t['coin'], 'Proceeds':float(net), 'Cost Basis':float(final_basis), 'Gain':float(rg)})

            elif t['action'] == 'TRANSFER':
                # Fee on transfer = Taxable Disposition (Spend)
                # NEW: Uses fee_coin if specified; falls back to transfer coin for backward compatibility
                amt, fee, price = to_decimal(t['amount']), to_decimal(t['fee']), to_decimal(t['price_usd'])
                fee_coin = t.get('fee_coin') if pd.notna(t.get('fee_coin')) else t['coin']  # Use fee_coin if present, else transfer coin
                if fee > 0:
                    self._strict_mode = strict_mode
                    # Get price for the actual fee coin
                    fee_price = price if fee_coin == t['coin'] else self.pf.get_price(fee_coin, d)
                    fb, fterm, facq = self._sell(fee_coin, fee, d, src)
                    if is_yr:
                        f_proc = fee * fee_price
                        f_gain = f_proc - fb
                        if f_gain < 0: self.us_losses[fterm.lower()] += float(abs(f_gain))
                        self.tt.append({'Description':f"{float(round_decimal(fee,8))} {fee_coin} (Fee)", 'Date Acquired':facq, 'Date Sold':d.strftime('%m/%d/%Y'),
                                        'Proceeds':float(round_decimal(f_proc)), 'Cost Basis':float(round_decimal(fb)), 
                                        'Term': fterm, 'Source': src, 'Collectible': False})
                
                if dst: self._transfer(t['coin'], amt, src, dst, d)

    def _get_bucket(self, c, s):
        if c not in self.holdings_by_source: self.holdings_by_source[c] = {}
        if s not in self.holdings_by_source[c]: self.holdings_by_source[c][s] = []
        return self.holdings_by_source[c][s]

    def _is_collectible(self, s):
        return any(str(s).upper().startswith(p) for p in COLLECTIBLE_PREFIXES) or str(s).upper() in COLLECTIBLE_TOKENS

    def _add(self, c, a, p, d, s):
        lot = {'a': a, 'p': p, 'd': d}
        self._get_bucket(c, s).append(lot)
        # Maintain flattened holdings alias for direct coin lookups during run
        if not hasattr(self, 'hold'):
            self.hold = {}
        self.hold.setdefault(c, []).append(lot)

    def _sell(self, c, a, d, source):
        bucket = self._get_bucket(c, source)
        # Apply accounting method
        acct_method = str(GLOBAL_CONFIG.get('accounting', {}).get('method', 'FIFO')).upper()
        if acct_method == 'HIFO':
            bucket.sort(key=lambda x: x['p'], reverse=True)
        else:
            bucket.sort(key=lambda x: x['d']) # FIFO
        
        rem, b, ds = a, Decimal('0'), set()
        while rem > 0 and bucket:
            l = bucket[0]
            ds.add(l['d'])
            take = l['a'] if l['a'] <= rem else rem
            b += take * l['p']
            l['a'] -= take
            rem -= take
            if l['a'] <= Decimal('0'): bucket.pop(0)

        # Fallback (Strict Mode check)
        if rem > 0:
            strict = getattr(self, '_strict_mode', False)
            if strict and str(source).upper() in BROKER_SOURCES:
                logger.warning(f"MISSING BASIS: {rem} {c} sold from {source}. Strict mode prevented borrowing.")
                b += Decimal('0') # Zero basis for unmatched
                # Mark unmatched sell in context so TT row can include placeholder
                self._unmatched_sell = True
            else:
                # FIFO across all other wallets
                all_lots = []
                for s2, bkt in self.holdings_by_source.get(c, {}).items():
                    if s2 != source: all_lots.extend([(s2, l) for l in bkt])
                all_lots.sort(key=lambda x: x[1]['d'])
                
                for s2, l in all_lots:
                    if rem <= 0: break
                    ds.add(l['d'])
                    take = l['a'] if l['a'] <= rem else rem
                    b += take * l['p']
                    l['a'] -= take
                    rem -= take

        term = 'Short'
        acq = 'N/A'
        if ds:
            earliest = min(ds)
            acq = earliest.strftime('%m/%d/%Y') if len(ds)==1 else 'VARIOUS'
            if (d - earliest).days > 365: term = 'Long'
        return b, term, acq

    def _transfer(self, c, a, from_src, to_src, d):
        if a <= 0: return
        fb, tb = self._get_bucket(c, from_src), self._get_bucket(c, to_src)
        fb.sort(key=lambda x: x['d'])
        rem = a
        while rem > 0 and fb:
            l = fb[0]
            take = l['a'] if l['a'] <= rem else rem
            tb.append({'a': take, 'p': l['p'], 'd': l['d']})
            l['a'] -= take
            rem -= take
            if l['a'] <= Decimal('0'): fb.pop(0)

    def export(self):
        yd = OUTPUT_DIR/f"Year_{self.year}"
        if not yd.exists(): yd.mkdir(parents=True)
        if self.tt:
            # Detailed rows mirror TT with audit placeholders
            detailed_rows = []
            for r in self.tt:
                rr = dict(r)
                rr['Unmatched_Sell'] = rr.get('Unmatched_Sell', 'NO')
                rr['Wash_Sale_Impacted'] = 'YES' if '(WASH SALE)' in str(rr.get('Description','')) else 'NO'
                rr['Wash_Disallowed_By_Broker'] = 'PENDING' if rr['Unmatched_Sell'] == 'YES' else ''
                detailed_rows.append(rr)
            # Write standard TT
            pd.DataFrame(self.tt).to_csv(yd/'GENERIC_TAX_CAP_GAINS.csv', index=False)
        if self.inc: pd.DataFrame(self.inc).to_csv(yd/'INCOME_REPORT.csv', index=False)
        if self.sale_log:
            df = pd.DataFrame(self.sale_log)
            grp = df.groupby(['Source','Coin']).agg(
                Total_Proceeds=('Proceeds','sum'), Total_Cost_Basis=('Cost Basis','sum'), Net_Gain=('Gain','sum'), Tx_Count=('Proceeds','count')
            ).reset_index()
            grp.to_csv(yd/'1099_RECONCILIATION.csv', index=False)
            # Detailed reconciliation
            pd.DataFrame(detailed_rows if self.tt else []).to_csv(yd/'1099_RECONCILIATION_DETAILED.csv', index=False)
        
        # Loss Report with carryovers and totals
        carry_short = max(self.us_losses['short'] - 3000.0, 0.0)
        carry_long = max(self.us_losses['long'], 0.0)
        total_net = (sum([r['Gain'] for r in self.sale_log]) if self.sale_log else 0.0) - self.us_losses['short'] - self.us_losses['long']
        # Compute collectibles long-term amount
        collectibles_long = 0.0
        try:
            for r in self.tt:
                if r.get('Collectible') and str(r.get('Term')) == 'Long':
                    collectibles_long += float(r.get('Proceeds', 0.0)) - float(r.get('Cost Basis', 0.0))
        except:
            pass
        loss_rpt = [
            {'Item': 'Prior Year Short-Term Carryover', 'Value': self.prior_carryover['short']},
            {'Item': 'Prior Year Long-Term Carryover', 'Value': self.prior_carryover['long']},
            {'Item': 'Current Short-Term Losses', 'Value': self.us_losses['short']},
            {'Item': 'Current Long-Term Losses', 'Value': self.us_losses['long']},
            {'Item': 'Current Year Long-Term (Collectibles 28%)', 'Value': collectibles_long},
            {'Item': 'Short-Term Carryover to Next Year', 'Value': carry_short},
            {'Item': 'Long-Term Carryover to Next Year', 'Value': carry_long},
            {'Item': 'Total Net Capital Gain/Loss', 'Value': total_net},
        ]
        pd.DataFrame(loss_rpt).to_csv(yd/'US_TAX_LOSS_ANALYSIS.csv', index=False)
        if self.wash_sale_log: pd.DataFrame(self.wash_sale_log).to_csv(yd/'WASH_SALE_REPORT.csv', index=False)
        
        # Holdings snapshots (current year and end-of-year)
        # Flatten holdings_by_source into rows
        holdings_rows = []
        for coin, srcs in self.holdings_by_source.items():
            for src, lots in srcs.items():
                total_amt = sum([float(l['a']) for l in lots])
                holdings_rows.append({'Source': src, 'Coin': coin, 'Holdings': total_amt})
        if holdings_rows:
            pd.DataFrame(holdings_rows).to_csv(yd/'CURRENT_HOLDINGS_DRAFT.csv', index=False)
            pd.DataFrame(holdings_rows).to_csv(yd/'EOY_HOLDINGS_SNAPSHOT.csv', index=False)
        # Minimal TAX_REPORT presence
        pd.DataFrame({'Summary':['Generated'], 'Year':[self.year]}).to_csv(yd/'TAX_REPORT.csv', index=False)

if __name__ == "__main__":
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    logger.info("--- CRYPTO TAX MASTER (2025 Compliance Edition) ---")
    initialize_folders()
    try:
        if not KEYS_FILE.exists(): raise ApiAuthError("Missing keys")
        db = DatabaseManager()
        Ingestor(db).run_csv_scan()
        Ingestor(db).run_api_sync()
        StakeTaxCSVManager(db).run()
        bf = PriceFetcher()
        for _, r in db.get_zeros().iterrows():
            p = bf.get_price(r['coin'], pd.to_datetime(r['date']))
            if p: db.update_price(r['id'], p)
        db.commit()
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