#!/usr/bin/env python3
"""
================================================================================
CLI - Command Line Interface
================================================================================

Provides unified command-line access to all tracker features:
    - Transaction processing and report generation
    - Setup and configuration management
    - Database backup/restore operations
    - Web UI launcher
    - Review and fix workflows

Features:
    - Rich text formatting with ANSI colors
    - Argument parsing for all major operations
    - Progress indicators and status updates
    - Error handling with user-friendly messages

Usage:
    python cli.py [command] [options]
    python cli.py --help

Author: Crypto Transaction Tracker Team
Last Modified: December 2025
================================================================================
"""

import sys
import argparse
import subprocess
import json
import io
import zipfile
import shutil
import tempfile
import uuid
import csv
import sqlite3
import os
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from getpass import getpass

from src.utils.constants import (
    BASE_DIR as CONST_BASE_DIR,
    INPUT_DIR,
    OUTPUT_DIR,
    CONFIG_FILE,
    DB_FILE,
    API_KEYS_ENCRYPTED_FILE,
    WALLETS_ENCRYPTED_FILE,
    API_KEYS_FILE,
    WALLETS_FILE,
)
from src.core.encryption import (
    load_api_keys_file,
    save_api_keys_file,
    load_wallets_file,
    save_wallets_file,
    DatabaseEncryption,
)
from src.web.scheduler import ScheduleManager
from src.web import server as web_server

# Check ToS acceptance
from src.utils.tos_checker import check_and_prompt_tos
check_and_prompt_tos()

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


PROJECT_ROOT = Path(__file__).resolve().parent
BASE_DIR = CONST_BASE_DIR if CONST_BASE_DIR.exists() else PROJECT_ROOT


def _pretty_json(payload: Any):
    """Render JSON to stdout with stable formatting."""
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _require_file(path: Path, label: str) -> Optional[Path]:
    """Validate a file exists and return it; emit friendly error otherwise."""
    resolved = path if path.is_absolute() else BASE_DIR / path
    if resolved.exists():
        return resolved
    print_error(f"{label} not found at {resolved}")
    return None


def _write_bytes_to_path(data: bytes, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, 'wb') as f:
        f.write(data)
    return dest


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _save_json(path: Path, data: Dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def _mark_data_changed_safely():
    """Notify the engine that on-disk data changed, ignoring soft failures."""
    try:
        web_server.txn_app.mark_data_changed()
    except Exception:
        pass

def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text:^70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.ENDC}\n")

def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓{Colors.ENDC} {text}")

def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗{Colors.ENDC} {text}")

def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ{Colors.ENDC} {text}")

def run_python_script(script_name, *args):
    """Run a Python script with arguments"""
    # Map script names to their new locations
    script_map = {
        'setup.py': 'src/tools/setup.py',
        'auto_runner.py': 'Auto_Runner.py',
        'review_fixer.py': 'src/tools/review_fixer.py',
        'start_web_ui.py': 'start_web_ui.py'
    }
    
    script_path = Path(__file__).parent / script_map.get(script_name, script_name)
    if not script_path.exists():
        print_error(f"Script not found: {script_name}")
        return False
    
    try:
        result = subprocess.run([sys.executable, str(script_path)] + list(args), check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print_error(f"Script failed with exit code {e.returncode}")
        return False
    except KeyboardInterrupt:
        print_info("Interrupted by user")
        return False

def cmd_setup(args):
    """Run initial setup wizard"""
    print_header("INITIAL SETUP")
    print_info("Initializing folders and configuration files...")
    return run_python_script('setup.py')

def cmd_run(args):
    """Process transactions"""
    print_header("TRANSACTION PROCESSING")
    
    # Check for cascade mode
    script_args = []
    if args.cascade:
        print_info("Running in CASCADE mode (includes all years)")
        script_args.append('--cascade')
    else:
        current_year = datetime.now().year
        print_info(f"Running for current year: {current_year}")
    
    return run_python_script('auto_runner.py', *script_args)

def cmd_review(args):
    """Run manual review assistant"""
    print_header("MANUAL REVIEW ASSISTANT")
    
    # Get year
    year = args.year if args.year else str(datetime.now().year)
    print_info(f"Reviewing activity year: {year}")
    
    return run_python_script('review_fixer.py', year)

def cmd_web(args):
    """Start web UI"""
    print_header("WEB UI SERVER")
    print_info("Starting web interface at https://localhost:5000")
    print_info("Press Ctrl+C to stop the server\n")
    
    return run_python_script('start_web_ui.py')

def cmd_test(args):
    """Run test suite"""
    print_header("TEST SUITE")
    
    if args.file:
        print_info(f"Running specific test: {args.file}")
        test_path = Path(__file__).parent / 'tests' / args.file
        if not test_path.exists():
            print_error(f"Test file not found: {args.file}")
            return False
        
        try:
            result = subprocess.run([sys.executable, '-m', 'pytest', str(test_path), '-v'], check=True)
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False
    else:
        print_info("Running full test suite...")
        try:
            result = subprocess.run([sys.executable, '-m', 'pytest', 'tests/', '-v'], check=True)
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False

def cmd_info(args):
    """Display system information"""
    print_header("SYSTEM INFORMATION")
    
    # Load constants for paths
    try:
        from src.utils.constants import (
            BASE_DIR, DB_FILE, CONFIG_FILE, STATUS_FILE, 
            INPUT_DIR, OUTPUT_DIR, API_KEYS_ENCRYPTED_FILE
        )
        from src.utils.config import load_config, get_status
        
        print(f"{Colors.BOLD}Paths:{Colors.ENDC}")
        print(f"  Base Directory:  {BASE_DIR}")
        print(f"  Database:        {DB_FILE} {'✓' if DB_FILE.exists() else '✗'}")
        print(f"  Config:          {CONFIG_FILE} {'✓' if CONFIG_FILE.exists() else '✗'}")
        print(f"  API Keys:        {API_KEYS_ENCRYPTED_FILE} {'✓' if API_KEYS_ENCRYPTED_FILE.exists() else '✗'}")
        print(f"  Input Folder:    {INPUT_DIR} ({len(list(INPUT_DIR.glob('*.csv'))) if INPUT_DIR.exists() else 0} CSVs)")
        
        # Try to load config
        try:
            config = load_config()
            status = get_status()
            
            print(f"\n{Colors.BOLD}Configuration:{Colors.ENDC}")
            print(f"  Accounting:      {config.get('accounting', {}).get('method', 'FIFO')}")
            print(f"  Audit Enabled:   {config.get('general', {}).get('run_audit', True)}")
            print(f"  Backups:         {config.get('general', {}).get('create_db_backups', True)}")
            
            print(f"\n{Colors.BOLD}Status:{Colors.ENDC}")
            print(f"  Last Run:        {status.get('last_run', 'Never')}")
            print(f"  Processing Year: {status.get('processing_year', 'Not set')}")
            
        except Exception as e:
            print(f"\n{Colors.YELLOW}⚠{Colors.ENDC} Could not load configuration: {e}")
        
        print_success("System information displayed")
        return True
        
    except Exception as e:
        print_error(f"Could not load system information: {e}")
        return False

def cmd_export(args):
    """Export reports to specified format"""
    print_header("EXPORT REPORTS")
    
    year = args.year if args.year else str(datetime.now().year)
    output_dir = Path(__file__).parent / 'outputs' / f'Year_{year}'
    
    if not output_dir.exists():
        print_error(f"No reports found for year {year}")
        print_info(f"Expected location: {output_dir}")
        return False
    
    # List available reports
    reports = list(output_dir.glob('*.csv'))
    if not reports:
        print_error("No CSV reports found")
        return False
    
    print_success(f"Found {len(reports)} report(s) for year {year}:")
    for report in reports:
        print(f"  • {report.name}")
    
    print_info(f"Reports location: {output_dir}")
    return True


# ==================================
# TRANSACTION MANAGEMENT
# ==================================

def cmd_tx_list(args):
    filters = {}
    if args.coin:
        filters['coin'] = args.coin
    if args.action:
        filters['action'] = args.action
    if args.source:
        filters['source'] = args.source

    result = web_server.get_transactions(
        page=args.page,
        per_page=args.per_page,
        search=args.search,
        filters=filters or None,
    )
    _pretty_json(result)
    return True


def cmd_tx_add(args):
    conn = web_server.get_db_connection()
    tx_id = str(uuid.uuid4())
    try:
        conn.execute(
            """
            INSERT INTO trades (id, date, source, destination, action, coin, amount, price_usd, fee, fee_coin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx_id,
                args.date,
                args.source or 'Manual',
                args.destination or '',
                args.action,
                args.coin,
                args.amount,
                args.price_usd or 0,
                args.fee or 0,
                args.fee_coin or '',
            ),
        )
        conn.commit()
        print_success(f"Transaction created with id {tx_id}")
        _mark_data_changed_safely()
        return True
    except Exception as e:
        print_error(f"Could not create transaction: {e}")
        return False
    finally:
        conn.close()


def cmd_tx_update(args):
    conn = web_server.get_db_connection()
    updates = {}
    for field in ['date', 'source', 'destination', 'action', 'coin', 'amount', 'price_usd', 'fee', 'fee_coin']:
        value = getattr(args, field, None)
        if value is not None:
            updates[field] = value

    if not updates:
        print_error("No fields provided to update")
        return False

    try:
        sets = ", ".join([f"{k} = ?" for k in updates])
        params = list(updates.values()) + [args.id]
        conn.execute(f"UPDATE trades SET {sets} WHERE id = ?", params)
        conn.commit()
        print_success(f"Transaction {args.id} updated")
        _mark_data_changed_safely()
        return True
    except Exception as e:
        print_error(f"Could not update transaction: {e}")
        return False
    finally:
        conn.close()


def cmd_tx_delete(args):
    conn = web_server.get_db_connection()
    try:
        conn.execute("DELETE FROM trades WHERE id = ?", (args.id,))
        conn.commit()
        print_success(f"Transaction {args.id} deleted")
        _mark_data_changed_safely()
        return True
    except Exception as e:
        print_error(f"Could not delete transaction: {e}")
        return False
    finally:
        conn.close()


def cmd_tx_upload(args):
    csv_path = _require_file(Path(args.file), "CSV file")
    if not csv_path:
        return False

    summary = web_server._ingest_csv_with_engine(csv_path)
    _mark_data_changed_safely()
    print_success(f"Imported {summary.get('new_trades', 0)} trades from {csv_path.name}")
    _pretty_json(summary)
    return True


def cmd_tx_template(args):
    headers = ['date','type','received_coin','received_amount','sent_coin','sent_amount','price_usd','fee','fee_coin','destination','source']
    sample_rows = [
        ['2024-01-01T12:00:00Z','trade','BTC','0.001','','','42000','0','','','MANUAL'],
        ['2024-01-02T08:00:00Z','staking','ETH','0.01','','','0','0','','','MANUAL'],
    ]
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(sample_rows)
    dest = Path(args.output or f"transactions_template_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    _write_bytes_to_path(buf.getvalue().encode('utf-8'), dest)
    print_success(f"Template written to {dest}")
    return True


def cmd_tx_reprocess(args):
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        ml_config = config.get('ml_fallback', {})
        if not ml_config.get('enabled', False):
            print_error('ML fallback is not enabled. Enable it in settings first.')
            return False

        conn = web_server.get_db_connection()
        cursor = conn.execute("SELECT * FROM trades ORDER BY date ASC")
        transactions = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if not transactions:
            print_info('No transactions to reprocess')
            return True

        from src.ml_service import MLService
        from src.rules_model_bridge import classify_rules_ml

        ml_service = MLService(mode=ml_config.get('model_name', 'shim'))
        batch_size = max(1, ml_config.get('batch_size', args.batch_size or 10))
        processed_count = 0
        updated_count = 0

        log_dir = OUTPUT_DIR / 'logs'
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'model_suggestions.log'

        for batch_start in range(0, len(transactions), batch_size):
            batch = transactions[batch_start: batch_start + batch_size]
            for tx in batch:
                try:
                    row = {
                        'description': f"{tx.get('action', '')} {tx.get('coin', '')}",
                        'amount': tx.get('amount', 0),
                        'price_usd': tx.get('price_usd', 0),
                        'coin': tx.get('coin', ''),
                        'action': tx.get('action', ''),
                        'source': tx.get('source', ''),
                        'date': tx.get('date', ''),
                    }
                    result = classify_rules_ml(row, ml_service)
                    processed_count += 1
                    if result.get('source') == 'ml' and result.get('label'):
                        current_action = tx.get('action', '')
                        new_action = result['label']
                        if current_action != new_action:
                            conn_u = web_server.get_db_connection()
                            conn_u.execute("UPDATE trades SET action = ? WHERE id = ?", (new_action, tx['id']))
                            conn_u.commit()
                            conn_u.close()
                            updated_count += 1
                        with open(log_file, 'a') as f:
                            f.write(json.dumps({
                                'timestamp': datetime.now().isoformat(),
                                'transaction_id': tx['id'],
                                'date': tx.get('date', ''),
                                'coin': tx.get('coin', ''),
                                'original_action': current_action,
                                'suggested_action': result.get('label'),
                                'confidence': result.get('confidence', 0),
                                'explanation': result.get('explanation', ''),
                            }) + '\n')
                except Exception as tx_error:
                    print_error(f"Error processing transaction {tx.get('id')}: {tx_error}")

        if ml_config.get('auto_shutdown_after_batch', True):
            try:
                ml_service.shutdown()
            except Exception:
                pass

        _mark_data_changed_safely()
        print_success(f"Reprocessing complete. Analyzed {processed_count}, updated {updated_count}.")
        return True
    except Exception as e:
        print_error(f"Reprocess failed: {e}")
        return False


# ==================================
# REPORTS, WARNINGS, STATS
# ==================================

def cmd_reports_list(args):
    reports = []
    if OUTPUT_DIR.exists():
        year_folders = [f for f in OUTPUT_DIR.iterdir() if f.is_dir() and f.name.startswith('Year_')]
        for year_folder in sorted(year_folders, key=lambda x: x.name, reverse=True):
            year = year_folder.name.replace('Year_', '')
            year_reports = []
            for report_file in year_folder.glob('*.csv'):
                year_reports.append({
                    'name': report_file.name,
                    'path': str(report_file.relative_to(BASE_DIR)).replace('\\', '/'),
                    'size': report_file.stat().st_size,
                    'modified': datetime.fromtimestamp(report_file.stat().st_mtime).isoformat(),
                })
            if year_reports:
                reports.append({'year': year, 'reports': year_reports})
    _pretty_json(reports)
    return True


def cmd_reports_download(args):
    report_path = Path(args.path)
    target = _require_file(BASE_DIR / report_path, "Report")
    if not target:
        return False
    dest = Path(args.output or target.name)
    shutil.copy2(target, dest)
    print_success(f"Report copied to {dest}")
    return True


def cmd_warnings(args):
    warnings_file = None
    suggestions_file = None
    if OUTPUT_DIR.exists():
        year_folders = [f for f in OUTPUT_DIR.iterdir() if f.is_dir() and f.name.startswith('Year_')]
        if year_folders:
            latest_year = max(year_folders, key=lambda x: x.name)
            warnings_file = latest_year / 'REVIEW_WARNINGS.csv'
            suggestions_file = latest_year / 'REVIEW_SUGGESTIONS.csv'

    result = {'warnings': [], 'suggestions': []}
    try:
        if warnings_file and warnings_file.exists():
            import pandas as pd  # noqa: F401
            df = pd.read_csv(warnings_file)
            result['warnings'] = df.to_dict('records')
    except Exception:
        if warnings_file and warnings_file.exists():
            with open(warnings_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                result['warnings'] = list(reader)

    try:
        if suggestions_file and suggestions_file.exists():
            import pandas as pd  # noqa: F401
            df = pd.read_csv(suggestions_file)
            result['suggestions'] = df.to_dict('records')
    except Exception:
        if suggestions_file and suggestions_file.exists():
            with open(suggestions_file, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                result['suggestions'] = list(reader)

    _pretty_json(result)
    return True


def cmd_stats(args):
    try:
        conn = web_server.get_db_connection()
        total_transactions = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
        actions = {row['action']: row['count'] for row in conn.execute("SELECT action, COUNT(*) as count FROM trades GROUP BY action")}
        coins = {row['coin']: row['count'] for row in conn.execute("SELECT coin, COUNT(*) as count FROM trades GROUP BY coin ORDER BY count DESC LIMIT 10")}
        date_range = conn.execute("SELECT MIN(date) as min_date, MAX(date) as max_date FROM trades").fetchone()
        conn.close()

        gains_losses = None
        if OUTPUT_DIR.exists():
            year_folders = [f for f in OUTPUT_DIR.iterdir() if f.is_dir() and f.name.startswith('Year_')]
            if year_folders:
                latest_year = max(year_folders, key=lambda x: x.name)
                loss_analysis_file = latest_year / 'US_transaction_LOSS_ANALYSIS.csv'
                if loss_analysis_file.exists():
                    import pandas as pd  # noqa: F401
                    df = pd.read_csv(loss_analysis_file)
                    if not df.empty:
                        gains_losses = df.to_dict('records')[0]

        result = {
            'total_transactions': total_transactions,
            'actions': actions,
            'top_coins': coins,
            'date_range': {'min': date_range['min_date'], 'max': date_range['max_date']},
            'gains_losses': gains_losses,
        }
        _pretty_json(result)
        return True
    except Exception as e:
        print_error(f"Could not compute stats: {e}")
        return False


# ==================================
# CONFIG, WALLETS, API KEYS
# ==================================

def cmd_config_show(args):
    if not CONFIG_FILE.exists():
        print_error("config.json not found. Run setup first.")
        return False
    data = _load_json(CONFIG_FILE)
    _pretty_json(data)
    return True


def cmd_config_set(args):
    if not args.file:
        print_error("Provide --file with a JSON payload to save the full config")
        return False
    cfg_path = _require_file(Path(args.file), "Config file")
    if not cfg_path:
        return False
    data = _load_json(cfg_path)
    _save_json(CONFIG_FILE, data)
    print_success(f"Configuration updated from {cfg_path}")
    return True


def cmd_wallets_show(args):
    wallets = load_wallets_file()
    _pretty_json(wallets)
    return True


def cmd_wallets_save(args):
    wallet_path = _require_file(Path(args.file), "Wallet JSON")
    if not wallet_path:
        return False
    wallets = _load_json(wallet_path)
    save_wallets_file(wallets)
    print_success("Wallets saved")
    return True


def cmd_wallets_test(args):
    from src.web.wallet_linker import WalletLinker
    wallets = load_wallets_file()
    linker = WalletLinker(wallets)
    match = linker.find_matching_wallet(args.source, args.address)
    if match:
        print_success("Matched wallet")
        _pretty_json(match)
    else:
        print_info("No exact match found; showing possible matches")
        _pretty_json(linker.get_possible_wallets_for_source(args.source))
    return True


def cmd_api_keys_show(args):
    keys = load_api_keys_file()
    for exchange, values in keys.items():
        if isinstance(values, dict):
            for key, value in values.items():
                if key in ['apiKey', 'secret', 'password'] and value and len(value) > 8 and not value.startswith('PASTE_'):
                    keys[exchange][key] = value[:4] + '*' * (len(value) - 8) + value[-4:]
    _pretty_json(keys)
    return True


def cmd_api_keys_save(args):
    key_path = _require_file(Path(args.file), "API keys JSON")
    if not key_path:
        return False
    new_keys = _load_json(key_path)
    existing = load_api_keys_file()
    for exchange, values in new_keys.items():
        if exchange not in existing:
            existing[exchange] = {}
        if isinstance(values, dict):
            for key, value in values.items():
                if value and '*' not in value:
                    existing[exchange][key] = value
    save_api_keys_file(existing)
    print_success("API keys saved")
    return True


def cmd_api_keys_test(args):
    try:
        import ccxt
    except ImportError:
        print_error("ccxt not installed. Install it to test API keys.")
        return False

    exchange = args.exchange.lower()
    if not hasattr(ccxt, exchange):
        print_error(f"Exchange '{exchange}' not supported")
        return False

    try:
        exchange_class = getattr(ccxt, exchange)
        exchange_obj = exchange_class({
            'apiKey': args.apiKey.strip(),
            'secret': args.secret.strip(),
            'enableRateLimit': True,
            'timeout': 10000,
        })
        exchange_obj.fetch_balance()
        print_success(f"{exchange.capitalize()} API key is valid")
        return True
    except ccxt.AuthenticationError as e:
        print_error(f"Authentication failed: {e}")
    except ccxt.NetworkError as e:
        print_error(f"Network error: {e}")
    except Exception as e:
        print_error(f"Test failed: {e}")
    return False


# ==================================
# BACKUP & RESTORE
# ==================================

def _build_full_backup_bytes() -> bytes:
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        conn = web_server.get_db_connection()
        try:
            cursor = conn.execute("SELECT * FROM trades")
            rows = cursor.fetchall()
            if cursor.description:
                column_names = [description[0] for description in cursor.description]
                csv_buffer = io.StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow(column_names)
                writer.writerows(rows)
                zf.writestr('trades_export.csv', csv_buffer.getvalue())
            else:
                zf.writestr('trades_export.csv', 'No data found')
        finally:
            conn.close()
    memory_file.seek(0)
    return memory_file.getvalue()


def cmd_backup_full(args):
    data = _build_full_backup_bytes()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = Path(args.output or f'crypto_transaction_db_export_{timestamp}.zip')
    _write_bytes_to_path(data, dest)
    print_success(f"Full backup written to {dest}")
    return True


def _build_zip_backup_bytes(db_key: Optional[bytes] = None) -> Tuple[bytes, str]:
    raw_zip = io.BytesIO()
    with zipfile.ZipFile(raw_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        manifest = {'created': datetime.now().isoformat(), 'version': '1.0', 'includes': []}

        def add_file(path: Path, arcname: str):
            if path.exists():
                zf.write(str(path), arcname)
                manifest['includes'].append(arcname)

        add_file(DB_FILE, 'crypto_master.db')
        add_file(BASE_DIR / '.db_key', '.db_key')
        add_file(BASE_DIR / '.db_salt', '.db_salt')
        add_file(CONFIG_FILE, 'config.json')
        add_file(API_KEYS_ENCRYPTED_FILE, 'api_keys_encrypted.json')
        if 'api_keys_encrypted.json' not in manifest['includes']:
            add_file(API_KEYS_FILE, 'api_keys.json')
        add_file(WALLETS_ENCRYPTED_FILE, 'wallets_encrypted.json')
        if 'wallets_encrypted.json' not in manifest['includes']:
            add_file(WALLETS_FILE, 'wallets.json')
        add_file(BASE_DIR / 'keys' / 'web_users.json', 'web_users.json')
        zf.writestr('manifest.json', json.dumps(manifest, indent=2))

    raw_zip.seek(0)
    if db_key:
        cipher = web_server.Fernet(db_key)
        return cipher.encrypt(raw_zip.getvalue()), 'enc'
    return raw_zip.getvalue(), 'zip'


def cmd_backup_zip(args):
    db_key = web_server.app.config.get('DB_ENCRYPTION_KEY')
    data, ext = _build_zip_backup_bytes(db_key)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = Path(args.output or f'backup_{timestamp}.zip{".enc" if ext == "enc" else ""}')
    _write_bytes_to_path(data, dest)
    print_success(f"Backup written to {dest}")
    return True


def cmd_restore_backup(args):
    backup_path = _require_file(Path(args.file), "Backup")
    if not backup_path:
        return False

    data = backup_path.read_bytes()
    filename = backup_path.name.lower()

    if filename.endswith('.enc'):
        password = args.password or getpass('Backup password: ')
        if not password:
            print_error('Password required for encrypted backup')
            return False
        try:
            if (BASE_DIR / '.db_key').exists() and (BASE_DIR / '.db_salt').exists():
                with open(BASE_DIR / '.db_key', 'rb') as f:
                    enc_key = f.read()
                with open(BASE_DIR / '.db_salt', 'rb') as f:
                    salt = f.read()
                db_key_bytes = DatabaseEncryption.decrypt_key(enc_key, password, salt)
            else:
                print_error('Key files not found to decrypt backup')
                return False
            cipher = web_server.Fernet(db_key_bytes)
            data = cipher.decrypt(data)
        except Exception as e:
            print_error(f"Failed to decrypt backup: {e}")
            return False

    tmp_mem = io.BytesIO(data)
    try:
        with zipfile.ZipFile(tmp_mem, 'r') as zf:
            members = zf.namelist()

            def restore_member(name: str, target: Path):
                if name in members:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(name) as src, open(target, 'wb') as dst:
                        shutil.copyfileobj(src, dst)

            mode = args.mode.lower()
            if 'crypto_master.db' in members:
                if mode == 'merge':
                    fallback_to_replace = False
                    tmpdb_path = None
                    try:
                        conn_init = sqlite3.connect(str(DB_FILE))
                        cur_init = conn_init.cursor()
                        cur_init.execute("""
                            CREATE TABLE IF NOT EXISTS trades (
                                id TEXT PRIMARY KEY,
                                date TEXT,
                                source TEXT,
                                destination TEXT,
                                action TEXT,
                                coin TEXT,
                                amount TEXT,
                                price_usd TEXT,
                                fee TEXT,
                                fee_coin TEXT,
                                batch_id TEXT
                            )
                        """)
                        conn_init.commit()
                    except Exception:
                        fallback_to_replace = True
                    finally:
                        try:
                            conn_init.close()
                        except Exception:
                            pass
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmpdb:
                            with zf.open('crypto_master.db') as src:
                                shutil.copyfileobj(src, tmpdb)
                            tmpdb_path = Path(tmpdb.name)
                        conn = None
                        try:
                            conn = sqlite3.connect(str(DB_FILE))
                            cur = conn.cursor()
                            cur.execute("ATTACH DATABASE ? AS olddb", (str(tmpdb_path),))
                            has_trades = cur.execute("SELECT name FROM olddb.sqlite_master WHERE type='table' AND name='trades'").fetchone()
                            if has_trades:
                                old_cols = [r[1] for r in cur.execute("PRAGMA olddb.table_info(trades)").fetchall()]
                                target_cols = ['id','date','source','destination','action','coin','amount','price_usd','fee','fee_coin','batch_id']
                                select_exprs = [f"olddb.trades.{c}" if c in old_cols else f"NULL AS {c}" for c in target_cols]
                                insert_cols = ",".join(target_cols)
                                select_sql = ", ".join(select_exprs)
                                cur.execute(f"INSERT OR IGNORE INTO trades ({insert_cols}) SELECT {select_sql} FROM olddb.trades")
                                conn.commit()
                        except Exception:
                            fallback_to_replace = True
                        finally:
                            try:
                                if conn:
                                    conn.execute("DETACH DATABASE olddb")
                            except Exception:
                                pass
                            if conn:
                                conn.close()
                    finally:
                        try:
                            if tmpdb_path:
                                tmpdb_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                    if fallback_to_replace:
                        restore_member('crypto_master.db', DB_FILE)
                else:
                    restore_member('crypto_master.db', DB_FILE)

            restore_member('config.json', CONFIG_FILE)
            restore_member('api_keys_encrypted.json', API_KEYS_ENCRYPTED_FILE)
            restore_member('api_keys.json', API_KEYS_FILE)
            restore_member('wallets_encrypted.json', WALLETS_ENCRYPTED_FILE)
            restore_member('wallets.json', WALLETS_FILE)
            restore_member('web_users.json', BASE_DIR / 'keys' / 'web_users.json')

        print_success("Backup restored")
        _mark_data_changed_safely()
        return True
    except Exception as e:
        print_error(f"Restore failed: {e}")
        return False


# ==================================
# LOGS
# ==================================

def cmd_logs_list(args):
    logs = []
    log_dir = OUTPUT_DIR / 'logs'
    if log_dir.exists():
        for log_file in sorted(log_dir.glob('*.log'), key=lambda x: x.stat().st_mtime, reverse=True):
            logs.append({
                'name': log_file.name,
                'path': str(log_file),
                'size': log_file.stat().st_size,
                'modified': datetime.fromtimestamp(log_file.stat().st_mtime).isoformat(),
            })
    _pretty_json(logs)
    return True


def cmd_logs_download(args):
    log_path = _require_file(Path(args.name), "Log file")
    if not log_path:
        return False
    dest = Path(args.output or log_path.name)
    shutil.copy2(log_path, dest)
    print_success(f"Log copied to {dest}")
    return True


def cmd_logs_download_all(args):
    log_dir = OUTPUT_DIR / 'logs'
    if not log_dir.exists():
        print_error("No logs directory found")
        return False
    mem_zip = io.BytesIO()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    with zipfile.ZipFile(mem_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for log_file in log_dir.glob('*.log'):
            zf.write(log_file, arcname=log_file.name)
    mem_zip.seek(0)
    dest = Path(args.output or f'all_logs_{timestamp}.zip')
    _write_bytes_to_path(mem_zip.getvalue(), dest)
    print_success(f"Logs archived to {dest}")
    return True


def cmd_logs_download_redacted(args):
    log_dir = OUTPUT_DIR / 'logs'
    if not log_dir.exists():
        print_error("No logs directory found")
        return False
    import re
    redaction_patterns = [
        (r'\b[a-fA-F0-9]{64,}\b', '[PRIVATE_KEY_REDACTED]'),
        (r'\b(sk_live_[a-zA-Z0-9]{10,})\b', '[REDACTED_SECRET_KEY]'),
        (r'\b(sk_test_[a-zA-Z0-9]{10,})\b', '[REDACTED_TEST_KEY]'),
        (r'\b(sk_[a-zA-Z0-9]{10,})\b', '[REDACTED_SECRET_KEY]'),
        (r'\b(0x[a-fA-F0-9]{40})\b', '[WALLET_ADDRESS]'),
        (r'\b(bc1[a-z0-9]{39,59})\b', '[WALLET_ADDRESS]'),
        (r'\b([13][a-km-zA-HJ-NP-Z1-9]{25,34})\b', '[WALLET_ADDRESS]'),
        (r'\b([a-zA-Z0-9_\-]{32,})\b', '[REDACTED_API_KEY]'),
        (r'(["\']?api[_-]?key["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]{16,})', r'\1[REDACTED_API_KEY]'),
        (r'(["\']?secret["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-/+=]{16,})', r'\1[REDACTED_SECRET]'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
        (r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', '[IP_REDACTED]'),
        (r'(user[_-]?name["\']?\s*[:=]\s*["\']?)([a-zA-Z0-9_\-]{3,})', r'\1[USERNAME]'),
    ]
    mem_zip = io.BytesIO()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    with zipfile.ZipFile(mem_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
        for log_file in log_dir.glob('*.log'):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                for pattern, replacement in redaction_patterns:
                    content = re.sub(pattern, replacement, content)
                zf.writestr(f'redacted_{log_file.name}', content)
            except Exception as e:
                zf.writestr(f'ERROR_{log_file.name}.txt', f'Failed to redact: {e}')
    mem_zip.seek(0)
    dest = Path(args.output or f'redacted_logs_{timestamp}.zip')
    _write_bytes_to_path(mem_zip.getvalue(), dest)
    print_success(f"Redacted logs archived to {dest}")
    return True


# ==================================
# DIAGNOSTICS & HEALTH
# ==================================

def cmd_diagnostics(args):
    result = web_server._compute_diagnostics()
    _pretty_json(result)
    return True


def cmd_diagnostics_schema(args):
    try:
        conn = web_server.get_db_connection()
        res = conn.execute('PRAGMA integrity_check').fetchone()
        conn.close()
        status = (res and res[0]) or 'unknown'
        ok = isinstance(status, str) and status.lower() == 'ok'
        _pretty_json({'status': status, 'ok': ok})
        return ok
    except Exception as e:
        print_error(f"Schema check failed: {e}")
        return False


def cmd_diagnostics_generate_cert(args):
    cert, key = web_server.generate_self_signed_cert()
    if cert and key:
        print_success(f"Certificate generated: {cert}")
        print_success(f"Key generated: {key}")
        return True
    print_error("Certificate generation failed; fallback to HTTP")
    return False


def cmd_diagnostics_unlock(args):
    password = args.password or getpass('Web password to unlock DB: ')
    if not password:
        print_error('Password is required to unlock database')
        return False
    try:
        db_key = DatabaseEncryption.initialize_encryption(password)
        web_server.app.config['DB_ENCRYPTION_KEY'] = db_key
        print_success('Database unlocked')
        return True
    except Exception as e:
        print_error(f"Unlock failed: {e}")
        return False


def cmd_system_health(args):
    try:
        health_status = {'timestamp': datetime.now().isoformat(), 'checks': []}
        try:
            conn = web_server.get_db_connection()
            conn.execute("SELECT COUNT(*) FROM trades").fetchone()
            conn.close()
            health_status['checks'].append({'name': 'Database Connection', 'status': 'OK', 'message': 'Database is accessible'})
        except Exception as e:
            health_status['checks'].append({'name': 'Database Connection', 'status': 'ERROR', 'message': f'Database error: {e}'})

        try:
            conn = web_server.get_db_connection()
            integrity_check = conn.execute('PRAGMA integrity_check').fetchone()
            conn.close()
            if integrity_check and integrity_check[0] == 'ok':
                health_status['checks'].append({'name': 'Database Integrity', 'status': 'OK', 'message': 'Database integrity verified'})
            else:
                health_status['checks'].append({'name': 'Database Integrity', 'status': 'WARNING', 'message': f'Integrity check result: {integrity_check[0] if integrity_check else "Unknown"}'})
        except Exception as e:
            health_status['checks'].append({'name': 'Database Integrity', 'status': 'ERROR', 'message': f'Integrity check failed: {e}'})

        core_scripts = ['Crypto_Transaction_Engine.py', 'Auto_Runner.py', 'src/tools/setup.py']
        missing_scripts = [script for script in core_scripts if not (BASE_DIR / script).exists()]
        if missing_scripts:
            health_status['checks'].append({'name': 'Core Scripts', 'status': 'WARNING', 'message': f'Missing scripts: {", ".join(missing_scripts)}'})
        else:
            health_status['checks'].append({'name': 'Core Scripts', 'status': 'OK', 'message': f'All {len(core_scripts)} core scripts present'})

        config_files = {'config.json': CONFIG_FILE, 'api_keys (encrypted)': API_KEYS_ENCRYPTED_FILE, 'wallets (encrypted)': WALLETS_ENCRYPTED_FILE}
        missing_configs = [name for name, path in config_files.items() if not path.exists()]
        if missing_configs:
            health_status['checks'].append({'name': 'Configuration Files', 'status': 'WARNING', 'message': f'Missing configs: {", ".join(missing_configs)}'})
        else:
            health_status['checks'].append({'name': 'Configuration Files', 'status': 'OK', 'message': 'All configuration files present'})

        if OUTPUT_DIR.exists():
            health_status['checks'].append({'name': 'Output Directory', 'status': 'OK', 'message': 'Output directory exists'})
        else:
            health_status['checks'].append({'name': 'Output Directory', 'status': 'WARNING', 'message': 'Output directory not found'})

        if (BASE_DIR / 'keys' / 'web_encryption.key').exists():
            health_status['checks'].append({'name': 'Encryption Key', 'status': 'OK', 'message': 'Encryption key present'})
        else:
            health_status['checks'].append({'name': 'Encryption Key', 'status': 'WARNING', 'message': 'Encryption key missing (will regenerate)'})

        has_errors = any(check['status'] == 'ERROR' for check in health_status['checks'])
        has_warnings = any(check['status'] == 'WARNING' for check in health_status['checks'])
        if has_errors:
            health_status['overall_status'] = 'ERROR'
            health_status['summary'] = 'System has critical errors'
        elif has_warnings:
            health_status['overall_status'] = 'WARNING'
            health_status['summary'] = 'System has warnings'
        else:
            health_status['overall_status'] = 'OK'
            health_status['summary'] = 'All systems operational'
        _pretty_json(health_status)
        return not has_errors
    except Exception as e:
        print_error(f"Health check failed: {e}")
        return False


def cmd_status(args):
    try:
        status = web_server.txn_app.get_status()
        _pretty_json(status)
        return True
    except Exception as e:
        print_error(f"Could not load status: {e}")
        return False


# ==================================
# SCHEDULER
# ==================================

def _get_scheduler():
    auto_runner_path = BASE_DIR / 'Auto_Runner.py'
    return ScheduleManager(BASE_DIR, auto_runner_path)


def cmd_schedule_show(args):
    scheduler = _get_scheduler()
    config = scheduler.load_schedule_config()
    active = scheduler.get_active_schedules()
    _pretty_json({'config': config, 'active': active})
    scheduler.shutdown()
    return True


def cmd_schedule_save(args):
    scheduler = _get_scheduler()
    cfg_path = _require_file(Path(args.file), "Schedule config")
    if not cfg_path:
        scheduler.shutdown()
        return False
    config = _load_json(cfg_path)
    if 'schedules' not in config:
        print_error('Missing schedules array in config file')
        scheduler.shutdown()
        return False
    scheduler.save_schedule_config(config)
    scheduler.reload_schedules()
    print_success('Schedule configuration saved')
    scheduler.shutdown()
    return True


def cmd_schedule_toggle(args):
    scheduler = _get_scheduler()
    config = scheduler.load_schedule_config()
    if args.disabled:
        enabled = False
    elif args.enabled:
        enabled = True
    else:
        print_error('Specify --enabled or --disabled')
        scheduler.shutdown()
        return False

    config['enabled'] = enabled
    scheduler.save_schedule_config(config)
    scheduler.reload_schedules()
    print_success(f"Scheduling {'enabled' if enabled else 'disabled'}")
    scheduler.shutdown()
    return True


def cmd_schedule_test(args):
    scheduler = _get_scheduler()
    cascade = args.cascade
    thread = subprocess.Popen([sys.executable, str(BASE_DIR / 'Auto_Runner.py')] + (['--cascade'] if cascade else []))
    print_info(f"Started test calculation (pid {thread.pid})")
    scheduler.shutdown()
    return True


# ==================================
# ACCURACY MODE / ML
# ==================================

def cmd_accuracy_get(args):
    try:
        config = _load_json(CONFIG_FILE)
        _pretty_json(config.get('accuracy_mode', {}))
        return True
    except Exception as e:
        print_error(f"Could not load accuracy config: {e}")
        return False


def cmd_accuracy_set(args):
    try:
        config = _load_json(CONFIG_FILE)
        if 'accuracy_mode' not in config:
            config['accuracy_mode'] = {}
        update_data = _load_json(Path(args.file)) if args.file else {}
        for field in ['enabled', 'fraud_detection', 'smart_descriptions', 'pattern_learning', 'natural_language_search', 'fallback_on_error']:
            if field in update_data:
                config['accuracy_mode'][field] = update_data[field]
        _save_json(CONFIG_FILE, config)
        print_success('Accuracy mode configuration updated')
        return True
    except Exception as e:
        print_error(f"Could not update accuracy config: {e}")
        return False


def cmd_ml_check_deps(args):
    try:
        torch_installed = False
        transformers_installed = False
        try:
            import torch  # noqa: F401
            torch_installed = True
        except ImportError:
            pass
        try:
            import transformers  # noqa: F401
            transformers_installed = True
        except ImportError:
            pass
        hf_cache = os.environ.get('HF_HOME', os.path.expanduser('~/.cache/huggingface/hub'))
        free_gb = None
        try:
            stat = shutil.disk_usage(os.path.dirname(hf_cache))
            free_gb = stat.free / (1024**3)
        except Exception:
            pass
        result = {
            'torch_installed': torch_installed,
            'transformers_installed': transformers_installed,
            'deps_satisfied': torch_installed and transformers_installed,
            'cache_location': hf_cache,
            'free_disk_space_gb': round(free_gb, 1) if free_gb else 'Unknown',
        }
        _pretty_json(result)
        return True
    except Exception as e:
        print_error(f"Dependency check failed: {e}")
        return False


def cmd_ml_pre_download(args):
    try:
        from src.ml_service import MLService
        ml_service = MLService(mode='tinyllama', auto_shutdown_after_inference=False)
        ml_service._load_model()
        ready = ml_service.pipe is not None
        if args.shutdown:
            try:
                ml_service.shutdown()
            except Exception:
                pass
        if ready:
            print_success('TinyLLaMA model downloaded and ready')
            return True
        print_error('Model failed to load')
        return False
    except Exception as e:
        print_error(f"Pre-download failed: {e}")
        return False


def cmd_ml_delete_model(args):
    try:
        hf_cache = os.environ.get('HF_HOME', os.path.expanduser('~/.cache/huggingface/hub'))
        tinyllama_cache = Path(hf_cache) / 'models--TheBloke--TinyLlama-1.1B-Chat-v1.0-GGUF'
        if not tinyllama_cache.exists():
            print_info('TinyLLaMA cache not found')
            return True
        total_size = 0
        for dirpath, _, filenames in os.walk(tinyllama_cache):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                total_size += filepath.stat().st_size
        shutil.rmtree(tinyllama_cache)
        freed_space_gb = round(total_size / (1024**3), 1)
        print_success(f"TinyLLaMA cache deleted (freed {freed_space_gb}GB)")
        return True
    except Exception as e:
        print_error(f"Delete failed: {e}")
        return False

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Crypto Transaction Tracker - Self-Hosted Activity Suite',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s setup              # Run initial setup wizard
  %(prog)s run                # Process current-year activity
  %(prog)s run --cascade      # Process all years
  %(prog)s review             # Review and fix audit warnings
  %(prog)s review 2024        # Review specific year
  %(prog)s web                # Start web UI
  %(prog)s test               # Run full test suite
  %(prog)s test --file test_setup_wizard.py  # Run specific test
  %(prog)s info               # Display system info
    %(prog)s export             # Export reports for current year
    %(prog)s export --year 2024 # Export reports for specific year

For more information, see README.md or visit the web UI.
        '''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Setup command
    parser_setup = subparsers.add_parser('setup', help='Run initial setup wizard')
    parser_setup.set_defaults(func=cmd_setup)
    
    # Run command
    parser_run = subparsers.add_parser('run', help='Process transactions')
    parser_run.add_argument('--cascade', action='store_true', 
                          help='Process all years (cascade mode)')
    parser_run.set_defaults(func=cmd_run)
    
    # Review command
    parser_review = subparsers.add_parser('review', help='Run manual review assistant')
    parser_review.add_argument('year', nargs='?', 
                             help='Year to review (default: current year)')
    parser_review.set_defaults(func=cmd_review)
    
    # Web command
    parser_web = subparsers.add_parser('web', help='Start web UI server')
    parser_web.set_defaults(func=cmd_web)
    
    # Test command
    parser_test = subparsers.add_parser('test', help='Run test suite')
    parser_test.add_argument('--file', help='Specific test file to run')
    parser_test.set_defaults(func=cmd_test)
    
    # Info command
    parser_info = subparsers.add_parser('info', help='Display system information')
    parser_info.set_defaults(func=cmd_info)
    
    # Export command
    parser_export = subparsers.add_parser('export', help='List/export generated reports')
    parser_export.add_argument('--year', help='Year (default: current year)')
    parser_export.set_defaults(func=cmd_export)

    # Transactions
    parser_tx = subparsers.add_parser('transactions', help='Manage transactions (list/add/update/delete/upload/reprocess)')
    tx_sub = parser_tx.add_subparsers(dest='tx_command')
    tx_sub.required = True

    tx_list = tx_sub.add_parser('list', help='List transactions')
    tx_list.add_argument('--page', type=int, default=1, help='Page number')
    tx_list.add_argument('--per-page', type=int, default=50, dest='per_page', help='Page size')
    tx_list.add_argument('--search', help='Search text')
    tx_list.add_argument('--coin', help='Filter by coin')
    tx_list.add_argument('--action', help='Filter by action')
    tx_list.add_argument('--source', help='Filter by source')
    tx_list.set_defaults(func=cmd_tx_list)

    tx_add = tx_sub.add_parser('add', help='Add a transaction')
    tx_add.add_argument('--date', required=True, help='ISO date/time')
    tx_add.add_argument('--action', required=True, help='Action (BUY/SELL/TRANSFER/...)')
    tx_add.add_argument('--coin', required=True, help='Coin symbol')
    tx_add.add_argument('--amount', required=True, help='Amount')
    tx_add.add_argument('--source', help='Source/exchange')
    tx_add.add_argument('--destination', help='Destination wallet/exchange')
    tx_add.add_argument('--price-usd', type=float, dest='price_usd', help='Price in USD')
    tx_add.add_argument('--fee', type=float, help='Fee amount')
    tx_add.add_argument('--fee-coin', dest='fee_coin', help='Fee coin')
    tx_add.set_defaults(func=cmd_tx_add)

    tx_update = tx_sub.add_parser('update', help='Update a transaction')
    tx_update.add_argument('id', help='Transaction id')
    tx_update.add_argument('--date')
    tx_update.add_argument('--action')
    tx_update.add_argument('--coin')
    tx_update.add_argument('--amount')
    tx_update.add_argument('--source')
    tx_update.add_argument('--destination')
    tx_update.add_argument('--price-usd', type=float, dest='price_usd')
    tx_update.add_argument('--fee', type=float)
    tx_update.add_argument('--fee-coin', dest='fee_coin')
    tx_update.set_defaults(func=cmd_tx_update)

    tx_delete = tx_sub.add_parser('delete', help='Delete a transaction')
    tx_delete.add_argument('id', help='Transaction id')
    tx_delete.set_defaults(func=cmd_tx_delete)

    tx_upload = tx_sub.add_parser('upload', help='Upload CSV transactions and ingest via engine')
    tx_upload.add_argument('file', help='Path to CSV file')
    tx_upload.set_defaults(func=cmd_tx_upload)

    tx_template = tx_sub.add_parser('template', help='Generate a CSV template for manual imports')
    tx_template.add_argument('--output', help='Destination path for template CSV')
    tx_template.set_defaults(func=cmd_tx_template)

    tx_reprocess = tx_sub.add_parser('reprocess', help='Reprocess all transactions with ML fallback')
    tx_reprocess.add_argument('--batch-size', type=int, default=10, dest='batch_size', help='Batch size for ML classification')
    tx_reprocess.set_defaults(func=cmd_tx_reprocess)

    # Reports and warnings
    parser_reports = subparsers.add_parser('reports', help='Report listing and downloads')
    reports_sub = parser_reports.add_subparsers(dest='reports_command')
    reports_sub.required = True
    rep_list = reports_sub.add_parser('list', help='List available reports')
    rep_list.set_defaults(func=cmd_reports_list)
    rep_dl = reports_sub.add_parser('download', help='Download a report')
    rep_dl.add_argument('path', help='Path relative to project root (e.g., outputs/Year_2024/REPORT.csv)')
    rep_dl.add_argument('--output', help='Destination path')
    rep_dl.set_defaults(func=cmd_reports_download)

    parser_warnings = subparsers.add_parser('warnings', help='Show review warnings and suggestions')
    parser_warnings.set_defaults(func=cmd_warnings)

    parser_stats = subparsers.add_parser('stats', help='Show transaction statistics dashboard data')
    parser_stats.set_defaults(func=cmd_stats)

    # Configuration
    parser_config = subparsers.add_parser('config', help='View or replace configuration')
    config_sub = parser_config.add_subparsers(dest='config_command')
    config_sub.required = True
    cfg_show = config_sub.add_parser('show', help='Show config.json')
    cfg_show.set_defaults(func=cmd_config_show)
    cfg_set = config_sub.add_parser('set', help='Replace config.json from a file')
    cfg_set.add_argument('--file', required=True, help='Path to JSON config file')
    cfg_set.set_defaults(func=cmd_config_set)

    # Wallets
    parser_wallets = subparsers.add_parser('wallets', help='Manage wallets')
    wallets_sub = parser_wallets.add_subparsers(dest='wallets_command')
    wallets_sub.required = True
    w_show = wallets_sub.add_parser('show', help='Show wallets')
    w_show.set_defaults(func=cmd_wallets_show)
    w_save = wallets_sub.add_parser('save', help='Save wallets from JSON file')
    w_save.add_argument('--file', required=True, help='Path to wallets JSON')
    w_save.set_defaults(func=cmd_wallets_save)
    w_test = wallets_sub.add_parser('test', help='Test wallet matching logic')
    w_test.add_argument('--source', required=True, help='Source/exchange label')
    w_test.add_argument('--address', required=True, help='Wallet address to match')
    w_test.set_defaults(func=cmd_wallets_test)

    # API keys
    parser_keys = subparsers.add_parser('api-keys', help='Manage exchange API keys')
    keys_sub = parser_keys.add_subparsers(dest='keys_command')
    keys_sub.required = True
    k_show = keys_sub.add_parser('show', help='Show API keys (masked)')
    k_show.set_defaults(func=cmd_api_keys_show)
    k_save = keys_sub.add_parser('save', help='Save API keys from JSON file')
    k_save.add_argument('--file', required=True, help='Path to API keys JSON')
    k_save.set_defaults(func=cmd_api_keys_save)
    k_test = keys_sub.add_parser('test', help='Test an API key against exchange')
    k_test.add_argument('--exchange', required=True, help='Exchange id (e.g., binance)')
    k_test.add_argument('--apiKey', required=True, help='API key')
    k_test.add_argument('--secret', required=True, help='API secret')
    k_test.set_defaults(func=cmd_api_keys_test)

    # Backups
    parser_backup = subparsers.add_parser('backup', help='Create or restore backups')
    backup_sub = parser_backup.add_subparsers(dest='backup_command')
    backup_sub.required = True
    b_full = backup_sub.add_parser('full', help='Export database table to zip CSV')
    b_full.add_argument('--output', help='Destination zip path')
    b_full.set_defaults(func=cmd_backup_full)
    b_zip = backup_sub.add_parser('zip', help='Create encrypted zip backup of configs/db')
    b_zip.add_argument('--output', help='Destination backup path')
    b_zip.set_defaults(func=cmd_backup_zip)
    b_restore = backup_sub.add_parser('restore', help='Restore from backup .zip or .zip.enc')
    b_restore.add_argument('file', help='Backup file path')
    b_restore.add_argument('--mode', choices=['merge', 'replace'], default='merge', help='Merge or replace database when restoring')
    b_restore.add_argument('--password', help='Password for encrypted backups')
    b_restore.set_defaults(func=cmd_restore_backup)

    # Logs
    parser_logs = subparsers.add_parser('logs', help='Inspect and download logs')
    logs_sub = parser_logs.add_subparsers(dest='logs_command')
    logs_sub.required = True
    l_list = logs_sub.add_parser('list', help='List log files')
    l_list.set_defaults(func=cmd_logs_list)
    l_dl = logs_sub.add_parser('download', help='Download a specific log file')
    l_dl.add_argument('name', help='Path to log file')
    l_dl.add_argument('--output', help='Destination path')
    l_dl.set_defaults(func=cmd_logs_download)
    l_all = logs_sub.add_parser('download-all', help='Download all logs as zip')
    l_all.add_argument('--output', help='Destination zip path')
    l_all.set_defaults(func=cmd_logs_download_all)
    l_red = logs_sub.add_parser('download-redacted', help='Download redacted logs for support')
    l_red.add_argument('--output', help='Destination zip path')
    l_red.set_defaults(func=cmd_logs_download_redacted)

    # Diagnostics
    parser_diag = subparsers.add_parser('diagnostics', help='Run diagnostics and health checks')
    diag_sub = parser_diag.add_subparsers(dest='diagnostics_command')
    diag_sub.required = True
    d_run = diag_sub.add_parser('run', help='Compute diagnostics')
    d_run.set_defaults(func=cmd_diagnostics)
    d_schema = diag_sub.add_parser('schema', help='Run PRAGMA integrity_check')
    d_schema.set_defaults(func=cmd_diagnostics_schema)
    d_cert = diag_sub.add_parser('generate-cert', help='Generate self-signed HTTPS cert')
    d_cert.set_defaults(func=cmd_diagnostics_generate_cert)
    d_unlock = diag_sub.add_parser('unlock', help='Unlock encrypted database with password')
    d_unlock.add_argument('--password', help='Web password')
    d_unlock.set_defaults(func=cmd_diagnostics_unlock)
    d_health = diag_sub.add_parser('health', help='System health summary')
    d_health.set_defaults(func=cmd_system_health)
    d_status = diag_sub.add_parser('status', help='System status timestamps')
    d_status.set_defaults(func=cmd_status)

    # Scheduler
    parser_sched = subparsers.add_parser('schedule', help='Manage automated schedules')
    sched_sub = parser_sched.add_subparsers(dest='schedule_command')
    sched_sub.required = True
    s_show = sched_sub.add_parser('show', help='Show schedule config and active jobs')
    s_show.set_defaults(func=cmd_schedule_show)
    s_save = sched_sub.add_parser('save', help='Save schedule config from file')
    s_save.add_argument('--file', required=True, help='Path to schedule_config.json')
    s_save.set_defaults(func=cmd_schedule_save)
    s_toggle = sched_sub.add_parser('toggle', help='Enable or disable scheduling')
    s_toggle.add_argument('--enabled', action='store_true', help='Enable scheduling')
    s_toggle.add_argument('--disabled', action='store_true', help='Disable scheduling')
    s_toggle.set_defaults(func=cmd_schedule_toggle)
    s_test = sched_sub.add_parser('test', help='Run a test calculation now')
    s_test.add_argument('--cascade', action='store_true', help='Run in cascade mode')
    s_test.set_defaults(func=cmd_schedule_test)

    # Accuracy / ML
    parser_accuracy = subparsers.add_parser('accuracy', help='Manage accuracy mode configuration')
    acc_sub = parser_accuracy.add_subparsers(dest='accuracy_command')
    acc_sub.required = True
    acc_get = acc_sub.add_parser('get', help='Show accuracy mode config')
    acc_get.set_defaults(func=cmd_accuracy_get)
    acc_set = acc_sub.add_parser('set', help='Update accuracy mode config from JSON file')
    acc_set.add_argument('--file', required=True, help='Path to JSON with accuracy_mode fields')
    acc_set.set_defaults(func=cmd_accuracy_set)

    parser_ml = subparsers.add_parser('ml', help='ML model management')
    ml_sub = parser_ml.add_subparsers(dest='ml_command')
    ml_sub.required = True
    ml_check = ml_sub.add_parser('check-deps', help='Check ML dependencies')
    ml_check.set_defaults(func=cmd_ml_check_deps)
    ml_pre = ml_sub.add_parser('pre-download', help='Pre-download TinyLLaMA model')
    ml_pre.add_argument('--shutdown', action='store_true', help='Shutdown model after download')
    ml_pre.set_defaults(func=cmd_ml_pre_download)
    ml_del = ml_sub.add_parser('delete-model', help='Delete TinyLLaMA cached model to free space')
    ml_del.set_defaults(func=cmd_ml_delete_model)
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command specified, show help
    if not args.command:
        parser.print_help()
        return 0
    
    # Run command
    try:
        success = args.func(args)
        return 0 if success else 1
    except KeyboardInterrupt:
        print_info("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
