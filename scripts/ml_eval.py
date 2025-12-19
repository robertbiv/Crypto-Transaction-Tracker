"""Simple evaluation harness for the ML shim.

Usage:
  python scripts/ml_eval.py [samples_csv]

If `label` column exists in the samples CSV, the script computes simple
accuracy/coverage metrics. Otherwise it prints model suggestions.
"""
import csv
import os
import sys
from collections import Counter

# Ensure local src is importable when running as a script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.ml_service import MLService


def load_samples(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)
    return rows


def evaluate(path):
    svc = MLService()
    rows = load_samples(path)
    total = 0
    correct = 0
    missing_label = 0
    confs = []
    counter = Counter()

    for r in rows:
        total += 1
        suggestion = svc.suggest(r)
        pred = suggestion.get('suggested_label')
        confs.append(suggestion.get('confidence', 0))
        counter[pred] += 1
        true = (r.get('label') or '').strip()
        if not true:
            missing_label += 1
        else:
            if pred.lower() == true.lower():
                correct += 1

    print(f"Rows: {total}")
    print(f"Missing true label: {missing_label}")
    if total - missing_label:
        print(f"Accuracy (on labeled rows): {correct}/{(total - missing_label)} = {correct / max(1, total - missing_label):.3f}")
    print("Prediction distribution:")
    for k, v in counter.most_common():
        print(f"  {k}: {v}")


def main():
    default = os.path.join(os.path.dirname(__file__), '..', 'outputs', 'ml_samples.csv')
    path = sys.argv[1] if len(sys.argv) > 1 else default
    if not os.path.exists(path):
        print("Samples file not found:", path)
        return
    evaluate(path)


if __name__ == '__main__':
    main()
