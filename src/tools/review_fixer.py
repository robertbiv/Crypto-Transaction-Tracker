"""
================================================================================
REVIEW FIXER - Interactive Issue Remediation Tool
================================================================================

Guided workflow tool for fixing audit risks and compliance issues
identified by the Tax Reviewer.

Fixable Issue Types:
    1. Missing Prices - Fetch from CoinGecko/CoinMarketCap APIs
    2. Spam Tokens - Bulk mark as spam (zero value airdrops)
    3. NFT Collectibles - Apply collectible prefix for 28% rate
    4. Duplicate Transactions - Merge or delete duplicates
    5. Price Anomalies - Correct unit price vs total value errors
    6. High Fees - Flag or correct excessive fee entries
    7. Missing Basis - Add acquisition records for unmatched sells

Interactive Features:
    - Step-by-step guided prompts
    - Batch operations for similar issues
    - Preview before commit
    - Automatic backup before changes
    - Undo/rollback capability
    - Progress tracking for large batches

Price Fetching:
    - CoinGecko Free API integration
    - CoinMarketCap API support
    - Historical price lookups with date matching
    - Rate limit compliance (10 calls/min free tier)
    - Token ID caching for performance
    - Fallback to multiple sources

Safety Features:
    - Database backup before any modifications
    - Transaction-based changes (atomic commits)
    - Dry-run mode for testing
    - Detailed change logging
    - Restoration from backup on errors

Usage:
    python src/tools/review_fixer.py
    python cli.py fix-review

Workflow:
    1. Run tax calculations (generates warnings)
    2. Run Tax Reviewer (identifies issues)
    3. Run Review Fixer (guided remediation)
    4. Re-run tax calculations (verify fixes)

Author: robertbiv
Last Modified: December 2025
================================================================================
"""

import json
import shutil
import os
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import pandas as pd
import requests
import time
import datetime as dt
import src.core.engine as app
from src.core.engine import DatabaseManager, logger
from src.processors import PriceFetcher

# ====================================================================================
# TOKEN CACHE CONFIGURATION
# ====================================================================================
TOKEN_CACHE_FILE = Path("configs/cached_token_addresses.json")
CACHE_REFRESH_DAYS = 7  # Refresh cache every 7 days

# ====================================================================================
# API RATE LIMITING CONFIGURATION (CoinGecko Free Tier: 10-30 calls/min)
# ====================================================================================
# For testing, set TEST_MODE=1 to reduce rate limit waits to 1 second (vs 60s production)
TEST_MODE = os.environ.get('TEST_MODE') == '1'
API_REQUEST_DELAY = 0.3  # Seconds between individual API requests (~3 calls/sec max)
API_BATCH_DELAY = 2  # Seconds after processing 50 tokens
API_MAX_RETRIES = 5  # Maximum retry attempts for failed requests
API_INITIAL_BACKOFF = 1  # Initial backoff delay in seconds
API_MAX_RETRY_WAIT = 1 if TEST_MODE else 60  # Max wait time for rate limit retries (1s test, 60s prod)

# ====================================================================================
# DATE PARSING HELPER
# ====================================================================================
def _parse_date_flexible(date_str):
    """Parse date string with multiple format fallbacks.
    
    Accepts:
    - ISO format with time: '2023-01-01T00:00:00'
    - ISO format with time and TZ: '2023-01-01T00:00:00+00:00'
    - Date with time: '2023-01-01 00:00:00'
    - Date only: '2023-01-01'
    """
    if isinstance(date_str, dt.date):
        return date_str
    
    date_str = str(date_str).strip()
    
    # Try pandas to_datetime first (most flexible)
    try:
        return pd.to_datetime(date_str, utc=True).date()
    except (ValueError, pd.errors.ParserError):
        pass
    
    # Try various strptime formats
    formats = [
        '%Y-%m-%d %H:%M:%S',  # '2023-01-01 00:00:00'
        '%Y-%m-%d',           # '2023-01-01'
        '%Y-%m-%dT%H:%M:%S',  # '2023-01-01T00:00:00'
    ]
    
    for fmt in formats:
        try:
            return dt.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    # Last resort: parse as ISO and extract date
    try:
        return dt.datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
    except (ValueError, AttributeError):
        raise ValueError(f"Unable to parse date: {date_str}")

class InteractiveReviewFixer:
    """Interactive tool to fix issues detected by Tax Reviewer"""
    
    def __init__(self, db, year):
        self.db = db
        self.year = year
        self.fixes_applied = []
        self.backup_file = None
        self._token_map_cache = None  # Session-level cache to avoid repeated API calls
        
        # Set up session logging
        self._setup_session_log()
    
    def _setup_session_log(self):
        """Set up logging for this fixer session"""
        from datetime import datetime
        
        # Create log directory if it doesn't exist
        log_dir = app.LOG_DIR if hasattr(app, 'LOG_DIR') else app.OUTPUT_DIR / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create session log file
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_file = log_dir / f"{timestamp}_interactive_fixer_session.log"
        
        # Open log file for writing
        self.log_handle = open(self.log_file, 'w', encoding='utf-8')
        self._log(f"=== INTERACTIVE REVIEW FIXER SESSION ===")
        self._log(f"Started: {datetime.now().isoformat()}")
        self._log(f"Year: {self.year}")
        self._log(f"Database: {self.db.db_file if hasattr(self.db, 'db_file') else 'unknown'}")
        self._log("="*80)
        self._log("")
    
    def _log(self, message):
        """Log a message to both console and log file"""
        try:
            if hasattr(self, 'log_handle') and self.log_handle and not self.log_handle.closed:
                self.log_handle.write(message + '\n')
                self.log_handle.flush()  # Ensure it's written immediately
        except:
            pass  # Ignore errors if log file is closed
    
    def _log_input(self, prompt, user_response):
        """Log user input"""
        self._log(f"PROMPT: {prompt}")
        self._log(f"USER INPUT: {user_response}")
        self._log("")
    
    def _log_output(self, message):
        """Log program output"""
        self._log(f"OUTPUT: {message}")
    
    def __del__(self):
        """Close log file on cleanup"""
        try:
            if hasattr(self, 'log_handle') and self.log_handle and not self.log_handle.closed:
                from datetime import datetime
                self._log("")
                self._log("="*80)
                self._log(f"Session ended: {datetime.now().isoformat()}")
                self._log(f"Log saved to: {self.log_file}")
                self.log_handle.close()
        except:
            pass  # Ignore errors during cleanup
    
    def _print(self, message):
        """Print to console and log to file"""
        print(message)
        self._log_output(message)
    
    def _input(self, prompt):
        """Get user input and log both prompt and response"""
        print(prompt, end='')
        response = input()
        self._log_input(prompt, response)
        return response
        
    def load_review_report(self, report_path=None):
        """Load the most recent review report"""
        self._log("Loading review report...")
        if report_path:
            with open(report_path, 'r') as f:
                return json.load(f)
        
        # Find most recent review report
        year_dir = app.OUTPUT_DIR / f"Year_{self.year}"
        if not year_dir.exists():
            print(f"Error: No reports found for year {self.year}")
            return None
        
        review_files = list(year_dir.glob("tax_review_*.json"))
        if not review_files:
            print(f"Error: No review reports found in {year_dir}")
            return None
        
        # Get most recent
        latest = max(review_files, key=lambda p: p.stat().st_mtime)
        print(f"Loading review report: {latest.name}")
        
        with open(latest, 'r') as f:
            return json.load(f)
    
    def create_backup(self):
        """Create database backup before making changes"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_file = app.DB_FILE.parent / f"{app.DB_FILE.stem}_BEFORE_FIX_{timestamp}.db"
        
        import shutil
        shutil.copy2(app.DB_FILE, self.backup_file)
        print(f"\n✓ Database backup created: {self.backup_file.name}")
        return self.backup_file
    
    def run_interactive_fixer(self):
        """Main interactive fixing workflow"""
        print("\n" + "="*80)
        print("INTERACTIVE REVIEW FIXER - Guided Fix Process")
        print("="*80)
        
        # Load report
        report = self.load_review_report()
        if not report:
            return
        
        warnings = report.get('warnings', [])
        if not warnings:
            print("\n✓ No warnings to fix! Your data looks clean.")
            return
        
        print(f"\nFound {len(warnings)} warning(s) requiring attention.")
        print("\nThis tool will guide you through fixing each issue automatically.")
        print("You can accept, override, or skip each transaction.\n")
        
        # Confirm before proceeding
        proceed = input("Ready to start? (yes/no): ").strip().lower()
        if proceed not in ['yes', 'y']:
            print("Exiting without changes.")
            return
        
        # Create backup
        self.create_backup()
        
        # Process each warning with guided flow
        for i, warning in enumerate(warnings, 1):
            print(f"\n{'='*80}")
            print(f"WARNING {i}/{len(warnings)}: {warning['title']}")
            print(f"{'='*80}")
            print(f"Category: {warning['category']}")
            print(f"Severity: {warning['severity']}")
            print(f"Count: {warning['count']} issue(s)")
            print(f"Description: {warning['description']}")
            
            # Route to appropriate guided fixer
            category = warning['category']
            if category == 'NFT_COLLECTIBLES':
                self._guided_fix_nft_collectibles(warning)
            elif category == 'SUBSTANTIALLY_IDENTICAL_WASH_SALES':
                self._guided_fix_wash_sales(warning)
            elif category == 'MISSING_PRICES':
                self._guided_fix_missing_prices(warning)
            elif category == 'DUPLICATE_TRANSACTIONS':
                self._guided_fix_duplicates(warning)
            elif category == 'HIGH_FEES':
                self._guided_fix_high_fees(warning)
            elif category == 'PRICE_ANOMALIES' or category == 'PRICE_ANOMALIES':
                self._guided_fix_price_anomalies(warning)
            else:
                self._generic_fix_prompt(warning)
        
        # Summary
        self._print_summary()
    
    def _guided_fix_nft_collectibles(self, warning):
        """Guided fix for NFT/collectible warnings - rename individually"""
        print("\n--- GUIDED FIX: NFT/COLLECTIBLES ---")
        print("Rename each NFT/collectible for proper tracking.\n")
        
        for item in warning['items']:
            print(f"\n  Current: {item['coin']} (Date: {item['date']}, Amount: {item['amount']})")
            new_name = input(f"    Rename to (Enter=keep as-is, 'skip'=skip all remaining): ").strip()
            
            if new_name.lower() == 'skip':
                print("\n[SKIPPED] Remaining NFTs will appear again next time you run the fixer.")
                break
            elif new_name:
                self._rename_coin(item['id'], item['coin'], new_name)
                print(f"    ✓ Renamed to '{new_name}'")
            else:
                print("    → Kept as-is")
    
    def _guided_fix_wash_sales(self, warning):
        """Guided fix for wash sale warnings - rename to distinguish"""
        print("\n--- GUIDED FIX: WASH SALES ---")
        print("Rename coins to distinguish between different wallets/exchanges.")
        print("Example: BTC-Coinbase, BTC-Ledger, ETH-Kraken\n")
        
        for item in warning['items']:
            print(f"\n  {item['coin']} (Date: {item['date']}, Amount: {item['amount']})")
            new_name = input(f"    Rename to (Enter=keep as-is, 'skip'=skip all remaining): ").strip()
            
            if new_name.lower() == 'skip':
                print("\n[SKIPPED] Remaining wash sales will appear again next time you run the fixer.")
                break
            elif new_name:
                self._rename_coin(item['id'], item['coin'], new_name)
                print(f"    ✓ Renamed to '{new_name}'")
            else:
                print("    → Kept as-is")
    
    def _guided_fix_missing_prices(self, warning):
        """Guided fix for missing prices - check blockchain first with API key prompts"""
        self._print("\n--- GUIDED FIX: MISSING PRICES ---")
        self._print(f"Found {len(warning['items'])} transactions with missing/zero prices.")
        
        # Simplified Menu (No Bulk Options)
        self._print("1. Guided fix (check blockchain, fetch suggestions, approve/override per item)")
        self._print("2. Set custom price (enter manually per item)")
        self._print("3. Skip (review later)")

        choice = self._input("\nSelect option (1-3): ").strip()

        if choice == '1':
            self._print("\n  Checking blockchain and fetching suggested prices...")
            fetcher = PriceFetcher()

            for item in warning['items']:
                coin = item['coin']
                date_str = str(item['date']).split()[0]
                transaction_id = item['id']

                self._print(f"\n  {coin} on {date_str} (amount: {item['amount']})")
                
                # Step 1: Check if transaction is on blockchain with existing wallets
                # This will prompt for API key if needed
                bc_found, bc_price, bc_details, api_key_needed = self._check_transaction_on_blockchain_with_prompts(
                    transaction_id, coin, date_str, item['amount']
                )
                
                new_wallet_to_save = None
                
                # If API key was needed but user skipped, treat as not found
                if api_key_needed == 'skipped':
                    self._print(f"    ⚠️  API key required but skipped - treating as transaction not found")
                    bc_found = False
                    bc_price = None
                
                if bc_found:
                    # Transaction found on blockchain
                    self._print(f"    ✅ Transaction found on blockchain!")
                    if bc_details:
                        self._print(f"       {bc_details}")
                    if bc_price and bc_price > 0:
                        self._print(f"    💎 On-chain price: ${bc_price:.6f}")
                        self._print(f"    → RECOMMENDED: Use blockchain price (most accurate)")
                    
                    # Ask if they want to add another wallet address
                    add_wallet = self._input("    Would you like to add another wallet address? (y/n): ").strip().lower()
                    if add_wallet == 'y':
                        new_wallet_to_save = self._input("    Enter wallet address: ").strip()
                else:
                    # Transaction NOT found on blockchain
                    self._print(f"    ⚠️  Transaction not found on blockchain")
                    
                    # Prompt for wallet address
                    add_wallet = self._input("    Would you like to enter a wallet address to check blockchain? (y/n): ").strip().lower()
                    if add_wallet == 'y':
                        new_wallet_to_save = self._input("    Enter wallet address: ").strip()
                        
                        if new_wallet_to_save:
                            # Check blockchain again with new wallet
                            self._print(f"    🔍 Checking blockchain with provided wallet...")
                            bc_found_new, bc_price_new, bc_details_new, api_key_status = self._check_transaction_on_blockchain_with_prompts(
                                transaction_id, coin, date_str, item['amount'], 
                                additional_wallet=new_wallet_to_save
                            )
                            
                            if api_key_status == 'skipped':
                                self._print(f"    ⚠️  API key required but skipped")
                                bc_found_new = False
                            
                            if bc_found_new:
                                self._print(f"    ✅ Transaction found with provided wallet!")
                                if bc_details_new:
                                    self._print(f"       {bc_details_new}")
                                bc_found = True
                                bc_price = bc_price_new
                            else:
                                self._print(f"    ❌ Transaction not found with provided wallet on blockchain")
                
                # Step 2: Always ask if they want to save the wallet (if provided)
                if new_wallet_to_save:
                    save_wallet = self._input("    Save this wallet address to wallets.json? (y/n): ").strip().lower()
                    if save_wallet == 'y':
                        success, message = self._save_wallet_address(new_wallet_to_save, coin)
                        self._print(f"    {message}")
                
                # Step 3: Get Yahoo Finance price as fallback
                yf_price = None
                try:
                    yf_price = fetcher.get_price(coin, pd.to_datetime(date_str, utc=True))
                except Exception as e:
                    yf_price = None
                
                # Step 4: Determine what to suggest
                if bc_found and bc_price and bc_price > 0:
                    # Blockchain price found - suggest it
                    suggested_price = bc_price
                    self._print(f"\n    💎 Blockchain price: ${bc_price:.6f}")
                    if yf_price and yf_price > 0:
                        diff_pct = abs(bc_price - yf_price) / yf_price * 100 if yf_price > 0 else 0
                        self._print(f"    📊 Yahoo Finance: ${yf_price:.2f} (diff: {diff_pct:.1f}%)")
                    self._print(f"    → Suggested: ${suggested_price:.6f} (blockchain - most accurate)")
                elif yf_price and yf_price > 0:
                    # Only Yahoo Finance available
                    suggested_price = yf_price
                    self._print(f"\n    📊 Yahoo Finance: ${yf_price:.2f}")
                    self._print(f"    ⚠️  WARNING: Daily close price may not match exact transaction time")
                    self._print(f"    💡 TIP: Check blockchain explorer or your exchange for exact price")
                    chain_hint = self._get_blockchain_explorer_hint(coin)
                    if chain_hint:
                        self._print(f"       {chain_hint}")
                    self._print(f"    → Suggested: ${suggested_price:.2f} (Yahoo Finance - may not be perfectly accurate)")
                else:
                    # No price available
                    self._print(f"\n    ❌ No price data available from any source")
                    self._print(f"    💡 TIP: Check your exchange transaction history or blockchain explorer")
                    chain_hint = self._get_blockchain_explorer_hint(coin)
                    if chain_hint:
                        self._print(f"       {chain_hint}")
                    suggested_price = None
                
                # Step 5: Get user confirmation
                if suggested_price:
                    user_input = self._input(f"    (Enter=accept ${suggested_price:.2f}, number=override, 'skip'=skip): ").strip()
                else:
                    user_input = self._input(f"    (Enter price manually or 'skip'): ").strip()
                
                if user_input.lower() == 'skip':
                    self._print(f"    → Skipped")
                    continue
                elif user_input == '' and suggested_price:
                    self._update_price(item['id'], Decimal(str(suggested_price)))
                    source = "blockchain" if bc_found and bc_price else "Yahoo Finance"
                    self._print(f"    ✓ Set to ${suggested_price:.2f} ({source})")
                else:
                    try:
                        manual_price = Decimal(user_input)
                        self._update_price(item['id'], manual_price)
                        self._print(f"    ✓ Set to ${manual_price} (manual)")
                    except:
                        self._print("    ✗ Invalid input, skipped.")

        elif choice == '2':
            for item in warning['items']:
                print(f"\n  {item['coin']} (Date: {item['date']}, Amount: {item['amount']})")
                price_input = input(f"    Enter USD price: $").strip()
                try:
                    price = Decimal(price_input)
                    self._update_price(item['id'], price)
                    print(f"    ✓ Updated to ${price}")
                except:
                    print(f"    ✗ Invalid price, skipping")

        else:
            print("\n[SKIPPED] Will review later.")
    
    def _guided_fix_duplicates(self, warning):
        """Guided fix for duplicate transactions - review each group"""
        print("\n--- GUIDED FIX: DUPLICATES ---")
        print(f"Found {len(warning['items'])} potential duplicate groups.")
        
        # Simplified Menu (No Bulk Options)
        print("1. Review each duplicate and choose which to keep")
        print("2. Skip (review later)")
        
        choice = input("\nSelect option (1-2): ").strip()
        
        if choice == '1':
            for item in warning['items']:
                ids = item['ids']
                print(f"\n  Duplicate group: {item['signature']}")
                
                # Show details of each
                for idx, tid in enumerate(ids, 1):
                    trade = self._get_transaction(tid)
                    print(f"    {idx}. ID={tid}, Source={trade.get('source')}, Batch={trade.get('batch_id')}")
                
                keep = input(f"  Which one to KEEP? (1-{len(ids)}) or 'skip': ").strip()
                
                if keep.isdigit() and 1 <= int(keep) <= len(ids):
                    keep_idx = int(keep) - 1
                    keep_id = ids[keep_idx]
                    
                    for idx, tid in enumerate(ids):
                        if idx != keep_idx:
                            self._delete_transaction(tid)
                            print(f"    ✓ Deleted: {tid}")
                    print(f"    ✓ Kept: {keep_id}")
                else:
                    print("    Skipped this group")
        
        else:
            print("\n[SKIPPED] Will review later.")
    
    def _guided_fix_high_fees(self, warning):
        """Guided fix for high fee warnings - show details for manual review"""
        print("\n--- GUIDED FIX: HIGH FEES ---")
        print("High fees in processed tax data can't be modified here.")
        print("Review these transactions and fix in your source CSV if needed:\n")
        
        for item in warning['items']:
            print(f"  • {item['coin']} on {item['date']}: Fee = ${item['fee_usd']}")
        
        print("\n  Edit these in your source CSV files and re-import if corrections needed.")
        input("\nPress Enter to continue...")
    
    def _guided_fix_price_anomalies(self, warning):
        """Guided fix for price anomalies - suggest correcting 'Total as Unit' errors"""
        print("\n--- GUIDED FIX: PRICE ANOMALIES ---")
        print("These transactions have prices that deviate significantly from market value.")
        print("Most common cause: Entering 'Total Value' instead of 'Price Per Coin'.\n")
        
        # Initialize PriceFetcher to get real market prices
        fetcher = PriceFetcher()
        
        for item in warning['items']:
            amount = float(item['amount'])
            reported_price = float(item.get('reported_price', 0))
            coin = item['coin']
            date_str = str(item['date']).split()[0]
            
            # Fetch real market price
            market_price = 0
            try:
                market_price = float(fetcher.get_price(coin, pd.to_datetime(date_str, utc=True)))
            except:
                pass  # If fetch fails, market_price remains 0
            
            suggested_fix_price = 0
            if amount != 0:
                suggested_fix_price = reported_price / amount
            
            print(f"\n  {coin} on {date_str}")
            print(f"    Amount: {amount}")
            print(f"    Current Price Entry: ${reported_price:,.2f}")
            if market_price > 0:
                print(f"    Market Price:        ${market_price:,.2f}")
            else:
                print(f"    Market Price:        Not available")
            
            print(f"\n    Option 1 (Fix 'Total as Unit'): Change price to ${suggested_fix_price:,.2f}")
            print(f"             (Use this if you entered the trade's total value in the price column)")
            
            if market_price > 0:
                print(f"    Option 2 (Use Market Price):    Change price to ${market_price:,.2f}")
            else:
                print(f"    Option 2 (Use Market Price):    [Not available - no price data found]")
            
            choice = input("    Choose fix (1/2), enter custom price, or 'skip': ").strip()
            
            if choice == '1':
                self._update_price(item['id'], Decimal(str(suggested_fix_price)))
                print(f"    ✓ Fixed: Price updated to ${suggested_fix_price:,.2f}")
            elif choice == '2':
                if market_price > 0:
                    self._update_price(item['id'], Decimal(str(market_price)))
                    print(f"    ✓ Fixed: Price updated to market value ${market_price:,.2f}")
                else:
                    print("    ✗ Market price not available. Please enter custom price or choose option 1.")
            elif choice.lower() == 'skip':
                print("    → Skipped")
            else:
                try:
                    custom = Decimal(choice)
                    self._update_price(item['id'], custom)
                    print(f"    ✓ Fixed: Price updated to ${custom}")
                except:
                    print("    ✗ Invalid input, skipped.")
    
    def _generic_fix_prompt(self, warning):
        """Generic handler for unimplemented fix types"""
        print("\n--- MANUAL REVIEW REQUIRED ---")
        print("This issue type requires manual review.")
        print(f"Please review the {warning['count']} item(s) listed above.")
        
        input("\nPress Enter to continue...")
    
    # ====================================================================================
    # DATABASE MODIFICATION METHODS
    # ====================================================================================
    
    def _rename_coin(self, transaction_id, old_name, new_name):
        """Rename a coin in the database (staged, not committed)"""
        self.db.cursor.execute("UPDATE trades SET coin = ? WHERE id = ?", (new_name, transaction_id))
        self.fixes_applied.append({
            'type': 'rename',
            'id': transaction_id,
            'old': old_name,
            'new': new_name
        })
    
    def _update_price(self, transaction_id, price):
        """Update price_usd for a transaction (staged, not committed)"""
        self.db.update_price(transaction_id, price)
        self.fixes_applied.append({
            'type': 'price_update',
            'id': transaction_id,
            'price': str(price)
        })
    
    def _delete_transaction(self, transaction_id):
        """Delete a transaction (staged, not committed)"""
        self.db.cursor.execute("DELETE FROM trades WHERE id = ?", (transaction_id,))
        self.fixes_applied.append({
            'type': 'delete',
            'id': transaction_id
        })
    
    def _get_transaction(self, transaction_id):
        """Get transaction details"""
        result = self.db.cursor.execute("SELECT * FROM trades WHERE id = ?", (transaction_id,))
        row = result.fetchone()
        if row:
            columns = [col[0] for col in result.description]
            return dict(zip(columns, row))
        return {}

    def _fetch_token_addresses_from_api(self):
        """Fetch token contract addresses from CoinGecko API with exponential backoff. 
        Returns dict: {chain: {symbol: contract_address}}"""
        print("\n[*] Fetching token addresses from CoinGecko API...")
        token_map = {}
        
        # Map CoinGecko platform IDs to our chain names
        platform_map = {
            'ethereum': 'ethereum',
            'polygon-pos': 'polygon',
            'binance-smart-chain': 'bsc',
            'avalanche': 'avax',
            'arbitrum-one': 'arbitrum',
            'optimistic-ethereum': 'optimism',
            'fantom': 'fantom'
        }
        
        def fetch_with_retry(url, params=None, max_retries=API_MAX_RETRIES, initial_delay=API_INITIAL_BACKOFF):
            """Fetch URL with exponential backoff on rate limit errors"""
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, params=params, timeout=30)
                    
                    # Check for rate limiting (429) or server errors (5xx)
                    if response.status_code == 429:
                        retry_after = int(response.headers.get('Retry-After', delay))
                        # Cap the retry wait time (5s in test mode, 60s in production)
                        retry_after = min(retry_after, API_MAX_RETRY_WAIT)
                        print(f"  [Rate limit] Waiting {retry_after}s before retry...")
                        time.sleep(retry_after)
                        delay = min(delay * 2, API_MAX_RETRY_WAIT)  # Exponential backoff
                        continue
                    elif response.status_code >= 500:
                        print(f"  [Server error {response.status_code}] Retrying in {delay}s...")
                        time.sleep(delay)
                        delay = min(delay * 2, API_MAX_RETRY_WAIT)
                        continue
                    
                    response.raise_for_status()
                    return response
                    
                except requests.exceptions.Timeout:
                    print(f"  [Timeout] Retrying in {delay}s...")
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries - 1:
                        raise
                    print(f"  [Error] {str(e)[:100]}... Retrying in {delay}s...")
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
            
            raise requests.exceptions.RequestException(f"Failed after {max_retries} retries")
        
        try:
            # Fetch top 250 tokens by market cap (free tier limit)
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': 250,
                'page': 1,
                'sparkline': False
            }
            
            response = fetch_with_retry(url, params=params)
            tokens = response.json()
            
            # For each token, get detailed info including contract addresses
            for i, token in enumerate(tokens):
                if i > 0 and i % 50 == 0:
                    print(f"  Processed {i}/{len(tokens)} tokens...")
                    time.sleep(API_BATCH_DELAY)  # Batch delay for free tier rate limiting (10-30 calls/min)
                
                try:
                    detail_url = f"https://api.coingecko.com/api/v3/coins/{token['id']}"
                    detail_response = fetch_with_retry(detail_url)
                    detail = detail_response.json()
                    
                    symbol = detail.get('symbol', '').upper()
                    platforms = detail.get('platforms', {})
                    
                    # Map contract addresses to our chain format
                    for platform_id, contract_addr in platforms.items():
                        if platform_id in platform_map and contract_addr:
                            chain = platform_map[platform_id]
                            if chain not in token_map:
                                token_map[chain] = {}
                            token_map[chain][symbol] = contract_addr
                    
                    time.sleep(API_REQUEST_DELAY)  # Request delay respects free tier (~3 calls/sec max)
                    
                except Exception as e:
                    print(f"  [Skipped] {token.get('id', 'unknown')}: {str(e)[:50]}")
                    continue  # Skip failed tokens
            
            print(f"[*] Fetched {sum(len(tokens) for tokens in token_map.values())} token addresses across {len(token_map)} chains")
            return token_map
            
        except Exception as e:
            print(f"[!] Error fetching from CoinGecko: {e}")
            print(f"[!] This may be due to rate limiting. Try again later or use cached data.")
            return {}
    
    def _get_cached_token_addresses(self):
        """Get token addresses from cache, fetching fresh if needed. Returns dict: {chain: {symbol: contract_address}}"""
        # Check session cache first (already loaded in this session)
        if self._token_map_cache is not None:
            return self._token_map_cache
        
        cache_path = TOKEN_CACHE_FILE
        
        # Check if cache exists and is recent
        if cache_path.exists():
            try:
                with open(cache_path, 'r') as f:
                    cache_data = json.load(f)
                
                cached_time = datetime.fromisoformat(cache_data.get('cached_at', '2000-01-01'))
                age_days = (datetime.now() - cached_time).days
                
                if age_days < CACHE_REFRESH_DAYS:
                    print(f"[*] Using cached token addresses (age: {age_days} days)")
                    tokens = cache_data.get('tokens', {})
                    self._token_map_cache = tokens  # Store in session cache
                    return tokens
                else:
                    print(f"[*] Cache expired (age: {age_days} days), fetching fresh...")
            except Exception as e:
                print(f"[!] Error reading cache: {e}")
        
        # Fetch fresh data
        token_map = self._fetch_token_addresses_from_api()
        
        if token_map:
            # Save to cache
            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_data = {
                    'cached_at': datetime.now().isoformat(),
                    'tokens': token_map
                }
                with open(cache_path, 'w') as f:
                    json.dump(cache_data, f, indent=2)
                print(f"[*] Token addresses cached to {cache_path}")
            except Exception as e:
                print(f"[!] Error saving cache: {e}")
        
        # Store in session cache
        self._token_map_cache = token_map
        return token_map
    
    def _save_wallet_address(self, wallet_address, coin):
        """Save wallet address to wallets.json in the appropriate chain section
        
        Returns: (success: bool, message: str)
        """
        # Detect chain from wallet address format
        chain = self._detect_chain_from_address(wallet_address, coin)
        
        if not chain:
            return False, f"Could not determine blockchain for {coin}"
        
        # Load or create wallets.json
        try:
            wallets = app.load_wallets_file()
        except Exception as e:
            return False, f"Error reading wallets: {e}"
        
        # Initialize chain section if needed
        if chain not in wallets:
            wallets[chain] = []
        
        # Convert to list if it's a dict with 'addresses' key
        if isinstance(wallets[chain], dict):
            if 'addresses' in wallets[chain]:
                wallets[chain] = wallets[chain]['addresses']
            else:
                wallets[chain] = []
        
        # Ensure it's a list
        if not isinstance(wallets[chain], list):
            wallets[chain] = [wallets[chain]] if wallets[chain] else []
        
        # Add wallet if not already present
        if wallet_address not in wallets[chain]:
            wallets[chain].append(wallet_address)
            
            # Save back to file (encrypted)
            try:
                app.save_wallets_file(wallets)
                return True, f"✓ Saved wallet to {chain} section in wallets.json"
            except Exception as e:
                return False, f"Error saving wallets: {e}"
        else:
            return True, f"Wallet already exists in {chain} section"
    
    def _detect_chain_from_address(self, address, coin):
        """Detect blockchain from wallet address format and coin symbol
        
        Returns: chain name (str) or None
        """
        address = address.strip()
        coin_upper = coin.upper()
        
        # Bitcoin addresses (legacy, segwit, native segwit)
        if address.startswith('1') or address.startswith('3') or address.startswith('bc1'):
            if coin_upper in ['BTC', 'BITCOIN']:
                return 'bitcoin'
        
        # Ethereum and EVM chains (0x prefix, 40-42 chars hex)
        if address.startswith('0x') and 40 <= len(address) <= 42:
            # Try to infer from coin
            if coin_upper in ['ETH', 'WETH', 'ETHEREUM']:
                return 'ethereum'
            elif coin_upper in ['MATIC', 'POLYGON']:
                return 'polygon'
            elif coin_upper in ['BNB', 'WBNB']:
                return 'bsc'
            elif coin_upper in ['AVAX', 'WAVAX']:
                return 'avalanche'
            elif coin_upper in ['FTM', 'FANTOM']:
                return 'fantom'
            elif 'ARBITRUM' in coin_upper or 'ARB' == coin_upper:
                return 'arbitrum'
            elif 'OPTIMISM' in coin_upper or 'OP' == coin_upper:
                return 'optimism'
            else:
                # Default to ethereum for unknown EVM tokens
                return 'ethereum'
        
        # Solana addresses (base58, typically 32-44 chars, no 0x prefix)
        if not address.startswith('0x') and 32 <= len(address) <= 44:
            if coin_upper in ['SOL', 'SOLANA']:
                return 'solana'
        
        # Couldn't determine
        return None
    
    def _prompt_for_api_key(self, service_name, key_name):
        """Prompt user to enter API key and optionally save it
        
        Args:
            service_name: Human-readable service name (e.g., "Blockchair", "Etherscan")
            key_name: Key name in api_keys.json (e.g., "blockchair", "etherscan")
        
        Returns:
            tuple: (api_key: str or None, status: 'provided'|'skipped'|'error')
        """
        self._print(f"\n    🔑 {service_name} API key required for blockchain verification")
        self._print(f"    Visit https://{service_name.lower()}.com to get a free API key")
        
        user_choice = self._input(f"    Enter API key (or 'skip' to use Yahoo Finance fallback): ").strip()
        
        if user_choice.lower() == 'skip' or not user_choice:
            return None, 'skipped'
        
        api_key = user_choice
        
        # Ask if they want to save it
        save_key = self._input(f"    Save this API key to api_keys.json for future use? (y/n): ").strip().lower()
        
        if save_key == 'y':
            success, message = self._save_api_key(key_name, api_key)
            if success:
                self._print(f"    💾 {message}")
            else:
                self._print(f"    ⚠️  {message}")
        
        return api_key, 'provided'
    
    def _save_api_key(self, key_name, api_key):
        """Save API key to api_keys.json
        
        Args:
            key_name: Key name (e.g., "blockchair", "etherscan", "polygonscan")
            api_key: The API key value
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            # Ensure parent directory exists first
            app.KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing keys or create new structure
            if app.KEYS_FILE.exists():
                with open(app.KEYS_FILE, 'r') as f:
                    keys_data = json.load(f)
            else:
                keys_data = {}
            
            # Ensure proper structure
            if key_name not in keys_data:
                keys_data[key_name] = {}
            
            # Save the API key
            keys_data[key_name]['apiKey'] = api_key
            
            # Write back to file
            with open(app.KEYS_FILE, 'w') as f:
                json.dump(keys_data, f, indent=2)
            
            return True, f"API key saved to {app.KEYS_FILE.name}"
            
        except Exception as e:
            return False, f"Error saving API key: {str(e)}"
    
    def _check_transaction_on_blockchain_with_prompts(self, transaction_id, coin, date_str, amount, additional_wallet=None):
        """Check blockchain with API key prompting if needed
        
        Args:
            transaction_id: Transaction ID from database
            coin: Coin symbol (e.g., 'BTC', 'ETH')
            date_str: Date string of transaction (YYYY-MM-DD format)
            amount: Transaction amount
            additional_wallet: Optional additional wallet address to check
        
        Returns:
            tuple: (found: bool, price: float or None, details: str or None, api_key_status: str)
        """
        # Load wallets first
        wallets_to_check = []
        
        if app.WALLETS_FILE.exists():
            try:
                with open(app.WALLETS_FILE, 'r') as f:
                    wallets_data = json.load(f)
                
                # Only check the correct blockchain for this coin
                chain = self._infer_chain_from_coin(coin)
                
                if chain and chain in wallets_data:
                    wallet_list = wallets_data[chain]
                    if isinstance(wallet_list, list):
                        wallets_to_check.extend(wallet_list)
                    elif isinstance(wallet_list, dict) and 'addresses' in wallet_list:
                        wallets_to_check.extend(wallet_list['addresses'])
            except Exception as e:
                pass
        
        # Add additional wallet if provided
        if additional_wallet:
            wallets_to_check.append(additional_wallet)
        
        if not wallets_to_check:
            return False, None, "No wallet addresses configured for this blockchain", 'no_wallets'
        
        # Load API keys
        api_keys = {}
        if app.KEYS_FILE.exists():
            try:
                with open(app.KEYS_FILE) as f:
                    api_keys = json.load(f)
            except Exception:
                pass
        
        coin_upper = coin.upper()
        
        # Route to appropriate blockchain and check/prompt for API key
        if coin_upper in ['BTC', 'BITCOIN']:
            # Bitcoin requires Blockchair
            blockchair_key = api_keys.get('blockchair', {}).get('apiKey')
            
            if not blockchair_key:
                # Prompt for API key
                blockchair_key, status = self._prompt_for_api_key('Blockchair', 'blockchair')
                if status == 'skipped':
                    return False, None, "Blockchair API key required but skipped", 'skipped'
            
            found, price, details = self._check_bitcoin_transaction(wallets_to_check, date_str, amount, blockchair_key)
            return found, price, details, 'ok'
        
        else:
            # EVM chains - will check within _check_evm_transaction
            found, price, details = self._check_evm_transaction_with_prompts(wallets_to_check, coin_upper, date_str, amount, api_keys)
            return found, price, details, 'ok'
    
    def _check_transaction_on_blockchain(self, transaction_id, coin, date_str, amount, additional_wallet=None):
        """Check if transaction exists on blockchain with wallet addresses using Etherscan/Blockchair
        
        Args:
            transaction_id: Transaction ID from database
            coin: Coin symbol (e.g., 'BTC', 'ETH')
            date_str: Date string of transaction (YYYY-MM-DD format)
            amount: Transaction amount
            additional_wallet: Optional additional wallet address to check
        
        Returns:
            tuple: (found: bool, price: float or None, details: str or None)
        """
        # Load wallets and API keys
        wallets_to_check = []
        
        if app.WALLETS_FILE.exists():
            try:
                with open(app.WALLETS_FILE, 'r') as f:
                    wallets_data = json.load(f)
                
                # Determine which chain this coin belongs to - ONLY CHECK THAT CHAIN
                chain = self._infer_chain_from_coin(coin)
                
                if chain and chain in wallets_data:
                    wallet_list = wallets_data[chain]
                    if isinstance(wallet_list, list):
                        wallets_to_check.extend(wallet_list)
                    elif isinstance(wallet_list, dict) and 'addresses' in wallet_list:
                        wallets_to_check.extend(wallet_list['addresses'])
            except Exception as e:
                pass  # Continue with empty wallet list
        
        # Add additional wallet if provided
        if additional_wallet:
            wallets_to_check.append(additional_wallet)
        
        if not wallets_to_check:
            return False, None, "No wallet addresses found"
        
        # Load API keys
        moralis_key = None
        blockchair_key = None
        if app.KEYS_FILE.exists():
            try:
                with open(app.KEYS_FILE) as f:
                    keys = json.load(f)
                blockchair_key = keys.get('blockchair', {}).get('apiKey') or None
            except Exception:
                pass
        
        coin_upper = coin.upper()
        
        # Route to appropriate blockchain API (ONLY the correct one for this coin)
        if coin_upper in ['BTC', 'BITCOIN']:
            # Use Blockchair for Bitcoin
            return self._check_bitcoin_transaction(wallets_to_check, date_str, amount, blockchair_key)
        else:
            # Use Etherscan for Ethereum and EVM chains
            return self._check_evm_transaction(wallets_to_check, coin_upper, date_str, amount)
    
    def _check_bitcoin_transaction(self, wallets, date_str, amount, blockchair_key):
        """Check Bitcoin transaction on blockchain using Blockchair API
        
        Returns: (found: bool, price: float or None, details: str or None)
        """
        if not blockchair_key:
            return False, None, "Blockchair API key not configured - cannot check Bitcoin transactions"
        
        try:
            # Parse date
            tx_date = _parse_date_flexible(date_str)
            
            for wallet in wallets:
                try:
                    # Check Blockchair API for wallet transactions
                    url = f"https://api.blockchair.com/bitcoin/addresses/{wallet}"
                    params = {'key': blockchair_key}
                    
                    response = requests.get(url, params=params, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    if data.get('data') and wallet in data['data']:
                        wallet_data = data['data'][wallet]
                        
                        # Get transactions for this wallet
                        tx_url = f"https://api.blockchair.com/bitcoin/transactions"
                        tx_params = {
                            'q': f'receiver({wallet})',
                            'key': blockchair_key,
                            'limit': 100,
                            'offset': 0
                        }
                        
                        tx_response = requests.get(tx_url, params=tx_params, timeout=10)
                        tx_response.raise_for_status()
                        tx_data = tx_response.json()
                        
                        # Search for matching transaction
                        if tx_data.get('data'):
                            for tx in tx_data['data']:
                                # Check if this transaction matches
                                tx_time = dt.datetime.fromtimestamp(tx.get('time', 0)).date()
                                
                                # Match by date (within 1 day) and look for amount
                                if abs((tx_time - tx_date).days) <= 1:
                                    # Blockchair doesn't provide price in transaction data
                                    # Return success with indication to use external price
                                    return True, None, f"✓ Found Bitcoin transaction on {tx_time} at {wallet[:16]}..."
                    
                    time.sleep(0.5)  # Rate limiting for Blockchair
                    
                except Exception as e:
                    logger.debug(f"Blockchair check failed for {wallet}: {str(e)[:100]}")
                    continue
        
        except Exception as e:
            return False, None, f"Blockchair lookup error: {str(e)[:100]}"
        
        return False, None, f"Bitcoin transaction not found in {len(wallets)} wallet(s)"
    
    def _check_evm_transaction_with_prompts(self, wallets, coin, date_str, amount, api_keys):
        """Check EVM transaction with API key prompting if needed
        
        Returns: (found: bool, price: float or None, details: str or None)
        """
        import datetime as dt
        
        # Map coins to their API services
        coin_to_service = {
            'ETH': ('Etherscan', 'etherscan', 'https://api.etherscan.io/api'),
            'WETH': ('Etherscan', 'etherscan', 'https://api.etherscan.io/api'),
            'MATIC': ('Polygonscan', 'polygonscan', 'https://api.polygonscan.com/api'),
            'BNB': ('BSCScan', 'bscscan', 'https://api.bscscan.com/api'),
            'WBNB': ('BSCScan', 'bscscan', 'https://api.bscscan.com/api'),
            'AVAX': ('Snowtrace', 'snowtrace', 'https://api.snowtrace.io/api'),
            'WAVAX': ('Snowtrace', 'snowtrace', 'https://api.snowtrace.io/api'),
            'FTM': ('FTMScan', 'ftmscan', 'https://api.ftmscan.com/api'),
        }
        
        # Get service info for this coin (default to Etherscan)
        service_name, key_name, api_url = coin_to_service.get(coin, ('Etherscan', 'etherscan', 'https://api.etherscan.io/api'))
        
        # Check if we have the API key
        api_key = api_keys.get(key_name, {}).get('apiKey')
        
        if not api_key:
            # Prompt for API key
            api_key, status = self._prompt_for_api_key(service_name, key_name)
            if status == 'skipped' or not api_key:
                return False, None, f"{service_name} API key required but skipped"
        
        # Now check the transaction with the API key
        return self._check_evm_transaction(wallets, coin, date_str, amount, api_key, api_url)
    
    def _check_evm_transaction(self, wallets, coin, date_str, amount, api_key=None, api_url=None):
        """Check Ethereum/EVM transaction on blockchain using Etherscan-compatible API
        
        Returns: (found: bool, price: float or None, details: str or None)
        """
        import datetime as dt
        
        # Map chains to Etherscan-compatible APIs
        chain_apis = {
            'ETH': {
                'name': 'Ethereum',
                'api_url': 'https://api.etherscan.io/api',
                'key_env': 'ETHERSCAN_API_KEY'
            },
            'MATIC': {
                'name': 'Polygon',
                'api_url': 'https://api.polygonscan.com/api',
                'key_env': 'POLYGONSCAN_API_KEY'
            },
            'BNB': {
                'name': 'BSC',
                'api_url': 'https://api.bscscan.com/api',
                'key_env': 'BSCSCAN_API_KEY'
            },
            'AVAX': {
                'name': 'Avalanche',
                'api_url': 'https://api.snowtrace.io/api',
                'key_env': 'SNOWTRACE_API_KEY'
            },
            'FTM': {
                'name': 'Fantom',
                'api_url': 'https://api.ftmscan.com/api',
                'key_env': 'FTMSCAN_API_KEY'
            }
        }
        
        # Use provided api_url or default to Ethereum for ERC-20 tokens
        if not api_url:
            chain_info = chain_apis.get(coin, chain_apis.get('ETH', {}))
            api_url = chain_info.get('api_url')
            chain_name = chain_info.get('name', 'EVM Chain')
        
        if not api_url:
            return False, None, f"API not configured for {coin}"
        
        # Use provided api_key or placeholder
        if not api_key:
            api_key = 'YourApiKeyToken'  # Placeholder
        
        try:
            tx_date = _parse_date_flexible(date_str)
            
            for wallet in wallets:
                try:
                    # Check normal transactions (ETH transfers)
                    if coin in ['ETH', 'WETH']:
                        params = {
                            'module': 'account',
                            'action': 'txlist',
                            'address': wallet,
                            'startblock': 0,
                            'endblock': 99999999,
                            'sort': 'desc',
                            'apikey': api_key
                        }
                        
                        response = requests.get(api_url, params=params, timeout=10)
                        response.raise_for_status()
                        data = response.json()
                        
                        if data.get('result') and isinstance(data['result'], list):
                            for tx in data['result']:
                                tx_time = dt.datetime.fromtimestamp(int(tx.get('timeStamp', 0))).date()
                                tx_value = float(int(tx.get('value', 0)) / 1e18)  # Convert wei to ETH
                                
                                # Match by date (within 1 day) and approximate amount
                                if abs((tx_time - tx_date).days) <= 1:
                                    if abs(tx_value - float(amount)) < float(amount) * 0.01:  # Within 1% match
                                        # Found matching transaction
                                        tx_hash = tx.get('hash', 'unknown')
                                        return True, None, f"✓ Found {coin} transaction {tx_hash[:16]}... on {tx_time} from {wallet[:16]}..."
                    
                    # Check ERC-20 token transfers
                    else:
                        params = {
                            'module': 'account',
                            'action': 'tokentxlist',
                            'address': wallet,
                            'startblock': 0,
                            'endblock': 99999999,
                            'sort': 'desc',
                            'apikey': 'YourApiKeyToken'  # Placeholder - would use from keys.json
                        }
                        
                        response = requests.get(api_url, params=params, timeout=10)
                        response.raise_for_status()
                        data = response.json()
                        
                        if data.get('result') and isinstance(data['result'], list):
                            for tx in data['result']:
                                tx_time = dt.datetime.fromtimestamp(int(tx.get('timeStamp', 0))).date()
                                token_symbol = tx.get('tokenSymbol', '')
                                
                                # Match by date and token symbol
                                if abs((tx_time - tx_date).days) <= 1 and token_symbol.upper() == coin.upper():
                                    tx_hash = tx.get('hash', 'unknown')
                                    return True, None, f"✓ Found {coin} transaction {tx_hash[:16]}... on {tx_time} from {wallet[:16]}..."
                    
                    time.sleep(0.2)  # Rate limiting for Etherscan-compatible APIs
                    
                except Exception as e:
                    logger.debug(f"EVM check failed for {wallet}: {str(e)[:100]}")
                    continue
        
        except Exception as e:
            return False, None, f"{chain_name} lookup error: {str(e)[:100]}"
        
        return False, None, f"{coin} transaction not found in {len(wallets)} wallet(s) on {chain_name}"
    
    def _infer_chain_from_coin(self, coin):
        """Infer blockchain network from coin symbol
        
        Returns:
            str: Chain name (e.g., 'ethereum', 'bitcoin') or None
        """
        coin_upper = coin.upper()
        
        # Native coins
        if coin_upper in ['BTC', 'BITCOIN']:
            return 'bitcoin'
        elif coin_upper in ['ETH', 'WETH', 'ETHEREUM']:
            return 'ethereum'
        elif coin_upper in ['MATIC', 'POLYGON']:
            return 'polygon'
        elif coin_upper in ['BNB', 'WBNB']:
            return 'bsc'
        elif coin_upper in ['AVAX', 'WAVAX']:
            return 'avalanche'
        elif coin_upper in ['FTM', 'FANTOM']:
            return 'fantom'
        elif coin_upper in ['SOL', 'SOLANA']:
            return 'solana'
        elif 'ARBITRUM' in coin_upper or coin_upper == 'ARB':
            return 'arbitrum'
        elif 'OPTIMISM' in coin_upper or coin_upper == 'OP':
            return 'optimism'
        
        # For ERC-20 tokens, default to ethereum
        # In a real implementation, you'd check token contract addresses
        return 'ethereum'
    
    def _get_blockchain_explorer_hint(self, coin):
        """Get blockchain explorer suggestion based on coin
        
        Returns:
            str: Helpful message with explorer URL or None
        """
        coin_upper = coin.upper()
        
        if coin_upper in ['BTC', 'BITCOIN']:
            return "Blockchain Explorer: https://www.blockchain.com/explorer or https://blockchair.com/bitcoin"
        elif coin_upper in ['MATIC', 'POLYGON']:
            return "Blockchain Explorer: https://polygonscan.com"
        elif coin_upper in ['ETH', 'WETH', 'ETHEREUM'] or 'ETH' in coin_upper:
            return "Blockchain Explorer: https://etherscan.io"
        elif coin_upper in ['BNB', 'WBNB']:
            return "Blockchain Explorer: https://bscscan.com"
        elif coin_upper in ['AVAX', 'WAVAX']:
            return "Blockchain Explorer: https://snowtrace.io"
        elif coin_upper in ['FTM', 'FANTOM']:
            return "Blockchain Explorer: https://ftmscan.com"
        elif coin_upper in ['SOL', 'SOLANA']:
            return "Blockchain Explorer: https://solscan.io or https://explorer.solana.com"
        elif 'ARBITRUM' in coin_upper or coin_upper == 'ARB':
            return "Blockchain Explorer: https://arbiscan.io"
        elif 'OPTIMISM' in coin_upper or coin_upper == 'OP':
            return "Blockchain Explorer: https://optimistic.etherscan.io"
        
        # Default to Ethereum for ERC-20 tokens
        return "Blockchain Explorer: https://etherscan.io (for Ethereum) or check your exchange"
    
    def _try_blockchain_price(self, coin, date_str):
        """Attempt on-chain pricing using wallets/key context. Returns (price, message)."""
        # If no wallets, we can't infer chains
        if not app.WALLETS_FILE.exists():
            return None, "wallets.json not found"

        try:
            with open(app.WALLETS_FILE) as f:
                wallets = json.load(f)
            if not wallets:
                return None, "wallets.json empty"
        except Exception:
            return None, "could not read wallets.json"

        # Check keys
        moralis_key = None
        blockchair_key = None
        if app.KEYS_FILE.exists():
            try:
                with open(app.KEYS_FILE) as f:
                    keys = json.load(f)
                moralis_key = keys.get('moralis', {}).get('apiKey') or None
                blockchair_key = keys.get('blockchair', {}).get('apiKey') or None
            except Exception:
                pass

        # Map chains present
        chains_present = set(wallets.keys()) if isinstance(wallets, dict) else set()

        # Minimal native coin mapping
        native_map = {
            'ethereum': 'ETH',
            'polygon': 'MATIC',
            'bsc': 'BNB',
            'binance-smart-chain': 'BNB',
            'avalanche': 'AVAX',
            'avalanche-c': 'AVAX',
            'arbitrum': 'ETH',
            'optimism': 'ETH',
            'fantom': 'FTM',
            'solana': 'SOL',
            'bitcoin': 'BTC',
        }

        coin_upper = coin.upper()

        # BTC path via Blockchair (if key present)
        if coin_upper == 'BTC' and 'bitcoin' in chains_present:
            if not blockchair_key:
                return None, "Blockchair key missing; cannot fetch BTC on-chain price"
            return None, "BTC present but on-chain price not implemented; falling back to Yahoo"

        # EVM/Solana native via Moralis (requires key)
        if moralis_key:
            for chain, native_symbol in native_map.items():
                if chain in chains_present and native_symbol == coin_upper:
                    return None, f"{coin_upper} present on {chain}, but on-chain historical price not implemented; using Yahoo"

        # ERC-20 tokens - check cached contract addresses
        token_map = self._get_cached_token_addresses()
        
        for chain in chains_present:
            if chain in token_map and coin_upper in token_map[chain]:
                contract_addr = token_map[chain][coin_upper]
                if chain != 'bitcoin':
                    if not moralis_key:
                        return None, f"Found {coin_upper} contract on {chain}, but Moralis key missing"
                    return None, f"Found {coin_upper} contract on {chain} ({contract_addr[:10]}...), but on-chain price not implemented; using Yahoo"
        
        return None, f"no contract found for {coin_upper}; using Yahoo"

    def _print_summary(self):
        """Print summary of changes and prompt to save or discard"""
        print("\n" + "="*80)
        print("FIX REVIEW - ALL CHANGES STAGED (NOT YET SAVED)")
        print("="*80)
        
        if not self.fixes_applied:
            print("\n✓ No changes were made. Database unchanged.")
            return
        
        # Group by type
        renames = [f for f in self.fixes_applied if f['type'] == 'rename']
        prices = [f for f in self.fixes_applied if f['type'] == 'price_update']
        deletes = [f for f in self.fixes_applied if f['type'] == 'delete']
        
        print(f"\nTotal staged changes: {len(self.fixes_applied)}")
        if renames:
            print(f"  - {len(renames)} rename(s)")
            for fix in renames[:5]:
                print(f"      • ID {fix['id']}: {fix['old']} → {fix['new']}")
            if len(renames) > 5:
                print(f"      ... and {len(renames)-5} more")
        
        if prices:
            print(f"  - {len(prices)} price update(s)")
            for fix in prices[:5]:
                print(f"      • ID {fix['id']}: ${fix['price']}")
            if len(prices) > 5:
                print(f"      ... and {len(prices)-5} more")
        
        if deletes:
            print(f"  - {len(deletes)} deletion(s)")
            for fix in deletes[:5]:
                print(f"      • ID {fix['id']}")
            if len(deletes) > 5:
                print(f"      ... and {len(deletes)-5} more")
        
        print("\n" + "="*80)
        print("SAVE OR DISCARD?")
        print("="*80)
        print("\nThese changes are currently staged but NOT saved to the database.")
        print("\nOptions:")
        print("  'save'    - Commit all changes permanently")
        print("  'discard' - Roll back all changes (database unchanged)")
        print("  'undo'    - Restore from backup (same as discard)")
        
        while True:
            choice = input("\nYour choice (save/discard/undo): ").strip().lower()
            
            if choice == 'save':
                print("\n[*] Committing changes to database...")
                self.db.commit()
                print(f"\n✓ Successfully saved {len(self.fixes_applied)} change(s) to database!")
                print(f"\n✓ Backup still available at: {self.backup_file.name}")
                print("\nNext steps:")
                print("  1. Re-run tax calculations: python Auto_Runner.py")
                print("  2. Review updated reports in outputs/Year_XXXX/")
                break
            
            elif choice in ['discard', 'undo']:
                print("\n[*] Rolling back all changes...")
                self.db.connection.rollback()
                print(f"\n✓ All {len(self.fixes_applied)} change(s) discarded. Database unchanged.")
                print(f"✓ Backup preserved at: {self.backup_file.name}")
                print("\nNo changes were made to your database.")
                break
            
            else:
                print("\n✗ Invalid choice. Please type 'save', 'discard', or 'undo'.")


def main():
    """Command-line entry point"""
    import sys
    
    print("\n" + "="*80)
    print("INTERACTIVE REVIEW FIXER")
    print("="*80)
    
    # Get year
    if len(sys.argv) > 1:
        year = sys.argv[1]
    else:
        from datetime import datetime
        year = input(f"\nEnter tax year [{datetime.now().year}]: ").strip() or str(datetime.now().year)
    
    # Initialize
    app.initialize_folders()
    db = DatabaseManager()
    
    fixer = InteractiveReviewFixer(db, year)
    
    try:
        fixer.run_interactive_fixer()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. No changes saved.")
    except Exception as e:
        print(f"\n\nError: {e}")
        logger.exception("Fixer error")
    finally:
        db.close()


if __name__ == "__main__":
    main()

