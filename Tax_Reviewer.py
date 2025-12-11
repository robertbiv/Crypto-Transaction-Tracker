"""
Tax Reviewer - Heuristic-Based Manual Review Assistant
Scans completed tax calculations and flags potential audit risks for manual review.
"""

import pandas as pd
from datetime import timedelta
from pathlib import Path
from collections import defaultdict
import logging

logger = logging.getLogger("crypto_tax_engine")

class TaxReviewer:
    """
    Post-processing reviewer that applies heuristics to detect:
    1. NFTs without collectible prefixes (28% tax risk)
    2. Substantially identical wash sales (BTC/WBTC)
    3. Potential constructive sales (offsetting positions)
    4. Complex DeFi transactions needing manual verification
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
            'TOKEN', 'DEED', 'PASS', 'GENESIS', 'FOUNDER'
        ]
        
        self.defi_protocols = [
            'UNI-V2', 'UNI-V3', 'SUSHI', 'CURVE', 'BALANCER', 'AAVE',
            'COMPOUND', 'MAKER', 'YEARN', '-LP', '_LP', 'POOL'
        ]
    
    def run_review(self):
        """Run all heuristic checks and generate review report"""
        logger.info("--- MANUAL REVIEW ASSISTANT ---")
        logger.info("Scanning for potential audit risks...")
        
        df = self.db.get_all()
        df['date'] = pd.to_datetime(df['date'])
        df = df[df['date'].dt.year == int(self.year)]
        
        if df.empty:
            logger.info("No trades found for review year.")
            return {'warnings': [], 'suggestions': []}
        
        # Run all checks
        self._check_nft_collectibles(df)
        self._check_substantially_identical_wash_sales(df)
        self._check_constructive_sales(df)
        self._check_defi_complexity(df)
        self._check_missing_prices(df)
        self._check_unmatched_sells()
        
        # Generate report
        report = self._generate_report()
        return report
    
    def _check_nft_collectibles(self, df):
        """Flag assets that look like NFTs but aren't marked as collectibles"""
        potential_nfts = []
        
        for _, row in df.iterrows():
            coin = str(row['coin']).upper()
            
            # Check if it matches NFT indicators
            looks_like_nft = False
            for indicator in self.nft_indicators:
                if indicator in coin:
                    looks_like_nft = True
                    break
            
            # Check if it has a # symbol (common in NFT names)
            if '#' in coin:
                looks_like_nft = True
            
            # Check if it's already marked as collectible
            is_marked = coin.startswith(('NFT-', 'ART-', 'COLLECTIBLE-'))
            
            if looks_like_nft and not is_marked:
                potential_nfts.append({
                    'coin': coin,
                    'date': row['date'],
                    'action': row['action'],
                    'amount': row['amount'],
                    'id': row['id']
                })
        
        if potential_nfts:
            self.warnings.append({
                'severity': 'HIGH',
                'category': 'NFT_COLLECTIBLES',
                'title': 'Potential NFTs Not Marked as Collectibles',
                'count': len(potential_nfts),
                'description': (
                    'Found assets that appear to be NFTs but are not prefixed with NFT-, ART-, or COLLECTIBLE-. '
                    'If these are collectibles, they should be taxed at 28% long-term rate (not 20%).'
                ),
                'items': potential_nfts[:10],  # Show first 10
                'action': (
                    'Review these assets. If they are NFTs:\n'
                    '  1. Edit your CSV to rename them with NFT- prefix (e.g., "BAYC#1234" → "NFT-BAYC#1234")\n'
                    '  2. Or add them to config.json "collectible_tokens" list\n'
                    '  3. Re-run the tax calculation'
                )
            })
    
    def _check_substantially_identical_wash_sales(self, df):
        """Flag potential wash sales between wrapped/similar assets"""
        wash_risks = []
        
        for mapping in self.substantially_identical:
            base = mapping['base']
            wrapped = mapping['wrapped']
            all_variants = [base] + wrapped
            
            # Get all sells at loss for any variant
            sells_at_loss = df[
                (df['action'] == 'SELL') & 
                (df['coin'].isin(all_variants))
            ]
            
            for _, sell in sells_at_loss.iterrows():
                sell_date = sell['date']
                sell_coin = sell['coin']
                
                # Check for buys of ANY variant within 30 days before/after
                window_start = sell_date - timedelta(days=30)
                window_end = sell_date + timedelta(days=30)
                
                nearby_buys = df[
                    (df['action'].isin(['BUY', 'INCOME'])) &
                    (df['coin'].isin(all_variants)) &
                    (df['coin'] != sell_coin) &  # Different variant
                    (df['date'] >= window_start) &
                    (df['date'] <= window_end) &
                    (df['date'] != sell_date)
                ]
                
                if not nearby_buys.empty:
                    for _, buy in nearby_buys.iterrows():
                        wash_risks.append({
                            'sell_coin': sell_coin,
                            'sell_date': sell['date'],
                            'sell_id': sell['id'],
                            'buy_coin': buy['coin'],
                            'buy_date': buy['date'],
                            'buy_id': buy['id'],
                            'days_apart': abs((buy['date'] - sell_date).days)
                        })
        
        if wash_risks:
            self.warnings.append({
                'severity': 'MEDIUM',
                'category': 'SUBSTANTIALLY_IDENTICAL_WASH_SALES',
                'title': 'Potential Wash Sales Between Similar Assets',
                'count': len(wash_risks),
                'description': (
                    'Found trades between "substantially identical" assets (e.g., BTC/WBTC) within 30-day wash sale window. '
                    'The IRS may consider these wash sales even though they have different tickers.'
                ),
                'items': wash_risks[:10],
                'action': (
                    'Review these transactions:\n'
                    '  1. If you sold BTC at a loss and bought WBTC within 30 days, the IRS likely treats this as a wash sale\n'
                    '  2. Consider manually adjusting your cost basis for the replacement purchase\n'
                    '  3. Consult a tax professional if losses are material'
                )
            })
    
    def _check_constructive_sales(self, df):
        """Flag potential constructive sales (offsetting long/short positions)"""
        # This is a basic heuristic - looks for same-day opposing trades
        constructive_risks = []
        
        # Group by coin and date
        for coin in df['coin'].unique():
            coin_trades = df[df['coin'] == coin].copy()
            coin_trades['date_only'] = coin_trades['date'].dt.date
            
            for date in coin_trades['date_only'].unique():
                day_trades = coin_trades[coin_trades['date_only'] == date]
                
                has_buy = any(day_trades['action'].isin(['BUY', 'INCOME']))
                has_sell = any(day_trades['action'] == 'SELL')
                
                # If both buy and sell on same day with significant volume
                if has_buy and has_sell:
                    buy_amt = day_trades[day_trades['action'].isin(['BUY', 'INCOME'])]['amount'].sum()
                    sell_amt = day_trades[day_trades['action'] == 'SELL']['amount'].sum()
                    
                    # Flag if amounts are similar (potential hedging)
                    if abs(buy_amt - sell_amt) / max(buy_amt, sell_amt) < 0.2:  # Within 20%
                        constructive_risks.append({
                            'coin': coin,
                            'date': date,
                            'buy_amount': float(buy_amt),
                            'sell_amount': float(sell_amt),
                            'note': 'Same-day offsetting trades (potential hedge)'
                        })
        
        if constructive_risks:
            self.suggestions.append({
                'severity': 'LOW',
                'category': 'CONSTRUCTIVE_SALES',
                'title': 'Potential Constructive Sales / Hedging Activity',
                'count': len(constructive_risks),
                'description': (
                    'Found same-day buy and sell trades with similar volumes. '
                    'If you opened offsetting positions (e.g., long and short) to lock in gains without selling, '
                    'the IRS may treat this as a "constructive sale" triggering immediate taxation.'
                ),
                'items': constructive_risks[:10],
                'action': (
                    'Review these dates:\n'
                    '  1. If you held a position and opened an offsetting short/hedge, this may be taxable\n'
                    '  2. This is rare for most crypto users but common in advanced trading strategies\n'
                    '  3. Consult IRS Publication 550 Section on "Constructive Sales"'
                )
            })
    
    def _check_defi_complexity(self, df):
        """Flag DeFi/LP token transactions that may need manual review"""
        defi_transactions = []
        
        for _, row in df.iterrows():
            coin = str(row['coin']).upper()
            
            # Check if coin name suggests DeFi/LP
            is_defi = False
            for protocol in self.defi_protocols:
                if protocol in coin:
                    is_defi = True
                    break
            
            if is_defi:
                defi_transactions.append({
                    'coin': coin,
                    'date': row['date'],
                    'action': row['action'],
                    'amount': row['amount'],
                    'id': row['id']
                })
        
        if defi_transactions:
            self.suggestions.append({
                'severity': 'MEDIUM',
                'category': 'DEFI_COMPLEXITY',
                'title': 'DeFi/LP Tokens Detected',
                'count': len(defi_transactions),
                'description': (
                    'Found transactions involving liquidity pool (LP) tokens or DeFi protocol tokens. '
                    'These transactions may involve complex tax treatment:\n'
                    '  - Providing liquidity may be a taxable swap\n'
                    '  - Yield generation may be taxable income\n'
                    '  - Impermanent loss is not auto-calculated'
                ),
                'items': defi_transactions[:10],
                'action': (
                    'Review these transactions:\n'
                    '  1. Verify that deposits/withdrawals are recorded correctly\n'
                    '  2. If you received yield, ensure it\'s marked as INCOME\n'
                    '  3. Consider consulting a crypto tax specialist for complex DeFi positions'
                )
            })
    
    def _check_missing_prices(self, df):
        """Flag transactions with zero or missing prices"""
        missing_prices = df[
            ((df['price_usd'] == 0) | (df['price_usd'].isna())) &
            (df['action'].isin(['BUY', 'SELL', 'INCOME']))
        ]
        
        if not missing_prices.empty:
            self.warnings.append({
                'severity': 'HIGH',
                'category': 'MISSING_PRICES',
                'title': 'Transactions with Missing Prices',
                'count': len(missing_prices),
                'description': (
                    'Found transactions with zero or missing USD prices. '
                    'These will cause incorrect cost basis and gain calculations.'
                ),
                'items': missing_prices[['id', 'date', 'coin', 'action', 'amount']].to_dict('records')[:10],
                'action': (
                    'Fix these transactions:\n'
                    '  1. Run Auto_Runner.py to fetch missing prices automatically\n'
                    '  2. Or manually add prices to your CSV and re-import'
                )
            })
    
    def _check_unmatched_sells(self):
        """Flag unmatched sells from TT rows if available"""
        if not self.engine or not hasattr(self.engine, 'tt'):
            return
        
        unmatched = [r for r in self.engine.tt if r.get('Unmatched_Sell') == 'YES']
        
        if unmatched:
            self.warnings.append({
                'severity': 'HIGH',
                'category': 'UNMATCHED_SELLS',
                'title': 'Unmatched Sells Detected (Strict Broker Mode)',
                'count': len(unmatched),
                'description': (
                    'Found sells with insufficient cost basis in the source wallet. '
                    'With strict_broker_mode enabled, these sells cannot borrow from other wallets. '
                    'This may indicate:\n'
                    '  - Missing import data (forgot to import buys)\n'
                    '  - Incorrect source attribution\n'
                    '  - Basis transferred from another platform'
                ),
                'items': [{'description': r['Description'], 'source': r['Source'], 'date': r['Date Sold']} 
                          for r in unmatched[:10]],
                'action': (
                    'Review these sells:\n'
                    '  1. Check if you\'re missing buy/transfer records\n'
                    '  2. Verify the source wallet is correct\n'
                    '  3. If you transferred crypto in from another platform, ensure that basis is recorded'
                )
            })
    
    def _generate_report(self):
        """Generate formatted review report"""
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
        
        # Print summary
        self._print_report(report)
        
        return report
    
    def _print_report(self, report):
        """Print formatted report to console"""
        print("\n" + "="*80)
        print("TAX REVIEW REPORT - MANUAL VERIFICATION REQUIRED")
        print("="*80)
        
        summary = report['summary']
        print(f"\n📊 SUMMARY:")
        print(f"   🚨 High Priority Warnings: {summary['high_severity']}")
        print(f"   ⚠️  Medium Priority: {summary['medium_severity']}")
        print(f"   💡 Suggestions: {summary['low_severity']}")
        
        if summary['total_warnings'] == 0 and summary['total_suggestions'] == 0:
            print("\n✅ No issues detected. Your tax calculation appears clean.")
            print("   (Note: This is a heuristic scan, not a guarantee of accuracy)")
            return
        
        # Print warnings
        for warning in self.warnings:
            print(f"\n{'='*80}")
            print(f"🚨 {warning['severity']}: {warning['title']}")
            print(f"{'='*80}")
            print(f"Category: {warning['category']}")
            print(f"Count: {warning['count']} items")
            print(f"\n{warning['description']}")
            print(f"\n📋 Sample Items:")
            for i, item in enumerate(warning['items'][:5], 1):
                print(f"   {i}. {item}")
            if warning['count'] > 5:
                print(f"   ... and {warning['count'] - 5} more")
            print(f"\n✅ RECOMMENDED ACTION:")
            print(f"{warning['action']}")
        
        # Print suggestions
        for suggestion in self.suggestions:
            print(f"\n{'='*80}")
            print(f"💡 {suggestion['severity']}: {suggestion['title']}")
            print(f"{'='*80}")
            print(f"Category: {suggestion['category']}")
            print(f"Count: {suggestion['count']} items")
            print(f"\n{suggestion['description']}")
            print(f"\n📋 Sample Items:")
            for i, item in enumerate(suggestion['items'][:5], 1):
                print(f"   {i}. {item}")
            if suggestion['count'] > 5:
                print(f"   ... and {suggestion['count'] - 5} more")
            print(f"\n💡 SUGGESTED ACTION:")
            print(f"{suggestion['action']}")
        
        print(f"\n{'='*80}")
        print("⚠️  IMPORTANT: These are heuristic suggestions, not definitive rulings.")
        print("   Always consult a qualified tax professional for material transactions.")
        print("="*80 + "\n")
    
    def export_report(self, output_dir):
        """Export review report to CSV files"""
        output_dir = Path(output_dir)
        if not output_dir.exists():
            output_dir.mkdir(parents=True)
        
        # Export warnings
        if self.warnings:
            warnings_data = []
            for w in self.warnings:
                for item in w['items']:
                    warnings_data.append({
                        'Severity': w['severity'],
                        'Category': w['category'],
                        'Title': w['title'],
                        'Item': str(item),
                        'Action': w['action']
                    })
            pd.DataFrame(warnings_data).to_csv(output_dir / 'REVIEW_WARNINGS.csv', index=False)
            logger.info(f"Exported warnings to {output_dir / 'REVIEW_WARNINGS.csv'}")
        
        # Export suggestions
        if self.suggestions:
            suggestions_data = []
            for s in self.suggestions:
                for item in s['items']:
                    suggestions_data.append({
                        'Severity': s['severity'],
                        'Category': s['category'],
                        'Title': s['title'],
                        'Item': str(item),
                        'Action': s['action']
                    })
            pd.DataFrame(suggestions_data).to_csv(output_dir / 'REVIEW_SUGGESTIONS.csv', index=False)
            logger.info(f"Exported suggestions to {output_dir / 'REVIEW_SUGGESTIONS.csv'}")
