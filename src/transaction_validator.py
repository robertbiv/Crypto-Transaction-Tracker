"""
Transaction input validation schema.
Ensures all transactions meet minimum data quality before ML processing.
"""

from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from src.decimal_utils import to_decimal, SATOSHI, STRUCTURING_THRESHOLD


class TransactionValidator:
    """Validates transaction data integrity and structure."""
    
    REQUIRED_FIELDS = {'action', 'coin', 'amount', 'price_usd', 'date'}
    VALID_ACTIONS = {'BUY', 'SELL', 'TRADE', 'TRANSFER', 'INCOME'}
    VALID_COINS = {
        'BTC', 'ETH', 'ADA', 'SOL', 'XRP', 'DOT', 'USDC', 'USDT', 'BNB', 'MATIC',
        'LINK', 'UNI', 'AAVE', 'WETH', 'DAI', 'USDE', 'BLUR', 'ARB', 'OP'
    }
    
    # Reasonable ranges (prevent typos like entering total as price)
    MIN_PRICE = Decimal('0.0000001')
    MAX_PRICE = Decimal('10000000')
    MIN_AMOUNT = SATOSHI
    MAX_AMOUNT = Decimal('1000000')
    
    @classmethod
    def validate_transaction(cls, tx: Dict) -> Tuple[bool, List[str]]:
        """
        Validate a single transaction.
        
        Args:
            tx: Transaction dict to validate.
        
        Returns:
            (is_valid, error_list) — bool and list of validation error messages.
        """
        errors = []
        
        # Check required fields
        missing = cls.REQUIRED_FIELDS - set(tx.keys())
        if missing:
            errors.append(f"Missing required fields: {missing}")
        
        # Type checks
        if not isinstance(tx.get('action'), str):
            errors.append("action must be string")
        elif tx['action'].upper() not in cls.VALID_ACTIONS:
            errors.append(f"action '{tx['action']}' not in {cls.VALID_ACTIONS}")
        
        if not isinstance(tx.get('coin'), str):
            errors.append("coin must be string")
        elif tx['coin'].upper() not in cls.VALID_COINS and not cls._is_custom_token(tx['coin']):
            errors.append(f"coin '{tx['coin']}' not recognized (or custom token)")
        
        # Numeric validation
        try:
            amount = to_decimal(tx.get('amount'))
            if amount < cls.MIN_AMOUNT:
                errors.append(f"amount {amount} below minimum {cls.MIN_AMOUNT}")
            if amount > cls.MAX_AMOUNT:
                errors.append(f"amount {amount} exceeds maximum {cls.MAX_AMOUNT}")
        except Exception as e:
            errors.append(f"amount conversion failed: {e}")
        
        try:
            price = to_decimal(tx.get('price_usd'))
            if price < cls.MIN_PRICE and price != Decimal(0):  # Allow 0 for income/transfers
                errors.append(f"price {price} below minimum {cls.MIN_PRICE}")
            if price > cls.MAX_PRICE:
                errors.append(f"price {price} exceeds maximum {cls.MAX_PRICE}")
        except Exception as e:
            errors.append(f"price_usd conversion failed: {e}")
        
        # Date validation
        try:
            from datetime import datetime
            date_str = tx.get('date', '')
            if not date_str:
                errors.append("date is empty")
            else:
                datetime.fromisoformat(date_str)
        except ValueError:
            errors.append(f"date '{tx.get('date')}' not ISO format")
        
        return len(errors) == 0, errors
    
    @classmethod
    def validate_batch(cls, transactions: List[Dict]) -> Tuple[int, List[Dict]]:
        """
        Validate a batch of transactions.
        
        Args:
            transactions: List of transaction dicts.
        
        Returns:
            (valid_count, invalid_transactions) — count of valid txs and list of invalid ones.
        """
        valid_count = 0
        invalid_txs = []
        
        for i, tx in enumerate(transactions):
            is_valid, errors = cls.validate_transaction(tx)
            if is_valid:
                valid_count += 1
            else:
                invalid_txs.append({
                    'index': i,
                    'transaction': tx,
                    'errors': errors
                })
        
        return valid_count, invalid_txs
    
    @classmethod
    def _is_custom_token(cls, token: str) -> bool:
        """Allow custom tokens with reasonable patterns."""
        # Allow ALL_CAPS, alphanumeric, hyphens (e.g., NFT-123, CUSTOM-TOK)
        return (
            len(token) <= 20 and
            token.replace('-', '').replace('_', '').isalnum()
        )


def validate_and_log(transactions: List[Dict]) -> List[Dict]:
    """
    Validate transactions and log issues, returning only valid ones.
    
    Args:
        transactions: List of transaction dicts.
    
    Returns:
        List of validated transactions (invalid ones filtered out).
    """
    valid_count, invalid_txs = TransactionValidator.validate_batch(transactions)
    
    if invalid_txs:
        import logging
        logger = logging.getLogger(__name__)
        for inv in invalid_txs:
            logger.warning(
                f"Invalid transaction at index {inv['index']}: {'; '.join(inv['errors'])}"
            )
    
    return [tx for tx in transactions 
            if TransactionValidator.validate_transaction(tx)[0]]
