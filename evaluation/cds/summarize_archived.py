#!/usr/bin/env python3
"""Recreate the manuscript Fig. 1C table and equally weighted tissue means.

The mRNAviewer column is explicitly the archived maximum test score over epochs.
Fresh checkpoint inference belongs in a separate column/table.
"""
import argparse
import csv
import json
import re
from pathlib import Path
from metrics import open_text, write_csv


HERE = Path(__file__).resolve().parent
METHODS = {
    "mRNAviewer_historical_max_test": ("cds_max_test_acc.csv", "max_test_acc"),
    "general_iDRO": ("cds_general_test_acc.csv", "test_acc"),
    "GEMORNA": ("cds_gemorna_test_acc.csv", "test_acc"),
    "CodonTransformer": ("cds_codontransformer_test_acc.csv", "test_acc"),
    "mRNASyner_synonymous": ("cds_mrnasyner_test_acc.csv", "test_acc"),
}


def read_table(path):
    with open_text(path) as handle:
        rows = list(csv.DictReader(handle))
    if len({row["tissue"] for row in rows}) != len(rows):
        raise ValueError("Duplicate tissue rows: {}".format(path))
    return {row["tissue"]: row for row in rows}


def parse_log(path):
    with open_text(path) as handle:
        lines = list(handle)
    epochs, current = {}, None
    for line in lines:
        match = re.search(r"^Epoch: (\d+)/\d+", line)
        if match:
            current = int(match.group(1))
            epochs[current] = {"epoch": current, "checkpoint_saved": False}
        if current is None:
            continue
        if line.startswith("Save current best model in file:"):
            epochs[current]["checkpoint_saved"] = True
            epochs[current]["checkpoint_at_training_time"] = line.split(":", 1)[1].strip()
        match = re.search(r"^Test:.*acc:\s*([\d.]+)", line)
        if match:
            epochs[current]["test_acc"] = float(match.group(1))
        match = re.search(r"^Dev:.*acc:\s*([\d.]+)", line)
        if match:
            epochs[current]["dev_acc"] = float(match.group(1))
    complete = [row for row in epochs.values() if "test_acc" in row]
    if not complete:
        raise ValueError("No epoch test results: {}".format(path))
    maximum = max(complete, key=lambda row: row["test_acc"])
    saved = [row for row in complete if row["checkpoint_saved"]]
    if not saved:
        raise ValueError("No saved checkpoint in log: {}".format(path))
    last_saved = saved[-1]
    return maximum, last_saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archived", type=Path, default=HERE / "archived")
    parser.add_argument("--output-dir", type=Path, default=HERE / "results")
    parser.add_argument("--checkpoint-metrics", type=Path,
                        help="Optional freshly evaluated 29-tissue CSV; adds a separate column")
    args = parser.parse_args()
    methods = dict(METHODS)
    tables = {method: read_table(args.archived / "metrics" / filename)
              for method, (filename, _) in methods.items()}
    if args.checkpoint_metrics:
        methods["mRNAviewer_current_checkpoint"] = (str(args.checkpoint_metrics), "test_acc")
        tables["mRNAviewer_current_checkpoint"] = read_table(args.checkpoint_metrics)
    tissue_set = set(tables["general_iDRO"])
    if len(tissue_set) != 29 or any(set(table) != tissue_set for table in tables.values()):
        raise ValueError("Every method must have exactly the same 29 tissues")
    rows = []
    for tissue in sorted(tissue_set):
        rows.append({"tissue": tissue, **{method: float(tables[method][tissue][column])
                     for method, (_, column) in methods.items()}})
    means = []
    for method in methods:
        mean = sum(row[method] for row in rows) / len(rows)
        means.append({"model": method, "n_tissues": 29, "macro_accuracy": mean,
                      "macro_accuracy_percent": mean * 100,
                      "accuracy_percent_2dp": "{:.2f}".format(mean * 100)})
    audit = []
    for tissue in sorted(tissue_set):
        maximum, last_saved = parse_log(args.archived / "finetune_logs" / (tissue + "_finetune.log.gz"))
        archived = tables["mRNAviewer_historical_max_test"][tissue]
        if maximum["test_acc"] != float(archived["max_test_acc"]) or maximum["epoch"] != int(archived["epoch"]):
            raise ValueError("Log and archived maximum disagree: {}".format(tissue))
        record = {"tissue": tissue, "archived_max_test_acc": maximum["test_acc"],
                  "archived_max_test_epoch_1_based": maximum["epoch"],
                  "last_dev_selected_epoch_1_based": last_saved["epoch"],
                  "test_acc_at_last_dev_selected_epoch": last_saved["test_acc"],
                  "difference_historical_max_minus_last_dev_selected": maximum["test_acc"] - last_saved["test_acc"],
                  "checkpoint_at_training_time": last_saved["checkpoint_at_training_time"],
                  "note": "Historical training log selection comparison only; the deployed renamed checkpoint need not be the last dev-selected epoch. Use evaluate_checkpoint.py to measure weights."}
        if args.checkpoint_metrics:
            actual = float(tables["mRNAviewer_current_checkpoint"][tissue]["test_acc"])
            record["fresh_checkpoint_test_acc"] = actual
            record["fresh_minus_archived_max"] = actual - maximum["test_acc"]
        audit.append(record)
    write_csv(args.output_dir / "fig1c_per_tissue.csv", rows)
    write_csv(args.output_dir / "fig1c_macro_accuracy.csv", means)
    write_csv(args.output_dir / "checkpoint_selection_audit.csv", audit)
    for row in means:
        print("{}: {}%".format(row["model"], row["accuracy_percent_2dp"]))
    print("{} tissues have different maximum-test and last-dev-selected logged scores".format(
        sum(abs(row["difference_historical_max_minus_last_dev_selected"]) > 1e-12 for row in audit)))


if __name__ == "__main__":
    main()
