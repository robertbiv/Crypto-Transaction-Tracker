"""Anomaly detection for crypto transactions.

Detects common data entry errors and suspicious patterns:
- Price entry errors (total value entered as per-unit price)
- Extreme amounts/prices
- Timestamp gaps and duplicates
"""
from typing import Dict, List
from decimal import Decimal, InvalidOperation
from src.decimal_utils import to_decimal
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    def __init__(self):
        """Initialize detector with heuristic thresholds."""
        pass

    def detect_price_error(self, row: Dict) -> Dict:
        """Detect if price might be total value entered as per-unit price.
        
        Common error: User enters transaction total ($5,000) into price column
        instead of per-unit price ($50,000/BTC for 0.1 BTC).
        
        Returns:
            {
                "anomaly": bool,
                "severity": "LOW" | "MEDIUM" | "HIGH",
                "message": str,
                "suggested_fix": str or None
            }
        """
        try:
            amount = float(row.get("amount", 0) or 0)
            price = float(row.get("price_usd", 0) or 0)
            
            if amount <= 0 or price <= 0:
                return {"anomaly": False, "severity": None, "message": None, "suggested_fix": None}
            
            # Skip dust amounts
            if amount < 0.00001:
                return {"anomaly": False, "severity": None, "message": None, "suggested_fix": None}
            
            implied_total = price * amount
            
            # Heuristic 1: Tiny amount with mid-range price
            # e.g., 0.001 BTC at "price" $50 but should be $50,000
            if amount <= 0.01 and 50 <= price <= 100000:
                corrected_price = price / amount
                return {
                    "anomaly": True,
                    "severity": "MEDIUM",
                    "message": f"Possible price entry error: {amount} units at ${price}/unit = ${implied_total:.2f} total.",
                    "suggested_fix": f"Verify: if correct per-unit price = ${corrected_price:.2f}"
                }
            
            # Heuristic 2: Small amount with high per-unit price
            # e.g., 0.1 BTC at $5,000 (implied $500 total) seems off if BTC=~$40k
            if 0.01 <= amount <= 0.5 and 1000 <= price <= 50000:
                corrected_price = price / amount
                return {
                    "anomaly": True,
                    "severity": "MEDIUM",
                    "message": f"Price entry suspicious: {amount} units at ${price}/unit. May be total value entered as price.",
                    "suggested_fix": f"Verify: actual per-unit price = ${corrected_price:.2f}"
                }
            
            return {"anomaly": False, "severity": None, "message": None, "suggested_fix": None}
            
        except (ValueError, TypeError):
            return {"anomaly": False, "severity": None, "message": None, "suggested_fix": None}

    def detect_timestamp_gap(self, row: Dict, prev_row: Dict = None) -> Dict:
        """Detect unusual gaps or ordering issues in timestamps."""
        if prev_row is None:
            return {"anomaly": False, "severity": None, "message": None}
        
        try:
            import pandas as pd
            curr_time = pd.to_datetime(row.get("date"), utc=True)
            prev_time = pd.to_datetime(prev_row.get("date"), utc=True)
            
            if pd.isna(curr_time) or pd.isna(prev_time):
                return {"anomaly": False, "severity": None, "message": None}
            
            # Out of order
            if curr_time < prev_time:
                return {
                    "anomaly": True,
                    "severity": "HIGH",
                    "message": f"Out-of-order timestamp: {row['date']} before previous {prev_row['date']}"
                }
            
            # Huge gap (>30 days)
            gap_days = (curr_time - prev_time).days
            if gap_days > 30:
                return {
                    "anomaly": True,
                    "severity": "LOW",
                    "message": f"Large gap: {gap_days} days since last transaction"
                }
            
            return {"anomaly": False, "severity": None, "message": None}
            
        except Exception:
            return {"anomaly": False, "severity": None, "message": None}

    def detect_extreme_value(self, row: Dict) -> Dict:
        """Flag extremely high or low transaction values."""
        try:
            amount = float(row.get("amount", 0) or 0)
            price = float(row.get("price_usd", 0) or 0)
            total = amount * price
            
            # Extreme high (> $1M)
            if total > 1_000_000:
                return {
                    "anomaly": True,
                    "severity": "MEDIUM",
                    "message": f"Extremely high transaction value: ${total:,.2f}. Verify amount and price."
                }
            
            # Extreme low (< $0.01, likely dust)
            if 0 < total < 0.01:
                return {
                    "anomaly": True,
                    "severity": "LOW",
                    "message": f"Dust amount: ${total:.6f}. May be test transaction or rounding error."
                }
            
            return {"anomaly": False, "severity": None, "message": None}
            
        except Exception:
            return {"anomaly": False, "severity": None, "message": None}

    def scan_row(self, row: Dict, prev_row: Dict = None) -> List[Dict]:
        """Run all anomaly checks on a row.
        
        Returns list of detected anomalies.
        """
        anomalies = []
        
        price_check = self.detect_price_error(row)
        if price_check.get("anomaly"):
            anomalies.append({"type": "PRICE_ERROR", **price_check})
        
        extreme_check = self.detect_extreme_value(row)
        if extreme_check.get("anomaly"):
            anomalies.append({"type": "EXTREME_VALUE", **extreme_check})
        
        if prev_row:
            gap_check = self.detect_timestamp_gap(row, prev_row)
            if gap_check.get("anomaly"):
                anomalies.append({"type": "TIMESTAMP_GAP", **gap_check})
        
        return anomalies

    def is_price_anomaly(self, price: float, recent_prices: List[float]) -> bool:
        """Simple range-based price anomaly check used in integration tests."""
        if price is None:
            return False
        try:
            numeric_prices = [to_decimal(p) for p in recent_prices if p is not None]
            current = to_decimal(price)
        except (InvalidOperation, ValueError, TypeError):
            return False
        if not numeric_prices:
            return False
        avg = sum(numeric_prices) / Decimal(len(numeric_prices))
        max_allowed = avg * Decimal(3)
        min_allowed = avg * Decimal('0.1')
        return current > max_allowed or current < min_allowed


def demo():
    detector = AnomalyDetector()
    
    # Test case 1: Price error (common mistake)
    row1 = {"description": "BTC purchase", "amount": 0.1, "price_usd": 5000}
    result1 = detector.scan_row(row1)
    print("Test 1 (price error):", result1)
    
    # Test case 2: Normal transaction
    row2 = {"description": "BTC purchase", "amount": 0.1, "price_usd": 42000}
    result2 = detector.scan_row(row2)
    print("Test 2 (normal):", result2)
    
    # Test case 3: Extreme value
    row3 = {"description": "ETH trade", "amount": 1000, "price_usd": 5000}
    result3 = detector.scan_row(row3)
    print("Test 3 (extreme):", result3)


if __name__ == "__main__":
    demo()
