"""Extract small labeled sample CSVs from processed_archive for ML prototyping.

Usage:
  python scripts/extract_samples.py [output_csv] [max_rows]

Default output: outputs/ml_samples.csv
"""
import csv
import glob
import os
import sys
from typing import List


def find_proc_files(directory: str) -> List[str]:
    pattern = os.path.join(directory, "*_PROC_*.csv")
    return sorted(glob.glob(pattern))


def sample_from_file(path: str, max_rows: int = 200):
    rows = []
    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        count = 0
        for r in reader:
            if count >= max_rows:
                break
            # Keep a small set of useful fields
            out = {
                'source_file': os.path.basename(path),
                'description': r.get('description') or r.get('memo') or r.get('note') or r.get('Description') or '',
                'amount': r.get('amount') or r.get('Quantity') or r.get('qty') or '',
                'symbol': r.get('symbol') or r.get('Token') or r.get('Asset') or '',
                'label': r.get('type') or r.get('side') or r.get('label') or ''
            }
            rows.append(out)
            count += 1
    return rows


def main():
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    proc_dir = os.path.join(workspace_root, 'processed_archive')
    out_default = os.path.join(workspace_root, 'outputs', 'ml_samples.csv')

    out_csv = sys.argv[1] if len(sys.argv) > 1 else out_default
    max_rows = int(sys.argv[2]) if len(sys.argv) > 2 else 1000

    files = find_proc_files(proc_dir)
    if not files:
        print("No processed_archive files found in:", proc_dir)
        return

    collected = []
    per_file = max(1, max_rows // max(1, len(files)))
    for f in files:
        collected.extend(sample_from_file(f, per_file))

    # write output
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=['source_file', 'description', 'amount', 'symbol', 'label'])
        writer.writeheader()
        for r in collected:
            writer.writerow(r)

    print(f"Wrote {len(collected)} samples to {out_csv}")


if __name__ == '__main__':
    main()
