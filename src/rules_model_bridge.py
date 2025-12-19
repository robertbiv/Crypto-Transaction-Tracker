"""Rules-first classification bridge.

This module provides a small integration helper that runs deterministic
rules first and falls back to the ML service only when necessary.
It is intentionally minimal so it can be wired into the existing
engine/reviewer code (pass your real rule-function into `classify`).
"""
from typing import Callable, Dict, Optional
from .ml_service import MLService


def classify(row: Dict, rules_fn: Optional[Callable[[Dict], Optional[str]]] = None, ml: Optional[MLService] = None) -> Dict:
    """Classify a transaction row using rules-first then ML fallback.

    - `rules_fn` should accept a row dict and return a label string
      (e.g., "BUY", "DEPOSIT") or None if it cannot decide.
    - Returns a dict with at least: label/source/confidence/explanation.
    """
    # 1) Try rules function if provided
    if rules_fn is not None:
        try:
            rules_label = rules_fn(row)
            if rules_label:
                return {"label": rules_label, "source": "rules", "confidence": 1.0, "explanation": "deterministic rule matched"}
        except Exception:
            # swallow rule exceptions and fall back to ML
            pass

    # 2) Minimal built-in rules to cover common fields (non-invasive)
    if row.get("type"):
        return {"label": str(row.get("type")).upper(), "source": "rules_field", "confidence": 1.0, "explanation": "had explicit type field"}
    if row.get("side"):
        return {"label": str(row.get("side")).upper(), "source": "rules_field", "confidence": 1.0, "explanation": "had explicit side field"}

    # 3) Fall back to ML
    if ml is None:
        ml = MLService()

    suggestion = ml.suggest(row)
    return {"label": suggestion.get("suggested_label"), "source": "ml_fallback", "confidence": suggestion.get("confidence", 0.0), "explanation": suggestion.get("explanation", "")}


if __name__ == "__main__":
    # tiny interactive demo
    demo_rows = [
        {"description": "Bought BTC on Binance", "amount": "0.1"},
        {"description": "Fee: network fee", "amount": "0.0002"},
        {"type": "income", "description": "Airdrop reward", "amount": "5"},
    ]

    for r in demo_rows:
        print(classify(r))
