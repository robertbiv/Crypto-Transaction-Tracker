"""
Edge-case unit tests for TinyLLaMA feature wiring (heuristic-only paths).
Covers malformed inputs, missing fields, extreme values, and failure-path behavior.
"""

import json
from pathlib import Path
import pytest
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from advanced_ml_features_accurate import (
    FraudDetectorAccurate,
    SmartDescriptionGeneratorAccurate,
    PatternLearnerAccurate,
)


@pytest.fixture(scope="module")
def fraud_detector():
    return FraudDetectorAccurate()


@pytest.fixture(scope="module")
def description_gen():
    return SmartDescriptionGeneratorAccurate()


@pytest.fixture(scope="module")
def pattern_learner():
    return PatternLearnerAccurate()


def test_fraud_handles_missing_fields(fraud_detector):
    tx = {"action": "buy", "coin": "BTC"}  # missing price_usd/amount/source/date
    out = fraud_detector.detect_fraud_comprehensive([tx])
    assert isinstance(out, dict)


def test_fraud_handles_negative_and_zero(fraud_detector):
    txs = [
        {"action": "buy", "coin": "BTC", "amount": -1, "price_usd": 45000, "source": "binance"},
        {"action": "buy", "coin": "BTC", "amount": 0, "price_usd": 0, "source": "binance"},
    ]
    out = fraud_detector.detect_fraud_comprehensive(txs)
    assert isinstance(out, dict)


def test_description_handles_special_chars(description_gen):
    tx = {
        "action": "buy",
        "coin": "BTC<script>",
        "amount": 1.0,
        "price_usd": 45000,
        "source": "exchange",
        "date": "2024-06-01",
        "description": "<script>alert('x')</script>",
    }
    out = description_gen.generate_description_smart(tx)
    assert isinstance(out, dict)
    assert "description" in out


def test_description_handles_unicode(description_gen):
    tx = {
        "action": "buy",
        "coin": "BTC",
        "amount": 1.0,
        "price_usd": 45000,
        "source": "binance_中文",
        "date": "2024-06-01",
    }
    out = description_gen.generate_description_smart(tx)
    assert isinstance(out, dict)


def test_pattern_handles_empty_list(pattern_learner):
    out = pattern_learner.learn_and_detect_accurate([])
    assert isinstance(out, dict)
    assert "statistical_anomalies" in out


def test_pattern_handles_minimal_transaction(pattern_learner):
    txs = [{"action": "buy", "coin": "BTC", "amount": 1.0, "price_usd": 45000, "source": "binance"}]
    out = pattern_learner.learn_and_detect_accurate(txs)
    assert isinstance(out, dict)


def test_fraud_handles_unexpected_types(fraud_detector):
    txs = [
        {},  # empty dict
        {"action": "buy", "coin": "BTC"},  # missing price/amount
        {"action": "buy", "coin": "BTC", "amount": 1.0, "price_usd": "45000"},  # string price
    ]
    out = fraud_detector.detect_fraud_comprehensive(txs)  # should not raise
    assert isinstance(out, dict)


def test_description_handles_unexpected_types(description_gen):
    tx = {"action": "buy", "coin": "BTC", "amount": "1.0", "price_usd": "45000"}
    out = description_gen.generate_description_smart(tx)
    assert isinstance(out, dict)


def test_pattern_handles_unexpected_types(pattern_learner):
    txs = [{"action": "buy", "coin": "BTC", "amount": "1.0", "price_usd": "45000"}]
    out = pattern_learner.learn_and_detect_accurate(txs)
    assert isinstance(out, dict)
