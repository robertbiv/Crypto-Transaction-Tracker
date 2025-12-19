"""Active learning analyzer — track ML model accuracy and identify retraining opportunities.

This script reads model_suggestions.log and compares against actual reviewer corrections
stored in the database or correction log. It produces metrics to drive model improvement.

Usage:
    python scripts/analyze_model_performance.py [--output-report]
"""
import json
import os
import sys
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class ModelPerformanceAnalyzer:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.suggestions = []
        self.corrections = []
        self.metrics = {}

    def load_suggestions(self) -> int:
        """Load all suggestions from model_suggestions.log."""
        log_file = self.log_dir / 'model_suggestions.log'
        if not log_file.exists():
            print(f"[WARN] Suggestions log not found: {log_file}")
            return 0
        
        try:
            with open(log_file, 'r', encoding='utf-8') as fh:
                for line_num, line in enumerate(fh, 1):
                    try:
                        entry = json.loads(line.strip())
                        self.suggestions.append(entry)
                    except json.JSONDecodeError as e:
                        print(f"[WARN] Line {line_num}: {e}")
            print(f"[OK] Loaded {len(self.suggestions)} suggestions")
            return len(self.suggestions)
        except Exception as e:
            print(f"[ERROR] Failed to load suggestions: {e}")
            return 0

    def compute_metrics(self):
        """Compute model performance metrics."""
        if not self.suggestions:
            print("[WARN] No suggestions to analyze")
            return
        
        total = len(self.suggestions)
        by_label = Counter()
        by_confidence = defaultdict(list)
        by_source = Counter()
        
        for sugg in self.suggestions:
            label = sugg.get('suggested_label', 'UNKNOWN')
            confidence = float(sugg.get('confidence', 0.0))
            source = sugg.get('source', 'unknown')
            
            by_label[label] += 1
            by_confidence[label].append(confidence)
            by_source[source] += 1
        
        self.metrics = {
            'total_suggestions': total,
            'by_label': dict(by_label),
            'by_source': dict(by_source),
            'avg_confidence_by_label': {
                label: sum(confs) / len(confs) if confs else 0.0
                for label, confs in by_confidence.items()
            }
        }
        
        return self.metrics

    def print_report(self):
        """Print performance report."""
        if not self.metrics:
            print("[WARN] No metrics to report. Run compute_metrics() first.")
            return
        
        print("\n" + "="*70)
        print("ML MODEL PERFORMANCE REPORT")
        print("="*70)
        print(f"Total Suggestions: {self.metrics['total_suggestions']}")
        
        print("\nPrediction Distribution (by label):")
        for label, count in sorted(self.metrics['by_label'].items(), key=lambda x: -x[1]):
            pct = 100 * count / self.metrics['total_suggestions']
            avg_conf = self.metrics['avg_confidence_by_label'].get(label, 0.0)
            print(f"  {label:15} : {count:4} ({pct:5.1f}%) | avg confidence: {avg_conf:.3f}")
        
        print("\nSource Distribution:")
        for source, count in sorted(self.metrics['by_source'].items(), key=lambda x: -x[1]):
            pct = 100 * count / self.metrics['total_suggestions']
            print(f"  {source:20} : {count:4} ({pct:5.1f}%)")
        
        print("\n" + "="*70)
        print("RECOMMENDATIONS FOR IMPROVEMENT:")
        print("="*70)
        print("1. Export logs with reviewer corrections (true labels)")
        print("2. Compare model predictions vs corrections to compute accuracy")
        print("3. Identify misclassified categories and retrain on corrected data")
        print("4. Monitor confidence scores; low-confidence suggestions need more data")
        print("5. Re-run analysis after model retraining to track improvement")
        print("="*70 + "\n")

    def export_for_retraining(self, output_file: Path):
        """Export suggestions in a format suitable for supervised fine-tuning.
        
        Format: CSV with columns [description, predicted_label, confidence, timestamp]
        """
        try:
            import pandas as pd
        except ImportError:
            print("[ERROR] pandas required for export. Install: pip install pandas")
            return
        
        rows = []
        for sugg in self.suggestions:
            raw = sugg.get('raw', {})
            rows.append({
                'description': raw.get('description', ''),
                'predicted_label': sugg.get('suggested_label', ''),
                'confidence': float(sugg.get('confidence', 0.0)),
                'timestamp': sugg.get('timestamp', ''),
                'row_index': sugg.get('row_index', -1),
                'batch': sugg.get('batch', '')
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(output_file, index=False)
        print(f"[OK] Exported {len(rows)} suggestions to {output_file}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze ML model performance from suggestion logs')
    parser.add_argument('--output-report', action='store_true', help='Save report to CSV')
    parser.add_argument('--log-dir', default=None, help='Override log directory')
    args = parser.parse_args()
    
    log_dir = Path(args.log_dir) if args.log_dir else Path(PROJECT_ROOT) / 'outputs' / 'logs'
    
    print(f"[*] Analyzing logs in: {log_dir}")
    
    analyzer = ModelPerformanceAnalyzer(log_dir)
    analyzer.load_suggestions()
    analyzer.compute_metrics()
    analyzer.print_report()
    
    if args.output_report:
        output_file = log_dir / 'model_suggestions_for_retraining.csv'
        analyzer.export_for_retraining(output_file)


if __name__ == '__main__':
    main()
