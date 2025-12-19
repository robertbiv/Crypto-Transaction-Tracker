"""Tests for the ML shim and rules→model bridge."""
import os
import sys
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ml_service import MLService
from src.rules_model_bridge import classify
import src.core.engine as engine


def test_ml_service_buy_keyword():
    svc = MLService()
    tx = {"description": "Bought BTC on Binance", "amount": "0.5"}
    out = svc.suggest(tx)
    assert out["suggested_label"] == "BUY"
    assert out["confidence"] > 0.9


def test_bridge_prefers_rules():
    def fake_rules(tx):
        return "INCOME"

    tx = {"description": "Airdrop", "amount": "5"}
    out = classify(tx, rules_fn=fake_rules)
    assert out["label"] == "INCOME"
    assert out["source"] == "rules"
    assert out["confidence"] == 1.0


def test_bridge_falls_back_to_ml_when_rules_none():
    def fake_rules_none(tx):
        return None

    tx = {"description": "Withdrawal to wallet", "amount": "1.0"}
    out = classify(tx, rules_fn=fake_rules_none)
    assert out["source"] == "ml_fallback"
    assert out["label"] in {"WITHDRAWAL", "TRANSFER"}
    assert out["confidence"] >= 0.58


def test_ingestor_ml_fallback_logs(tmp_path, monkeypatch):
    class DummyDB:
        pass

    ingest = engine.Ingestor(db=DummyDB())
    ingest.ml_enabled = True
    ingest.ml_service = MLService()

    log_path = tmp_path / "ml_log.log"
    monkeypatch.setattr(engine, "ML_LOG_FILE", log_path, raising=False)
    monkeypatch.setattr(engine, "LOG_DIR", tmp_path, raising=False)

    row = pd.Series({"description": "Withdrawal to wallet", "amount": "1.0"})
    ingest._ml_fallback(row, batch="TEST", idx=0)

    assert log_path.exists()
    content = log_path.read_text().strip().splitlines()
    assert len(content) >= 1
