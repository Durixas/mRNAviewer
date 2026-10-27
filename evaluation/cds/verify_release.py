#!/usr/bin/env python3
"""CPU-only audit: check packaged hashes and recompute comparator codon counts."""
import argparse
import csv
import json
from pathlib import Path
from metrics import DEFAULT_DATA, load_records, open_text, score_rows, sha256


HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    manifest = json.loads((HERE / "archived/provenance.json").read_text())
    for item in manifest["files"]:
        path = HERE / item["path"]
        if sha256(path) != item["packaged_sha256"]:
            raise ValueError("Packaged checksum mismatch: {}".format(path))
    records = load_records(args.data_root)
    if len(records) != 5682 or len({row["tissue"] for row in records}) != 29:
        raise ValueError("Expected 5,682 test sequences in 29 tissues")
    for method in ("gemorna", "codontransformer", "mrnasyner", "mrnasyner_native"):
        prediction_path = HERE / "archived/predictions" / (method + "_cds_predictions.csv.gz")
        with open_text(prediction_path) as handle:
            metrics, _ = score_rows(records, csv.DictReader(handle), method)
        with (HERE / "archived/metrics" / ("cds_" + method + "_test_acc.csv")).open(newline="") as handle:
            reference = {row["tissue"]: row for row in csv.DictReader(handle)}
        for row in metrics:
            old = reference[row["tissue"]]
            for key in ("correct_positions", "total_positions", "test_sequences", "coding_correct_codons", "coding_total_codons", "stop_correct_sequences"):
                if row[key] != int(old[key]):
                    raise ValueError("{} {} {} differs: {} vs {}".format(method, row["tissue"], key, row[key], old[key]))
            if "{:.6f}".format(row["test_acc"]) != old["test_acc"]:
                raise ValueError("Rounded accuracy mismatch")
        print("{}: 5682 predictions; all integer counts and 29 archived accuracies match".format(method))
    print("All {} packaged file checksums match".format(len(manifest["files"])))


if __name__ == "__main__":
    main()
