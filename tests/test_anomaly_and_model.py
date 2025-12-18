"""Tests for anomaly detection and real model loading."""
import os
import sys
import pandas as pd
import pytest

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.anomaly_detector import AnomalyDetector
from src.ml_service import MLService


class TestAnomalyDetector:
    def test_price_error_detection(self):
        detector = AnomalyDetector()
        row = {"amount": 0.01, "price_usd": 50}  # Likely total entered as price
        result = detector.detect_price_error(row)
        assert result["anomaly"] is True
        assert result["severity"] == "MEDIUM"

    def test_no_false_positive_normal_price(self):
        detector = AnomalyDetector()
        row = {"amount": 2.5, "price_usd": 42000}  # Normal BTC price, larger amount
        result = detector.detect_price_error(row)
        assert result["anomaly"] is False

    def test_extreme_value_detection(self):
        detector = AnomalyDetector()
        row = {"amount": 1000, "price_usd": 5000}  # $5M transaction
        result = detector.detect_extreme_value(row)
        assert result["anomaly"] is True
        assert result["severity"] == "MEDIUM"

    def test_dust_detection(self):
        detector = AnomalyDetector()
        row = {"amount": 0.000001, "price_usd": 0.01}  # Dust amount
        result = detector.detect_extreme_value(row)
        assert result["anomaly"] is True
        assert result["severity"] == "LOW"

    def test_scan_row_multiple_checks(self):
        detector = AnomalyDetector()
        row = {"amount": 0.01, "price_usd": 50, "description": "test"}
        anomalies = detector.scan_row(row)
        assert len(anomalies) >= 1
        assert any(a["type"] == "PRICE_ERROR" for a in anomalies)


class TestMLService:
    def test_shim_mode_basic(self):
        svc = MLService(mode="shim")
        tx = {"description": "Bought BTC", "amount": "0.1"}
        result = svc.suggest(tx)
        assert result["suggested_label"] == "BUY"
        assert result["confidence"] > 0.9

    def test_gemma_mode_graceful_fallback(self):
        """Gemma mode should fall back to shim if model not available."""
        svc = MLService(mode="gemma")
        tx = {"description": "Bought BTC", "amount": "0.1"}
        result = svc.suggest(tx)
        # Should return something (either real model or fallback to shim)
        assert result["suggested_label"] in {"BUY", "TRANSFER"}

    def test_auto_shutdown(self):
        svc = MLService(mode="shim", auto_shutdown_after_inference=True)
        tx = {"description": "Fee charge", "amount": "0.0001"}
        result = svc.suggest(tx)
        assert result["suggested_label"] == "FEE"
        # Shutdown should not raise
        svc.shutdown()

    def test_all_transaction_types(self):
        svc = MLService(mode="shim")
        test_cases = [
            ({"description": "Bought BTC", "amount": "1"}, "BUY"),
            ({"description": "Sold ETH", "amount": "1"}, "SELL"),
            ({"description": "Deposit to wallet", "amount": "1"}, "DEPOSIT"),
            ({"description": "Withdraw funds", "amount": "1"}, "WITHDRAWAL"),
            ({"description": "Network fee", "amount": "0.001"}, "FEE"),
        ]
        for tx, expected_label in test_cases:
            result = svc.suggest(tx)
            assert result["suggested_label"] == expected_label, f"Failed for {tx}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
