#!/usr/bin/env python3
"""Reproduce the archived manuscript benchmarks without GPUs or model weights."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=root / "results")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    stages = [
        ("Verify and extract processed tissue datasets", ["data/extract.py"]),
        ("Verify and re-score archived CDS predictions", ["evaluation/cds/verify_release.py"]),
        ("Summarize archived ORF results and log selections", ["evaluation/cds/summarize_archived.py", "--output-dir", str(output / "cds")]),
        ("Recompute UTR ROUGE and BLEU", ["evaluation/utr/evaluate.py", "--archive", "--output-dir", str(output / "utr")]),
        ("Audit UTR tables against saved scores and manuscript means", ["evaluation/utr/audit_results.py", "--results-dir", str(output / "utr")]),
    ]
    for label, command in stages:
        print("\n" + label, flush=True)
        subprocess.run([sys.executable] + command, cwd=str(root), check=True)
    print("\nReproduction completed. Results: {}".format(output), flush=True)


if __name__ == "__main__":
    main()
