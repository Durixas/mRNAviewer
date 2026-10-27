#!/usr/bin/env python3
"""Recompute pooled codon accuracy from saved prediction CSV(.gz), using only stdlib."""
import argparse
import csv
import json
from pathlib import Path
from metrics import DEFAULT_DATA, load_records, open_text, score_rows, sha256, write_csv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--tissues", nargs="+")
    parser.add_argument("--model", required=True, help="Method name used in the output")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-subset", action="store_true", help="Explicitly permit an incomplete pilot table")
    args = parser.parse_args()
    records = load_records(args.data_root, args.tissues)
    with open_text(args.predictions) as handle:
        rows = list(csv.DictReader(handle))
    if args.tissues:
        rows = [r for r in rows if r["tissue"] in args.tissues]
    metrics, _ = score_rows(records, rows, args.model, args.allow_subset)
    write_csv(args.output, metrics)
    metadata = {"prediction_sha256": sha256(args.predictions), "prediction_file": str(args.predictions),
                "data_root": str(args.data_root), "allow_subset": args.allow_subset,
                "test_files_sha256": {r["tissue"]: sha256(args.data_root / r["tissue"] / "test.txt") for r in metrics},
                "macro_test_acc": sum(r["test_acc"] for r in metrics) / len(metrics),
                "total_sequences": sum(r["test_sequences"] for r in metrics)}
    args.output.with_suffix(args.output.suffix + ".provenance.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print("{} tissues; {} sequences; macro accuracy {:.6f}%".format(
        len(metrics), metadata["total_sequences"], 100 * metadata["macro_test_acc"]))


if __name__ == "__main__":
    main()
