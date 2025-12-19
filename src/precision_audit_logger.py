"""
Precision audit logging for tax-critical operations.
Logs all fraud detection, fee calculations, and tax-sensitive computations
with full Decimal precision for audit trails and debugging.
"""

import logging
import json
from decimal import Decimal
from typing import Dict, Any
from datetime import datetime


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that preserves Decimal precision."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def create_precision_logger(name: str) -> logging.Logger:
    """Create a logger for precision-critical operations."""
    logger = logging.getLogger(name)
    
    # File handler with JSON format for machine parsing
    handler = logging.FileHandler('outputs/logs/precision_audit.log')
    formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    
    return logger


# Global precision logger
precision_logger = create_precision_logger('precision_audit')


def log_fraud_detection(
    tx: Dict[str, Any],
    fraud_score: Decimal,
    flags: Dict[str, Any]
) -> None:
    """Log fraud detection with full precision."""
    precision_logger.info(
        f"FRAUD_DETECTION | tx_id={tx.get('id')} | "
        f"coin={tx.get('coin')} | amount={tx.get('amount')} | "
        f"price={tx.get('price_usd')} | fraud_score={fraud_score} | "
        f"flags={json.dumps(flags, cls=DecimalEncoder)}"
    )


def log_fee_calculation(
    tx_id: str,
    total_value: Decimal,
    fee: Decimal,
    fee_pct: Decimal
) -> None:
    """Log fee calculation with full precision."""
    precision_logger.info(
        f"FEE_CALC | tx_id={tx_id} | "
        f"total_value={total_value} | fee={fee} | fee_pct={fee_pct}%"
    )


def log_tax_calculation(
    tx_id: str,
    action: str,
    coin: str,
    amount: Decimal,
    price_usd: Decimal,
    proceeds: Decimal,
    cost_basis: Decimal,
    capital_gain: Decimal
) -> None:
    """Log tax calculation with full precision."""
    precision_logger.info(
        f"TAX_CALC | tx_id={tx_id} | action={action} | "
        f"coin={coin} | amount={amount} | price_usd={price_usd} | "
        f"proceeds={proceeds} | cost_basis={cost_basis} | "
        f"capital_gain={capital_gain}"
    )


def log_wash_sale_detection(
    coin: str,
    buy_tx_id: str,
    sell_tx_id: str,
    buy_price: Decimal,
    sell_price: Decimal,
    days_apart: int
) -> None:
    """Log wash sale detection with full precision."""
    precision_logger.warning(
        f"WASH_SALE | coin={coin} | "
        f"buy_tx={buy_tx_id} @ {buy_price} | "
        f"sell_tx={sell_tx_id} @ {sell_price} | "
        f"days_apart={days_apart}"
    )


def log_structuring_alert(
    total_value: Decimal,
    num_txs: int,
    days: int,
    avg_per_tx: Decimal
) -> None:
    """Log structuring (AML) alert with full precision."""
    precision_logger.warning(
        f"STRUCTURING | total_value={total_value} | "
        f"num_txs={num_txs} | days_span={days} | avg_per_tx={avg_per_tx}"
    )


def log_anomaly_detection(
    tx_id: str,
    anomaly_type: str,
    expected: Decimal,
    actual: Decimal,
    deviation_pct: Decimal
) -> None:
    """Log anomaly detection with full precision."""
    precision_logger.info(
        f"ANOMALY | tx_id={tx_id} | type={anomaly_type} | "
        f"expected={expected} | actual={actual} | deviation={deviation_pct}%"
    )
