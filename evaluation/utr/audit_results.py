#!/usr/bin/env python3
"""Audit reproduced ROUGE/BLEU tables and the manuscript's rounded claims."""
import argparse
import csv
import json
from pathlib import Path

from evaluate import METRICS

HERE = Path(__file__).resolve().parent
EXPECTED = {
    ("5utr", "bert2bert_best"): (0.772, 0.541),
    ("5utr", "bart_base"): (0.563, 0.425),
    ("5utr", "mrnasyner"): (0.742, 0.531),
    ("3utr", "bert2bert_best"): (0.828, 0.699),
    ("3utr", "bart_base"): (0.641, 0.470),
    ("3utr", "mrnasyner"): (0.766, 0.526),
}


def load(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as source:
        return list(csv.DictReader(source))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=HERE/"published_results")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    reference = {(r["region"], r["model"], r["tissue"]): r for r in load(HERE/"reference_per_tissue_metrics.csv")}
    results = {(r["region"], r["model"], r["tissue"]): r for r in load(args.results_dir/"per_tissue_metrics.csv")}
    if set(results) != set(reference) or len(results) != 174:
        raise ValueError("Expected the same 174 tissue/model rows as the saved evaluation")
    maximum_error = 0.0
    for key, row in results.items():
        if row["total_samples"] != reference[key]["total_samples"]:
            raise ValueError("Sample count differs: {}".format(key))
        for metric in METRICS:
            error = abs(float(row[metric])-float(reference[key][metric]))
            maximum_error = max(error, maximum_error)
            if error > 1e-12:
                raise ValueError("Saved metric differs: {} {} {}".format(key, metric, error))
    macro = {(r["region"], r["model"]): r for r in load(args.results_dir/"macro_metrics.csv")}
    if set(macro) != set(EXPECTED):
        raise ValueError("Expected all six region/model macro rows")
    for key, expected in EXPECTED.items():
        row = macro[key]
        if int(row["tissues"]) != 29 or row["aggregation"] != "equal_weight_per_tissue":
            raise ValueError("Macro statistics must equally weight all 29 tissues")
        actual = tuple(round(float(row[m]), 3) for m in ("rouge", "bleu"))
        if actual != expected:
            raise ValueError("Manuscript mean differs: {} {} versus {}".format(key, actual, expected))
    wins = load(args.results_dir/"pairwise_tissue_wins.csv")
    selected = [r for r in wins if r["model"] == "bert2bert_best" and r["comparator"] == "mrnasyner"]
    expected_wins = {("3utr", "rouge"): 28, ("3utr", "bleu"): 29,
                     ("5utr", "rouge"): 23, ("5utr", "bleu"): 16}
    if len(selected) != 4:
        raise ValueError("Missing BERT2BERT/mRNASyner comparisons")
    for row in selected:
        if int(row["matched_tissues"]) != 29 or int(row["wins"]) != expected_wins[(row["region"], row["metric"])]:
            raise ValueError("Tissue win count differs: {}".format(row))
    report = {"status": "passed", "per_tissue_rows": len(results),
              "metric_fields_per_row": len(METRICS), "maximum_absolute_error": maximum_error,
              "manuscript_rounded_macro_means_match": True,
              "three_prime_manuscript_win_counts_match": True,
              "bert2bert_vs_mrnasyner": selected,
              "interpretation": "The manuscript's 28 ROUGE / 29 BLEU tissue wins apply to 3-prime UTR. The 5-prime win counts are 23 / 16."}
    output = args.output or args.results_dir/"audit.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
