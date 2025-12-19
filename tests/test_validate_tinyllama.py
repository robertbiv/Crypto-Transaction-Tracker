"""
Validation tests for TinyLLaMA setup and core ML feature wiring.
These tests run heuristics-only code paths (no model download) so they stay fast.
"""

import json
from pathlib import Path
import pytest

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from advanced_ml_features_accurate import (
    FraudDetectorAccurate,
    SmartDescriptionGeneratorAccurate,
    PatternLearnerAccurate,
)

CONFIG_PATH = Path(__file__).parent.parent / "configs" / "config.json"


@pytest.fixture(scope="module")
def config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return json.load(f)
    else:
        # Return default config if file doesn't exist
        return {
            "ml": {
                "enabled": True,
                "model": "tinyllama",
                "auto_shutdown": True
            },
            "ml_fallback": {
                "enabled": True,
                "model_name": "tinyllama",
                "batch_size": 5,
                "auto_shutdown_after_batch": True
            },
            "accuracy_mode": {
                "enabled": True,
                "fraud_detection": True,
                "smart_descriptions": True,
                "pattern_learning": True,
                "natural_language_search": False
            },
            "anomaly_detection": {
                "enabled": True,
                "price_error_threshold": 0.15,
                "extreme_value_threshold": 3.0,
                "dust_threshold_usd": 1.0,
                "pattern_deviation_multiplier": 2.5,
                "min_transactions_for_learning": 10
            }
        }


@pytest.fixture(scope="module")
def fraud_detector():
    return FraudDetectorAccurate()


@pytest.fixture(scope="module")
def description_gen():
    return SmartDescriptionGeneratorAccurate()


@pytest.fixture(scope="module")
def pattern_learner():
    return PatternLearnerAccurate()


@pytest.fixture
def sample_transactions():
    return [
        {
            "action": "buy",
            "coin": "BTC",
            "amount": 1.0,
            "price_usd": 45000,
            "source": "binance",
            "date": "2024-06-01",
        },
        {
            "action": "sell",
            "coin": "ETH",
            "amount": 2.0,
            "price_usd": 2500,
            "source": "kraken",
            "date": "2024-06-02",
        },
    ]


def test_config_ml_settings(config):
    assert config["ml_fallback"]["enabled"] is True
    assert config["ml_fallback"]["model_name"] == "tinyllama"
    assert config["ml_fallback"]["batch_size"] == 5
    assert config["ml_fallback"]["auto_shutdown_after_batch"] is True


def test_config_accuracy_mode(config):
    acc = config["accuracy_mode"]
    assert acc["enabled"] is True
    assert acc["fraud_detection"] is True
    assert acc["smart_descriptions"] is True
    assert acc["pattern_learning"] is True
    assert acc["natural_language_search"] is False


def test_config_anomaly_detection(config):
    anomaly = config["anomaly_detection"]
    assert anomaly["enabled"] is True
    assert "price_error_threshold" in anomaly
    assert "extreme_value_threshold" in anomaly
    assert "dust_threshold_usd" in anomaly
    assert "pattern_deviation_multiplier" in anomaly
    assert "min_transactions_for_learning" in anomaly


def test_fraud_detection_runs(fraud_detector, sample_transactions):
    result = fraud_detector.detect_fraud_comprehensive(sample_transactions)
    assert isinstance(result, dict)
    for key in ["wash_sales", "pump_dumps", "suspicious_volumes", "gemma_analysis", "use_gemma"]:
        assert key in result


def test_smart_description_runs(description_gen, sample_transactions):
    tx = sample_transactions[0]
    out = description_gen.generate_description_smart(tx)
    assert isinstance(out, dict)
    assert "description" in out
    assert isinstance(out.get("description"), str)
    assert out.get("source") in {"heuristic", "gemma"}


def test_pattern_learning_runs(pattern_learner, sample_transactions):
    out = pattern_learner.learn_and_detect_accurate(sample_transactions)
    assert isinstance(out, dict)
    for key in ["statistical_anomalies", "behavioral_anomalies", "use_gemma"]:
        assert key in out


def test_suspicious_transaction_handled(fraud_detector):
    suspicious_tx = {
        "action": "buy",
        "coin": "BTC",
        "amount": 100.0,
        "price_usd": 5000,
        "source": "unknown_exchange",
        "date": "2024-06-04",
    }
    result = fraud_detector.detect_fraud_comprehensive([suspicious_tx])
    assert isinstance(result, dict)
