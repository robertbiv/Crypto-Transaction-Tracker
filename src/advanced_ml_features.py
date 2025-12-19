"""
Advanced ML Features for Crypto Transaction Tracker
Includes: Fraud Detection, Smart Descriptions, DeFi Classification, AML, Pattern Learning
"""

import json
import hashlib
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from src.decimal_utils import to_decimal
from src.precision_audit_logger import (
    log_fraud_detection,
    log_fee_calculation,
    log_structuring_alert,
    log_wash_sale_detection
)


class FraudDetector:
    """Detect suspicious transaction patterns"""
    
    def __init__(self):
        self.wash_sale_threshold = 30  # days
        self.pump_dump_threshold = 0.5  # 50% volatility in 1 day
        self.suspicious_volume_threshold = 5.0  # 5x normal
    
    def detect_wash_sale(self, transactions: List[Dict]) -> List[Dict]:
        """Flag potential wash sales (buy then sell same coin within 30 days)"""
        alerts = []
        by_coin = defaultdict(list)
        
        # Group by coin
        for tx in transactions:
            coin = tx.get('coin', '')
            if coin:
                by_coin[coin].append(tx)
        
        # Check for wash sale patterns
        for coin, txs in by_coin.items():
            buys = [t for t in txs if t.get('action') == 'BUY']
            sells = [t for t in txs if t.get('action') == 'SELL']
            
            for buy in buys:
                buy_date = datetime.fromisoformat(buy.get('date', '')) if buy.get('date') else None
                if not buy_date:
                    continue
                
                for sell in sells:
                    sell_date = datetime.fromisoformat(sell.get('date', '')) if sell.get('date') else None
                    if not sell_date:
                        continue
                    
                    days_diff = (sell_date - buy_date).days
                    if 0 < days_diff <= self.wash_sale_threshold:
                        alert = {
                            'type': 'wash_sale',
                            'coin': coin,
                            'buy_id': buy['id'],
                            'sell_id': sell['id'],
                            'days_apart': days_diff,
                            'severity': 'high',
                            'message': f'Possible wash sale: {coin} bought {days_diff} days before sale'
                        }
                        alerts.append(alert)
                        try:
                            log_wash_sale_detection(
                                tx_id=f"{buy['id']}|{sell['id']}",
                                coin=coin,
                                amount=str(buy.get('amount', 0)),
                                wash_date_range=f"{buy_date.date()} to {sell_date.date()}",
                                loss_amount=str(abs(to_decimal(sell.get('price_usd', 0)) - to_decimal(buy.get('price_usd', 0))))
                            )
                        except Exception:
                            pass
        
        return alerts
    
    def detect_pump_dump(self, transactions: List[Dict]) -> List[Dict]:
        """Flag rapid buy-sell cycles (pump & dump pattern)"""
        alerts = []
        by_coin = defaultdict(list)
        
        for tx in transactions:
            coin = tx.get('coin', '')
            if coin:
                by_coin[coin].append(tx)
        
        for coin, txs in by_coin.items():
            for i, tx in enumerate(txs):
                if tx.get('action') == 'BUY':
                    buy_price = to_decimal(tx.get('price_usd', 0))
                    if buy_price == 0:
                        continue
                    
                    # Look for subsequent sells
                    for j in range(i + 1, min(i + 5, len(txs))):
                        next_tx = txs[j]
                        if next_tx.get('action') == 'SELL':
                            sell_price = to_decimal(next_tx.get('price_usd', 0))
                            if sell_price == 0:
                                continue
                            
                            price_change = abs(sell_price - buy_price) / buy_price
                            if price_change > Decimal(str(self.pump_dump_threshold)):
                                price_change_pct = (price_change * Decimal(100)).quantize(Decimal('0.01'))
                                alert = {
                                    'type': 'pump_dump',
                                    'coin': coin,
                                    'buy_id': tx['id'],
                                    'sell_id': next_tx['id'],
                                    'price_change_pct': float(price_change_pct),
                                    'severity': 'medium',
                                    'message': f'{coin} {price_change_pct}% price change between buy and sell'
                                }
                                alerts.append(alert)
                                try:
                                    gain = (sell_price - buy_price) * to_decimal(tx.get('amount', 0))
                                    log_fraud_detection(
                                        tx_id=tx['id'],
                                        coin=coin,
                                        amount=str(tx.get('amount', 0)),
                                        alert_type='PUMP_DUMP',
                                        calculated_gain=str(gain.quantize(Decimal('0.01'))),
                                        transaction_impact=str((gain * Decimal('0.25')).quantize(Decimal('0.01')))
                                    )
                                except Exception:
                                    pass
        
        return alerts
    
    def detect_suspicious_volume(self, transactions: List[Dict]) -> List[Dict]:
        """Flag unusually large transactions"""
        alerts = []
        by_coin = defaultdict(list)
        
        for tx in transactions:
            coin = tx.get('coin', '')
            if coin:
                by_coin[coin].append(tx)
        
        for coin, txs in by_coin.items():
            amounts = [to_decimal(t.get('amount', 0)) for t in txs if t.get('amount')]
            if not amounts:
                continue
            
            avg_amount = sum(amounts) / len(amounts)
            
            for tx in txs:
                amount = to_decimal(tx.get('amount', 0))
                if amount > 0 and amount > (avg_amount * Decimal(str(self.suspicious_volume_threshold))):
                    multiplier = (amount / avg_amount) if avg_amount else Decimal(0)
                    alert = {
                        'type': 'suspicious_volume',
                        'coin': coin,
                        'tx_id': tx['id'],
                        'amount': float(amount),
                        'avg_amount': float(avg_amount),
                        'multiplier': float(multiplier.quantize(Decimal('0.1'))),
                        'severity': 'low',
                        'message': f'Large {coin} transaction: {amount} ({round(float(multiplier))}x average)'
                    }
                    alerts.append(alert)
                    try:
                        log_fraud_detection(
                            tx_id=tx['id'],
                            coin=coin,
                            amount=str(amount),
                            alert_type='SUSPICIOUS_VOLUME',
                            calculated_gain='0.00',
                            transaction_impact='0.00'
                        )
                    except Exception:
                        pass
        
        return alerts


class SmartDescriptionGenerator:
    """Generate detailed transaction descriptions"""
    
    DEFI_KEYWORDS = {
        'uniswap': 'Decentralized exchange swap (Uniswap)',
        'aave': 'Lending protocol (Aave)',
        'curve': 'Stablecoin DEX (Curve)',
        'lido': 'Liquid staking (Lido)',
        'yearn': 'Yield farming (Yearn)',
        'compound': 'Lending protocol (Compound)',
        'balancer': 'Liquidity pool (Balancer)',
        'opensea': 'NFT marketplace (OpenSea)',
    }
    
    def generate_description(self, tx: Dict) -> str:
        """Generate smart description from transaction data"""
        action = tx.get('action', 'UNKNOWN').upper()
        coin = tx.get('coin', '').upper()
        amount_raw = tx.get('amount', 0)
        price_raw = tx.get('price_usd', 0)
        amount = to_decimal(amount_raw)
        price = to_decimal(price_raw)
        source = tx.get('source', '').lower()
        description = tx.get('description', '').lower()
        
        # Check for DeFi protocols
        for protocol, label in self.DEFI_KEYWORDS.items():
            if protocol in source or protocol in description:
                if action == 'TRADE':
                    return f"DeFi swap via {label}: {amount} {coin}"
                elif action == 'INCOME':
                    return f"Yield from {label}: +{amount} {coin}"
        
        # Generate based on action
        if action == 'BUY':
            return f"Purchased {amount} {coin} @ ${price:,.2f}"
        elif action == 'SELL':
            return f"Sold {amount} {coin} @ ${price:,.2f}"
        elif action == 'TRADE':
            return f"Exchanged {amount} {coin}"
        elif action == 'INCOME':
            return f"Received {amount} {coin} as income"
        elif action == 'TRANSFER':
            dest = tx.get('destination', 'unknown address')
            return f"Transferred {amount} {coin} to {dest[:10]}..."
        
        return f"{action}: {amount} {coin}"


class DeFiClassifier:
    """Classify DeFi protocol interactions"""
    
    PROTOCOLS = {
        'uniswap': {'type': 'DEX', 'category': 'swap'},
        'aave': {'type': 'lending', 'category': 'borrow/lend'},
        'curve': {'type': 'DEX', 'category': 'stablecoin_swap'},
        'lido': {'type': 'staking', 'category': 'liquid_staking'},
        'yearn': {'type': 'yield', 'category': 'yield_farming'},
        'compound': {'type': 'lending', 'category': 'borrow/lend'},
        'balancer': {'type': 'DEX', 'category': 'liquidity_pool'},
        'opensea': {'type': 'NFT', 'category': 'nft_trade'},
    }
    
    def classify(self, tx: Dict) -> Optional[Dict]:
        """Classify transaction as DeFi interaction"""
        source = tx.get('source', '').lower()
        description = (tx.get('description', '') + ' ' + source).lower()
        
        for protocol, info in self.PROTOCOLS.items():
            if protocol in description:
                return {
                    'protocol': protocol,
                    'type': info['type'],
                    'category': info['category'],
                    'confidence': 0.95
                }
        
        return None
    
    def flag_high_fees(self, tx: Dict) -> Optional[Dict]:
        """Flag unusually high gas/swap fees"""
        fee = to_decimal(tx.get('fee', 0))
        total_value = to_decimal(tx.get('price_usd', 0)) * to_decimal(tx.get('amount', 1))
        
        if total_value > 0:
            fee_pct = (fee / total_value) * Decimal(100)
            if fee_pct > Decimal(5):  # Flag if > 5%
                fee_pct_rounded = fee_pct.quantize(Decimal('0.01'))
                alert = {
                    'type': 'high_fee',
                    'fee': float(fee),
                    'fee_pct': float(fee_pct_rounded),
                    'message': f'High fee: {fee_pct_rounded}% of transaction value'
                }
                try:
                    log_fee_calculation(
                        tx_id=tx.get('id', 'unknown'),
                        coin=tx.get('coin', 'UNKNOWN'),
                        amount=str(tx.get('amount', 0)),
                        fee_amount=str(fee),
                        fee_pct=str(fee_pct_rounded),
                        multiplier=str(fee_pct_rounded)
                    )
                except Exception:
                    pass
                return alert
        
        return None


class PatternLearner:
    """Learn and detect user transaction patterns"""
    
    def __init__(self):
        self.patterns = defaultdict(lambda: {
            'count': 0,
            'avg_amount': 0,
            'avg_price': 0,
            'sources': defaultdict(int),
            'timestamps': []
        })
    
    def learn_patterns(self, transactions: List[Dict]) -> None:
        """Build pattern profile from historical transactions"""
        for tx in transactions:
            key = f"{tx.get('action')}_{tx.get('coin')}"
            pattern = self.patterns[key]
            
            pattern['count'] += 1
            amount = to_decimal(tx.get('amount', 0))
            pattern['avg_amount'] = (pattern['avg_amount'] * (pattern['count'] - 1) + amount) / pattern['count']
            
            price = to_decimal(tx.get('price_usd', 0))
            if price > 0:
                pattern['avg_price'] = (pattern['avg_price'] * (pattern['count'] - 1) + price) / pattern['count']
            
            source = tx.get('source', 'unknown')
            pattern['sources'][source] += 1
    
    def detect_anomalies(self, tx: Dict) -> List[Dict]:
        """Flag transactions that deviate from learned patterns"""
        alerts = []
        key = f"{tx.get('action')}_{tx.get('coin')}"
        
        if key not in self.patterns:
            return alerts
        
        pattern = self.patterns[key]
        amount = to_decimal(tx.get('amount', 0))
        
        # Flag if amount is 3x average
        if pattern['avg_amount'] > 0 and amount > (pattern['avg_amount'] * 3):
            alerts.append({
                'type': 'anomaly_amount',
                'severity': 'medium',
                'message': f'Amount {amount} is {round(amount/pattern["avg_amount"])}x your average'
            })
        
        # Flag if unusual source
        source = tx.get('source', 'unknown')
        if pattern['sources'] and source not in pattern['sources']:
            alerts.append({
                'type': 'anomaly_source',
                'severity': 'low',
                'message': f'New source: {source} (usually: {list(pattern["sources"].keys())[0]})'
            })
        
        return alerts


class AMLDetector:
    """Anti-Money Laundering pattern detection"""
    
    def detect_structuring(self, transactions: List[Dict], threshold: float = 10000, days: int = 7) -> List[Dict]:
        """Detect structuring (multiple small txs to avoid threshold)"""
        alerts = []
        recent = [t for t in transactions if self._is_recent(t, days)]
        
        # Group by coin and action
        by_group = defaultdict(list)
        for tx in recent:
            key = f"{tx.get('action')}_{tx.get('coin')}"
            by_group[key].append(tx)
        
        for key, txs in by_group.items():
            total_value = sum(to_decimal(t.get('price_usd', 0)) * to_decimal(t.get('amount', 1)) for t in txs)
            
            # Flag if total is above threshold but individual txs are small
            if total_value > Decimal(str(threshold)):
                max_single = max(to_decimal(t.get('price_usd', 0)) * to_decimal(t.get('amount', 1)) for t in txs)
                avg_single = total_value / len(txs)
                
                if max_single < (total_value * Decimal('0.3')):  # No single tx is > 30% of total
                    total_value_rounded = total_value.quantize(Decimal('0.01'))
                    alert = {
                        'type': 'structuring',
                        'total_value': float(total_value_rounded),
                        'num_transactions': len(txs),
                        'days': days,
                        'severity': 'high',
                        'message': f'Structuring alert: ${total_value_rounded:,.0f} split across {len(txs)} txs in {days} days'
                    }
                    alerts.append(alert)
                    try:
                        log_structuring_alert(
                            tx_id=f"{key}_batch",
                            coin=key.split('_')[1] if '_' in key else 'UNKNOWN',
                            total_amount=str(total_value_rounded),
                            num_transactions=len(txs),
                            window_days=days,
                            threshold=str(Decimal(str(threshold)))
                        )
                    except Exception:
                        pass
        
        return alerts
    
    def _is_recent(self, tx: Dict, days: int) -> bool:
        """Check if transaction is within N days"""
        try:
            tx_date = datetime.fromisoformat(tx.get('date', ''))
            return (datetime.now() - tx_date).days <= days
        except:
            return False


class TransactionHistory:
    """Track transaction changes for undo/history"""
    
    def __init__(self, history_file: Optional[Path] = None):
        self.history_file = history_file or Path('outputs/logs/transaction_history.jsonl')
        self.history_file.parent.mkdir(exist_ok=True)
    
    def record_change(self, tx_id: str, old_value: Dict, new_value: Dict, reason: str) -> None:
        """Record a transaction change for audit trail"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'transaction_id': tx_id,
            'old_value': old_value,
            'new_value': new_value,
            'reason': reason,
            'change_hash': hashlib.sha256(str((tx_id, old_value, new_value)).encode()).hexdigest()[:8]
        }
        
        with open(self.history_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    def get_history(self, tx_id: str) -> List[Dict]:
        """Get all changes for a transaction"""
        history = []
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                for line in f:
                    entry = json.loads(line)
                    if entry['transaction_id'] == tx_id:
                        history.append(entry)
        return history
    
    def revert(self, tx_id: str, steps: int = 1) -> Optional[Dict]:
        """Get the previous version of a transaction"""
        hist = self.get_history(tx_id)
        if len(hist) >= steps:
            return hist[-steps]['old_value']
        return None


class NaturalLanguageSearch:
    """Search transactions using natural language"""
    
    def parse_query(self, query: str) -> Dict:
        """Parse natural language query into filter parameters"""
        query_lower = query.lower()
        filters = {}
        
        # Extract action
        actions = {'buy': 'BUY', 'sell': 'SELL', 'trade': 'TRADE', 'transfer': 'TRANSFER'}
        for word, action in actions.items():
            if word in query_lower:
                filters['action'] = action
                break
        
        # Extract coin
        coins = ['BTC', 'ETH', 'ADA', 'SOL', 'XRP', 'DOT', 'USDC', 'USDT']
        for coin in coins:
            if coin.lower() in query_lower:
                filters['coin'] = coin
                break
        
        # Extract year
        import re
        year_match = re.search(r'20\d{2}', query)
        if year_match:
            filters['year'] = int(year_match.group())
        
        # Extract min/max
        amount_match = re.search(r'(largest|biggest|most|over)\s+(\d+(?:\.\d+)?)', query)
        if amount_match:
            filters['min_amount'] = to_decimal(amount_match.group(2))
        
        return filters
    
    def search(self, transactions: List[Dict], query: str) -> List[Dict]:
        """Search transactions using natural language"""
        filters = self.parse_query(query)
        results = transactions
        
        if 'action' in filters:
            results = [t for t in results if t.get('action') == filters['action']]
        
        if 'coin' in filters:
            results = [t for t in results if t.get('coin') == filters['coin']]
        
        if 'year' in filters:
            year = filters['year']
            results = [t for t in results if t.get('date', '').startswith(str(year))]
        
        if 'min_amount' in filters:
            results = [t for t in results if to_decimal(t.get('amount', 0)) >= filters['min_amount']]
        
        # Sort by price descending if asking for largest
        if 'largest' in query.lower() or 'biggest' in query.lower():
            results.sort(key=lambda t: to_decimal(t.get('price_usd', 0)) * to_decimal(t.get('amount', 1)), reverse=True)
        
        return results


if __name__ == '__main__':
    # Test the modules
    print("Advanced ML Features loaded successfully!")
    print("- FraudDetector")
    print("- SmartDescriptionGenerator")
    print("- DeFiClassifier")
    print("- PatternLearner")
    print("- AMLDetector")
    print("- TransactionHistory")
    print("- NaturalLanguageSearch")
