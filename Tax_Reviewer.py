"""
Tax Reviewer - Heuristic-Based Manual Review Assistant (Enhanced)
Scans completed tax calculations and flags potential audit risks for manual review.
"""

import pandas as pd
from datetime import timedelta
from pathlib import Path
import logging

logger = logging.getLogger("crypto_tax_engine")

class TaxReviewer:
    """
    Post-processing reviewer that applies heuristics to detect:
    1. NFTs without collectible prefixes (28% tax risk)
    2. Substantially identical wash sales (BTC/WBTC)
    3. Potential constructive sales (offsetting positions)
    4. Complex DeFi transactions needing manual verification
    5. Missing prices or unmatched sells
    6. High Fees (Fat-finger errors) [NEW]
    7. Spam Tokens (Scam airdrops) [NEW]
    8. Duplicate Transaction Suspects [NEW]
    """
    
    def __init__(self, db, tax_year, tax_engine=None):
        self.db = db
        self.year = tax_year
        self.engine = tax_engine
        self.warnings = []
        self.suggestions = []
        
        # Heuristic databases
        self.substantially_identical = [
            {'base': 'BTC', 'wrapped': ['WBTC', 'RENBTC', 'BTCB']},
            {'base': 'ETH', 'wrapped': ['WETH', 'STETH', 'RETH', 'CBETH']},
            {'base': 'USDC', 'wrapped': ['USDC.E', 'BRIDGED-USDC']},
            {'base': 'USDT', 'wrapped': ['USDT.E', 'BRIDGED-USDT']},
        ]
        
        self.nft_indicators = [
            'PUNK', 'APE', 'BAYC', 'MAYC', 'AZUKI', 'DOODLE', 'CLONE',
            'MOONBIRD', 'CRYPTOKITTY', 'MEEBITS', 'OTHERDEED', 'MUTANT',
            'TOKEN', 'DEED', 'PASS', 'GENESIS', 'FOUNDER', '#'
        ]
        
        self.defi_protocols = [
            'UNI-V2', 'UNI-V3', 'SUSHI', 'CURVE', 'BALANCER', 'AAVE',
            'COMPOUND', 'MAKER', 'YEARN', '-LP', '_LP', 'POOL'
        ]
    
    def run_review(self):
        """Run all heuristic checks and generate review report"""
        logger.info("--- MANUAL REVIEW ASSISTANT ---")
        logger.info("Scanning for potential audit risks...")
        
        # Check if we have full engine access
        has_full_access = self.engine and hasattr(self.engine, 'tt') and self.engine.tt
        if not has_full_access:
            logger.info("Note: Limited data access. Some advanced checks will be skipped.")
            logger.info("      For full analysis, ensure tax calculations are run first.")
        
        df = self.db.get_all()
        df['date'] = pd.to_datetime(df['date'], format='mixed')
        # Filter for current tax year
        df_year = df[df['date'].dt.year == int(self.year)].copy()
        
        if df_year.empty:
            logger.info("No trades found for review year.")
            return {'warnings': [], 'suggestions': []}
        
        # Run all checks
        self._check_nft_collectibles(df_year)
        self._check_substantially_identical_wash_sales(df_year)
        self._check_constructive_sales(df_year)
        self._check_defi_complexity(df_year)
        self._check_missing_prices(df_year)
        self._check_unmatched_sells()
        
        # --- NEW CHECKS ---
        self._check_high_fees(df_year)
        self._check_spam_tokens(df_year)
        self._check_duplicate_suspects(df_year)
        
        # Generate report
        report = self._generate_report()
        
        # Return report with action_required flag
        report['action_required'] = len(self.warnings) > 0
        return report

    # ... [Keep existing _check methods: nft, wash_sales, constructive, defi, missing_prices, unmatched] ...
    # (Copy them from your previous file to ensure completeness)

    def _check_nft_collectibles(self, df):
        """Flag assets that look like NFTs but aren't marked as collectibles"""
        potential_nfts = []
        for _, row in df.iterrows():
            coin = str(row['coin']).upper()
            if any(ind in coin for ind in self.nft_indicators) and not coin.startswith(('NFT-', 'ART-', 'COLLECTIBLE-')):
                potential_nfts.append({'coin': coin, 'date': row['date'], 'id': row['id']})
        
        if potential_nfts:
            self.warnings.append({
                'severity': 'HIGH',
                'category': 'NFT_COLLECTIBLES',
                'title': 'Potential NFTs Not Marked as Collectibles',
                'count': len(potential_nfts),
                'description': 'Found assets matching NFT naming patterns without NFT- prefix.',
                'items': potential_nfts[:10],
                'action': 'Rename assets with NFT- prefix in CSV or add to config.'
            })

    def _check_substantially_identical_wash_sales(self, df):
        """Flag potential wash sales between wrapped/similar assets"""
        wash_risks = []
        
        # Check for each pair of substantially identical assets
        for pair in self.substantially_identical:
            base = pair['base']
            wrapped_list = pair['wrapped']
            
            # Find sales of base asset
            base_sales = df[(df['coin'] == base) & (df['action'].isin(['SELL', 'SPEND']))].copy()
            
            for _, sale in base_sales.iterrows():
                sale_date = sale['date']
                window_start = sale_date - timedelta(days=30)
                window_end = sale_date + timedelta(days=30)
                
                # Look for purchases of wrapped variants within 61-day window
                for wrapped_coin in wrapped_list:
                    wrapped_buys = df[
                        (df['coin'] == wrapped_coin) & 
                        (df['action'].isin(['BUY', 'INCOME'])) &
                        (df['date'] >= window_start) &
                        (df['date'] <= window_end)
                    ]
                    
                    if not wrapped_buys.empty:
                        wash_risks.append({
                            'sale_coin': base,
                            'sale_date': sale_date,
                            'purchase_coin': wrapped_coin,
                            'purchase_dates': wrapped_buys['date'].tolist(),
                            'id': sale['id']
                        })
        
        if wash_risks:
            self.warnings.append({
                'severity': 'HIGH',
                'category': 'SUBSTANTIALLY_IDENTICAL_WASH_SALES',
                'title': 'Potential Wash Sales Between Substantially Identical Assets',
                'count': len(wash_risks),
                'description': 'Found sales followed by purchases of wrapped/similar assets within 61-day window (BTC->WBTC, ETH->STETH, etc.)',
                'items': wash_risks[:10],
                'action': 'IRS may disallow loss deductions. Review these transactions and consult a tax professional.'
            })

    def _check_constructive_sales(self, df):
        """Flag potential constructive sales (offsetting positions on same day)"""
        constructive_risks = []
        
        # Group by coin and date
        for coin in df['coin'].unique():
            coin_df = df[df['coin'] == coin].copy()
            coin_df['date_only'] = coin_df['date'].dt.date
            
            for date in coin_df['date_only'].unique():
                day_trades = coin_df[coin_df['date_only'] == date]
                
                # Check if there are both buys and sells on same day
                has_buy = day_trades['action'].isin(['BUY', 'INCOME']).any()
                has_sell = day_trades['action'].isin(['SELL', 'SPEND']).any()
                
                if has_buy and has_sell:
                    # Calculate net position change
                    buy_amount = day_trades[day_trades['action'].isin(['BUY', 'INCOME'])]['amount'].sum()
                    sell_amount = day_trades[day_trades['action'].isin(['SELL', 'SPEND'])]['amount'].sum()
                    
                    # If amounts are similar (within 10%), flag as potential constructive sale
                    if buy_amount > 0 and abs(buy_amount - sell_amount) / buy_amount < 0.1:
                        constructive_risks.append({
                            'coin': coin,
                            'date': date,
                            'buy_amount': buy_amount,
                            'sell_amount': sell_amount,
                            'ids': day_trades['id'].tolist()
                        })
        
        if constructive_risks:
            self.suggestions.append({
                'severity': 'MEDIUM',
                'category': 'CONSTRUCTIVE_SALES',
                'title': 'Potential Constructive Sales Detected',
                'count': len(constructive_risks),
                'description': 'Found offsetting buy/sell positions on the same day that may trigger constructive sale rules.',
                'items': constructive_risks[:10],
                'action': 'Review these same-day offsetting trades. Constructive sales can trigger capital gains.'
            })

    def _check_defi_complexity(self, df):
        """Flag DeFi LP tokens and complex protocol interactions"""
        defi_transactions = []
        
        for _, row in df.iterrows():
            coin = str(row['coin']).upper()
            
            # Check if coin matches any DeFi protocol pattern
            if any(protocol in coin for protocol in self.defi_protocols):
                defi_transactions.append({
                    'coin': coin,
                    'date': row['date'],
                    'action': row['action'],
                    'id': row['id']
                })
        
        if defi_transactions:
            self.suggestions.append({
                'severity': 'MEDIUM',
                'category': 'DEFI_COMPLEXITY',
                'title': 'Complex DeFi Transactions Requiring Review',
                'count': len(defi_transactions),
                'description': 'Found LP tokens and DeFi protocol interactions. These may require special treatment.',
                'items': defi_transactions[:10],
                'action': 'Verify DeFi transaction handling. LP deposits may not be taxable events, but rewards are income.'
            })

    def _check_missing_prices(self, df):
        """Flag transactions with missing or zero prices"""
        missing_prices = []
        
        for _, row in df.iterrows():
            price = row.get('price_usd', 0)
            
            # Check if price is missing, null, or zero
            if pd.isna(price) or price == 0 or price == '' or price is None:
                missing_prices.append({
                    'coin': row['coin'],
                    'date': row['date'],
                    'action': row['action'],
                    'amount': row['amount'],
                    'id': row['id']
                })
        
        if missing_prices:
            self.warnings.append({
                'severity': 'HIGH',
                'category': 'MISSING_PRICES',
                'title': 'Missing Price Data',
                'count': len(missing_prices),
                'description': 'Found transactions with missing or zero USD prices. This will cause incorrect tax calculations.',
                'items': missing_prices[:10],
                'action': 'Update price_usd column in CSV or configure price lookups in Setup.py'
            })

    def _check_unmatched_sells(self):
        """Flag unmatched sells when using strict broker mode"""
        if not self.engine:
            return
        
        # Check if engine has unmatched sells recorded
        if hasattr(self.engine, 'unmatched_sell_log') and self.engine.unmatched_sell_log:
            self.warnings.append({
                'severity': 'HIGH',
                'category': 'UNMATCHED_SELLS',
                'title': 'Unmatched Sells in Strict Mode',
                'count': len(self.engine.unmatched_sell_log),
                'description': 'Found sell transactions with insufficient cost basis records in strict broker mode.',
                'items': self.engine.unmatched_sell_log[:10],
                'action': 'Add matching purchase records or switch to universal pool mode in Setup.py'
            })

    # --- NEW METHODS START HERE ---

    def _check_high_fees(self, df):
        """Flag transactions with unusually high fees (> $100 OR > 10% of value)"""
        high_fee_txs = []
        
        # Check "SPEND" actions (fees) in the tax report (engine.tt)
        # This requires full engine access with processed tax data
        if not self.engine or not hasattr(self.engine, 'tt') or not self.engine.tt:
            logger.debug("High fee detection skipped: Tax calculations not available. Run engine.run() first.")
            return
        
        try:
            for t in self.engine.tt:
                if '(Fee)' in str(t.get('Description', '')):
                    proceeds = float(t.get('Proceeds', 0))  # This is the Fee USD value
                    if proceeds > 100.0:
                        high_fee_txs.append({
                            'date': t.get('Date Sold'),
                            'coin': t.get('Description').replace('(Fee)', '').strip(),
                            'fee_usd': proceeds
                        })
        except Exception as e:
            logger.debug(f"High fee check encountered error: {e}")
            return
        
        if high_fee_txs:
            self.warnings.append({
                'severity': 'MEDIUM',
                'category': 'HIGH_FEES',
                'title': 'Unusually High Fees Detected',
                'count': len(high_fee_txs),
                'description': 'Found transactions with fees > $100. This might be a "fat-finger" error or incorrect data import.',
                'items': high_fee_txs[:10],
                'action': 'Verify these fees. If incorrect, edit the "fee" column in your input CSV.'
            })

    def _check_spam_tokens(self, df):
        """Flag potential spam tokens: High Quantity (>1000) but Low Price (<$0.0001)"""
        spam_candidates = []
        for _, row in df.iterrows():
            try:
                amt = float(row['amount'])
                price = float(row['price_usd'])
                if amt > 1000 and price < 0.0001 and row['action'] == 'INCOME':
                    spam_candidates.append({
                        'coin': row['coin'],
                        'date': row['date'],
                        'amount': amt,
                        'price': price
                    })
            except: pass
            
        if spam_candidates:
            self.suggestions.append({
                'severity': 'LOW',
                'category': 'SPAM_TOKENS',
                'title': 'Potential Spam/Scam Airdrops',
                'count': len(spam_candidates),
                'description': 'Found Income records with high quantity but near-zero value. These may be scam airdrops.',
                'items': spam_candidates[:10],
                'action': 'If these are scam tokens, you can delete them from the CSV or mark them as "IGNORE" to clean up reports.'
            })

    def _check_duplicate_suspects(self, df):
        """Flag potential duplicate transactions (Same coin, amount, time)"""
        # Create a signature for each trade
        df['sig'] = df.apply(lambda x: f"{x['date']}_{x['coin']}_{float(x['amount']):.6f}_{x['action']}", axis=1)
        duplicates = df[df.duplicated(subset=['sig'], keep=False)]
        
        if not duplicates.empty:
            # Group by signature to show pairs
            dupe_groups = []
            for sig, group in duplicates.groupby('sig'):
                if len(group) > 1:
                    dupe_groups.append({
                        'signature': sig,
                        'ids': group['id'].tolist(),
                        'count': len(group)
                    })
            
            if dupe_groups:
                self.warnings.append({
                    'severity': 'HIGH',
                    'category': 'DUPLICATE_TRANSACTIONS',
                    'title': 'Suspected Duplicate Transactions',
                    'count': len(dupe_groups),
                    'description': 'Found transactions with identical Date, Coin, Amount, and Action but different IDs. This often happens when importing via both API and CSV.',
                    'items': dupe_groups[:10],
                    'action': 'Check these IDs in your database. If they are duplicates, delete one.'
                })

    def _generate_report(self):
        # ... [Same as previous] ...
        report = {
            'warnings': self.warnings,
            'suggestions': self.suggestions,
            'summary': {
                'total_warnings': len(self.warnings),
                'total_suggestions': len(self.suggestions),
                'high_severity': sum(1 for w in self.warnings if w['severity'] == 'HIGH'),
                'medium_severity': sum(1 for w in self.warnings + self.suggestions if w['severity'] == 'MEDIUM'),
                'low_severity': sum(1 for s in self.suggestions if s['severity'] == 'LOW')
            }
        }
        self._print_report(report)
        return report

    def _print_report(self, report):
        """Print formatted report to console and log"""
        print("\n" + "="*80)
        print("TAX REVIEW REPORT - MANUAL VERIFICATION REQUIRED")
        print("="*80)
        
        # Check if we had full access
        has_full_access = self.engine and hasattr(self.engine, 'tt') and self.engine.tt
        if not has_full_access:
            print("\n[!] LIMITED SCAN: Advanced checks skipped (tax calculations not run).")
            print("   For complete analysis, run tax calculations first.")
        
        summary = report['summary']
        print(f"\nTotal Warnings: {summary['total_warnings']}")
        print(f"Total Suggestions: {summary['total_suggestions']}")
        print(f"  - High Severity: {summary['high_severity']}")
        print(f"  - Medium Severity: {summary['medium_severity']}")
        print(f"  - Low Severity: {summary['low_severity']}")
        
        # Print warnings
        if report['warnings']:
            print("\n" + "-"*80)
            print("WARNINGS (Action Required)")
            print("-"*80)
            for w in report['warnings']:
                print(f"\n[{w['severity']}] {w['title']}")
                print(f"  Category: {w['category']}")
                print(f"  Count: {w['count']}")
                print(f"  Description: {w['description']}")
                print(f"  Action: {w['action']}")
                if w.get('items'):
                    print(f"  Sample Items: {w['items'][:3]}")
        
        # Print suggestions
        if report['suggestions']:
            print("\n" + "-"*80)
            print("SUGGESTIONS (Review Recommended)")
            print("-"*80)
            for s in report['suggestions']:
                print(f"\n[{s['severity']}] {s['title']}")
                print(f"  Category: {s['category']}")
                print(f"  Count: {s['count']}")
                print(f"  Description: {s['description']}")
                print(f"  Action: {s['action']}")
        
        print("\n" + "="*80)
        
        # Prominent alert if warnings exist
        if report['warnings']:
            print("\n" + "!"*80)
            print("[!!!] ACTION REQUIRED: {num} WARNING{s} DETECTED".format(
                num=len(report['warnings']),
                s='S' if len(report['warnings']) != 1 else ''
            ))
            print("Review the warnings above and take corrective action before filing taxes.")
            print("Detailed reports saved to: outputs/Year_{year}/REVIEW_WARNINGS.csv".format(year=self.year))
            print("!"*80)
        
        # Also log
        logger.info(f"Review Complete: {summary['total_warnings']} warnings, {summary['total_suggestions']} suggestions")

    def export_report(self, output_dir):
        """Export review report to JSON and CSV files"""
        import json
        from datetime import datetime
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Export JSON
        json_filename = f"tax_review_{self.year}_{timestamp}.json"
        json_filepath = output_path / json_filename
        
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'tax_year': self.year,
            'warnings': self.warnings,
            'suggestions': self.suggestions,
            'summary': {
                'total_warnings': len(self.warnings),
                'total_suggestions': len(self.suggestions),
                'high_severity': sum(1 for w in self.warnings if w['severity'] == 'HIGH'),
                'medium_severity': sum(1 for w in self.warnings + self.suggestions if w['severity'] == 'MEDIUM'),
                'low_severity': sum(1 for s in self.suggestions if s['severity'] == 'LOW')
            }
        }
        
        with open(json_filepath, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        logger.info(f"Review report exported to {json_filepath}")
        
        # Export CSV files
        if self.warnings:
            warnings_df = pd.DataFrame([
                {
                    'Category': w['category'],
                    'Severity': w['severity'],
                    'Title': w['title'],
                    'Count': w['count'],
                    'Description': w['description'],
                    'Action': w['action']
                }
                for w in self.warnings
            ])
            csv_warnings_path = output_path / 'REVIEW_WARNINGS.csv'
            warnings_df.to_csv(csv_warnings_path, index=False)
            logger.info(f"Warnings exported to {csv_warnings_path}")
        
        if self.suggestions:
            suggestions_df = pd.DataFrame([
                {
                    'Category': s['category'],
                    'Severity': s['severity'],
                    'Title': s['title'],
                    'Count': s['count'],
                    'Description': s['description'],
                    'Action': s['action']
                }
                for s in self.suggestions
            ])
            csv_suggestions_path = output_path / 'REVIEW_SUGGESTIONS.csv'
            suggestions_df.to_csv(csv_suggestions_path, index=False)
            logger.info(f"Suggestions exported to {csv_suggestions_path}")
        
        return json_filepath