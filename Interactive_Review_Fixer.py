"""
Interactive Review Fixer - Fix issues detected by Tax Reviewer
Provides guided, interactive fixing of audit risk warnings.
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from decimal import Decimal
import pandas as pd
import requests
import time
import Crypto_Tax_Engine as app
from Crypto_Tax_Engine import DatabaseManager, logger, WALLETS_FILE, KEYS_FILE

# Token address cache configuration
TOKEN_CACHE_FILE = Path("configs/cached_token_addresses.json")
CACHE_REFRESH_DAYS = 7  # Refresh cache every 7 days

class InteractiveReviewFixer:
    """Interactive tool to fix issues detected by Tax Reviewer"""
    
    def __init__(self, db, year):
        self.db = db
        self.year = year
        self.fixes_applied = []
        self.backup_file = None
        self._token_map_cache = None  # Session-level cache to avoid repeated API calls
        
    def load_review_report(self, report_path=None):
        """Load the most recent review report"""
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
        """Guided fix for missing prices - show suggestions and let user accept/override"""
        print("\n--- GUIDED FIX: MISSING PRICES ---")
        print("For each transaction, we'll show suggested prices from available sources.")
        print("You can accept (Enter), override (number), or skip (type 'skip').\n")
        
        from Crypto_Tax_Engine import PriceFetcher
        fetcher = PriceFetcher()

        for item in warning['items']:
            coin = item['coin']
            date_str = str(item['date']).split()[0]

            # 1) Try blockchain context (if wallets available)
            bc_price, bc_msg = self._try_blockchain_price(coin, date_str)

            # 2) Yahoo Finance fallback
            yf_price = None
            try:
                yf_price = fetcher.get_price(coin, pd.to_datetime(date_str))
            except Exception as e:
                yf_price = None

            # Pick best suggestion
            suggested_price = bc_price if bc_price is not None else yf_price

            print(f"\n  {coin} on {date_str} (amount: {item['amount']})")
            if bc_price is not None:
                print(f"    On-chain price: ${bc_price}")
            else:
                print(f"    On-chain: {bc_msg}")

            if yf_price is not None and yf_price > 0:
                print(f"    Yahoo Finance: ${yf_price}")
            else:
                print("    Yahoo Finance: unavailable")

            if suggested_price is not None and suggested_price > 0:
                print(f"    → Suggested: ${suggested_price}")
            else:
                print("    → Suggested: unavailable (enter manually or skip)")

            user_input = input("    (Enter=accept, number=override, 'skip'=skip this, 'skip-all'=skip all remaining): ").strip()

            if user_input.lower() == 'skip-all':
                print("\n[SKIPPED] Remaining missing prices will appear again next time you run the fixer.")
                break
            elif user_input.lower() == 'skip':
                print("    → Skipped this transaction")
                continue
            elif user_input == '' and suggested_price is not None and suggested_price > 0:
                self._update_price(item['id'], suggested_price)
                print(f"    ✓ Set to ${suggested_price}")
            else:
                try:
                    manual_price = Decimal(user_input)
                    self._update_price(item['id'], manual_price)
                    print(f"    ✓ Set to ${manual_price}")
                except:
                    print("    ✗ Invalid input, skipped this transaction")
        print("1. Guided fix (fetch suggestions, approve/override per item)")
        print("2. Set custom price for each transaction")
        print("3. Set all to $0 (mark as basis-only, no income)")
        print("4. Delete transactions (if spam/invalid)")
        print("5. Skip")

        choice = input("\nSelect option (1-5): ").strip()

        if choice == '1':
            print("\n  Fetching suggested prices...")
            from Crypto_Tax_Engine import PriceFetcher
            fetcher = PriceFetcher()

            for item in warning['items']:
                coin = item['coin']
                date_str = str(item['date']).split()[0]

                # 1) Try blockchain context (if wallets available)
                bc_price, bc_msg = self._try_blockchain_price(coin, date_str)

                # 2) Yahoo Finance fallback
                yf_price = None
                try:
                    yf_price = fetcher.get_price(coin, pd.to_datetime(date_str))
                except Exception as e:
                    yf_price = None
                    print(f"  ✗ {coin} ({date_str}): error fetching Yahoo price - {e}")

                # Pick best suggestion
                suggested_price = bc_price if bc_price is not None else yf_price

                print(f"\n  {coin} on {date_str} (amount: {item['amount']})")
                if bc_price is not None:
                    print(f"    On-chain price (wallets present): ${bc_price} ({bc_msg})")
                else:
                    print(f"    On-chain price: unavailable ({bc_msg})")

                if yf_price is not None and yf_price > 0:
                    print(f"    Yahoo Finance: ${yf_price}")
                else:
                    print("    Yahoo Finance: unavailable")

                if suggested_price is not None and suggested_price > 0:
                    print(f"    Suggested: ${suggested_price}")
                else:
                    print("    Suggested: unavailable")

                user_input = input("    Accept suggested? (Enter=accept, number=override, 'skip'=skip): ").strip()

                if user_input.lower() == 'skip':
                    print("    Skipped.")
                    continue
                elif user_input == '' and suggested_price is not None and suggested_price > 0:
                    self._update_price(item['id'], suggested_price)
                    print(f"    ✓ Set to ${suggested_price}")
                else:
                    try:
                        manual_price = Decimal(user_input)
                        self._update_price(item['id'], manual_price)
                        print(f"    ✓ Set to ${manual_price}")
                    except:
                        print("    ✗ Invalid input, skipped.")

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

        elif choice == '3':
            confirm = input("  Set all to $0? This means no taxable income. (yes/no): ").strip().lower()
            if confirm in ['yes', 'y']:
                for item in warning['items']:
                    self._update_price(item['id'], 0)
                print(f"  ✓ Set {len(warning['items'])} price(s) to $0")

        elif choice == '4':
            print("\n  WARNING: This will permanently delete transactions!")
            confirm = input("  Are you sure? Type 'DELETE' to confirm: ").strip()
            if confirm == 'DELETE':
                for item in warning['items']:
                    self._delete_transaction(item['id'])
                print(f"  ✓ Deleted {len(warning['items'])} transaction(s)")
            else:
                print("  Deletion cancelled.")

        elif choice == '5':
            print("\n[SKIPPED] This warning will appear again next time you run the fixer.")
            print("Fix the underlying issue to resolve this warning permanently.")

        else:
            print("\n[SKIPPED] Invalid choice. This warning will appear again next time.")
    
    def _guided_fix_duplicates(self, warning):
        """Guided fix for duplicate transactions - review each group"""
        print("\n--- GUIDED FIX: DUPLICATES ---")
        print("Review each duplicate group and choose which transaction to keep.\n")
        
        for item in warning['items']:
            ids = item['ids']
            print(f"\n  Duplicate group: {item['signature']}")
            
            # Show details of each
            for idx, tid in enumerate(ids, 1):
                trade = self._get_transaction(tid)
                print(f"    {idx}. ID={tid}, Source={trade.get('source')}, Batch={trade.get('batch_id')}")
            
            keep = input(f"  Which one to KEEP? (1-{len(ids)}, 'skip'=skip this group, 'skip-all'=skip all remaining): ").strip()
            
            if keep.lower() == 'skip-all':
                print("\n[SKIPPED] Remaining duplicates will appear again next time you run the fixer.")
                break
            elif keep.lower() == 'skip':
                print("    → Skipped this group")
                continue
            elif keep.isdigit() and 1 <= int(keep) <= len(ids):
                keep_idx = int(keep) - 1
                keep_id = ids[keep_idx]
                
                for idx, tid in enumerate(ids):
                    if idx != keep_idx:
                        self._delete_transaction(tid)
                        print(f"    ✓ Deleted: {tid}")
                
                print(f"    ✓ Kept: {keep_id}")
            else:
                print("    ✗ Invalid choice, skipped this group")
        print("1. Auto-delete duplicates (keep first occurrence)")
        print("2. Review each duplicate and choose which to keep")
        print("3. Skip (review later)")
        
        choice = input("\nSelect option (1-3): ").strip()
        
        if choice == '1':
            for item in warning['items']:
                ids = item['ids']
                keep_id = ids[0]
                delete_ids = ids[1:]
                
                print(f"\n  Keeping: {keep_id}")
                for del_id in delete_ids:
                    self._delete_transaction(del_id)
                    print(f"  ✓ Deleted: {del_id}")
        
        elif choice == '2':
            for item in warning['items']:
                ids = item['ids']
                print(f"\n  Duplicate group: {item['signature']}")
                
                # Show details of each
                for idx, tid in enumerate(ids, 1):
                    trade = self._get_transaction(tid)
                    print(f"    {idx}. ID={tid}, Source={trade.get('source')}, Batch={trade.get('batch_id')}")
                
                keep = input(f"  Which one to KEEP? (1-{len(ids)}) or 'all' to skip: ").strip()
                
                if keep.isdigit() and 1 <= int(keep) <= len(ids):
                    keep_idx = int(keep) - 1
                    keep_id = ids[keep_idx]
                    
                    for idx, tid in enumerate(ids):
                        if idx != keep_idx:
                            self._delete_transaction(tid)
                            print(f"    ✓ Deleted: {tid}")
                    
                    print(f"    ✓ Kept: {keep_id}")
                elif keep.lower() == 'all':
                    print("    Skipped this group")
                else:
                    print("    Invalid choice, skipping group")
        
        elif choice == '3':
            print("\n[SKIPPED] This warning will appear again next time you run the fixer.")
            print("Fix the underlying issue to resolve this warning permanently.")
        
        else:
            print("\n[SKIPPED] Invalid choice. This warning will appear again next time.")
    
    def _guided_fix_high_fees(self, warning):
        """Guided fix for high fee warnings - show details for manual review"""
        print("\n--- GUIDED FIX: HIGH FEES ---")
        print("High fees in processed tax data can't be modified here.")
        print("Review these transactions and fix in your source CSV if needed:\n")
        
        for item in warning['items']:
            print(f"  • {item['coin']} on {item['date']}: Fee = ${item['fee_usd']}")
        
        print("\n  Edit these in your source CSV files and re-import if corrections needed.")
        input("\nPress Enter to continue...")
        print("Note: High fees in processed tax data can't be modified directly.")
        print("You need to fix the source CSV/database and re-run calculations.")
        print("\n1. Show transaction IDs for manual CSV editing")
        print("2. Skip (review later)")
        
        choice = input("\nSelect option (1-2): ").strip()
        
        if choice == '1':
            print("\n  Transaction details:")
            for item in warning['items']:
                print(f"    Date: {item['date']}, Coin: {item['coin']}, Fee: ${item['fee_usd']}")
            print("\n  Edit these in your source CSV and re-import.")
        
        elif choice == '2':
            print("\n[SKIPPED] This warning will appear again next time you run the fixer.")
            print("Fix the underlying issue to resolve this warning permanently.")
        
        else:
            print("\n[SKIPPED] Invalid choice. This warning will appear again next time.")
    
    def _generic_fix_prompt(self, warning):
        """Generic handler for unimplemented fix types"""
        print("\n--- MANUAL REVIEW REQUIRED ---")
        print("This issue type requires manual review.")
        print(f"Please review the {warning['count']} item(s) listed above.")
        
        input("\nPress Enter to continue...")
    
    # Database modification methods
    
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
    
    def _add_note_to_transaction(self, transaction_id, note):
        """Add a note to transaction (if notes column exists, staged)"""
        # Check if notes column exists
        try:
            self.db.cursor.execute("UPDATE trades SET notes = ? WHERE id = ?", (note, transaction_id))
            self.fixes_applied.append({
                'type': 'note',
                'id': transaction_id,
                'note': note
            })
        except:
            # Notes column doesn't exist, skip
            pass
    
    def _get_transaction(self, transaction_id):
        """Get transaction details"""
        result = self.db.cursor.execute("SELECT * FROM trades WHERE id = ?", (transaction_id,))
        row = result.fetchone()
        if row:
            columns = [col[0] for col in result.description]
            return dict(zip(columns, row))
        return {}

    def _fetch_token_addresses_from_api(self):
        """Fetch token contract addresses from CoinGecko API. Returns dict: {chain: {symbol: contract_address}}"""
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
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            tokens = response.json()
            
            # For each token, get detailed info including contract addresses
            for i, token in enumerate(tokens):
                if i > 0 and i % 50 == 0:
                    print(f"  Processed {i}/{len(tokens)} tokens...")
                    time.sleep(1)  # Rate limiting
                
                try:
                    detail_url = f"https://api.coingecko.com/api/v3/coins/{token['id']}"
                    detail_response = requests.get(detail_url, timeout=10)
                    detail_response.raise_for_status()
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
                    
                    time.sleep(0.1)  # Rate limiting between requests
                    
                except Exception:
                    continue  # Skip failed tokens
            
            print(f"[*] Fetched {sum(len(tokens) for tokens in token_map.values())} token addresses across {len(token_map)} chains")
            return token_map
            
        except Exception as e:
            print(f"[!] Error fetching from CoinGecko: {e}")
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
    
    def _try_blockchain_price(self, coin, date_str):
        """Attempt on-chain pricing using wallets/key context. Returns (price, message)."""
        # If no wallets, we can't infer chains
        if not WALLETS_FILE.exists():
            return None, "wallets.json not found"

        try:
            with open(WALLETS_FILE) as f:
                wallets = json.load(f)
            if not wallets:
                return None, "wallets.json empty"
        except Exception:
            return None, "could not read wallets.json"

        # Check keys
        moralis_key = None
        blockchair_key = None
        if KEYS_FILE.exists():
            try:
                with open(KEYS_FILE) as f:
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
            # Historical price via Blockchair market endpoint not implemented here (kept safe offline)
            return None, "BTC present but on-chain price not implemented; falling back to Yahoo"

        # EVM/Solana native via Moralis (requires key)
        if moralis_key:
            # Find any chain that matches this native coin
            for chain, native_symbol in native_map.items():
                if chain in chains_present and native_symbol == coin_upper:
                    # We would call Moralis native price; keep offline-safe placeholder.
                    return None, f"{coin_upper} present on {chain}, but on-chain historical price not implemented; using Yahoo"

        # ERC-20 tokens - check cached contract addresses
        token_map = self._get_cached_token_addresses()
        
        # Check each configured chain for this token
        for chain in chains_present:
            if chain in token_map and coin_upper in token_map[chain]:
                contract_addr = token_map[chain][coin_upper]
                
                # Check if we have Moralis key for EVM chains
                if chain != 'bitcoin':
                    if not moralis_key:
                        return None, f"Found {coin_upper} contract on {chain}, but Moralis key missing"
                    
                    # API infrastructure ready but not implemented yet to keep offline-safe
                    return None, f"Found {coin_upper} contract on {chain} ({contract_addr[:10]}...), but on-chain price not implemented; using Yahoo"
        
        # Token not found in cache
        return None, f"no contract found for {coin_upper}; using Yahoo"
    
    def _export_wash_sale_report(self, warning):
        """Export detailed wash sale report"""
        output_dir = app.OUTPUT_DIR / f"Year_{self.year}"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_dir / f"WASH_SALE_DETAILS_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(warning, f, indent=2, default=str)
        
        return filename
    
    def restore_from_backup(self, backup_path=None):
        """Restore database from backup file"""
        if backup_path is None:
            backup_path = self.backup_file
        
        if not backup_path or not Path(backup_path).exists():
            print(f"\n✗ Backup file not found: {backup_path}")
            return False
        
        try:
            print(f"\n[*] Restoring database from {Path(backup_path).name}...")
            shutil.copy2(backup_path, app.DB_FILE)
            print("\n✓ Database successfully restored from backup!")
            print("\nYou may need to reconnect your DatabaseManager:")
            print("  db = DatabaseManager()")
            print("  db.connect()")
            return True
        except Exception as e:
            print(f"\n✗ Error restoring backup: {e}")
            return False
    
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
        notes = [f for f in self.fixes_applied if f['type'] == 'note']
        
        print(f"\nTotal staged changes: {len(self.fixes_applied)}")
        if renames:
            print(f"  - {len(renames)} rename(s)")
            for fix in renames[:5]:  # Show first 5
                print(f"      • ID {fix['id']}: {fix['old']} → {fix['new']}")
            if len(renames) > 5:
                print(f"      ... and {len(renames)-5} more")
        
        if prices:
            print(f"  - {len(prices)} price update(s)")
            for fix in prices[:5]:  # Show first 5
                print(f"      • ID {fix['id']}: ${fix['price']}")
            if len(prices) > 5:
                print(f"      ... and {len(prices)-5} more")
        
        if deletes:
            print(f"  - {len(deletes)} deletion(s)")
            for fix in deletes[:5]:  # Show first 5
                print(f"      • ID {fix['id']}")
            if len(deletes) > 5:
                print(f"      ... and {len(deletes)-5} more")
        
        if notes:
            print(f"  - {len(notes)} note(s) added")
        
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
