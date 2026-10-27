#!/usr/bin/env python3
"""Dependency-free, sentence-level nucleotide ROUGE/BLEU evaluation.

This is the ROUGE/BLEU subset of utr_v2_overlap_bleu_20261019.
No third-party package or model weights are needed to score saved predictions.
"""
import argparse
from collections import Counter, defaultdict
import csv
from functools import lru_cache
import gzip
import hashlib
import math
from pathlib import Path

VERSION = "utr_v2_overlap_bleu_20261019"
METRICS = ("rouge", "bleu", "rouge_1", "rouge_2", "rouge_3",
           "bleu_1", "bleu_2", "bleu_3")
KEYS = ("region", "model", "tissue")


def open_text(path, mode="rt"):
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    return opener(path, mode, encoding="utf-8-sig" if "r" in mode else "utf-8", newline="")


def dna(value, allow_empty=False):
    value = "".join(value.split()).upper()
    if (not value and not allow_empty) or set(value) - set("ACGT"):
        raise ValueError("Expected A/C/G/T DNA; only predictions may be empty")
    return value


@lru_cache(maxsize=50000)
def score(prediction, reference):
    """Clip overlapping 1/2/3-mer counts; return eight manuscript scores."""
    if set(prediction + reference) - set("ACGT") or not reference:
        raise ValueError("Metrics require DNA and a nonempty reference")
    recalls, precisions = [], []
    for order in (1, 2, 3):
        pred = Counter(prediction[i:i+order] for i in range(max(0, len(prediction)-order+1)))
        ref = Counter(reference[i:i+order] for i in range(max(0, len(reference)-order+1)))
        overlap = sum((pred & ref).values())
        recalls.append(overlap / sum(ref.values()) if ref else 0.0)
        precisions.append(overlap / sum(pred.values()) if pred else 0.0)
    bp = math.exp(min(0.0, 1.0-len(reference)/len(prediction))) if prediction else 0.0
    cumulative = []
    for order in (1, 2, 3):
        product = 1.0
        for precision in precisions[:order]:
            product *= precision
        cumulative.append(bp * product ** (1.0 / order))
    result = {"rouge": sum(recalls)/3, "bleu": sum(cumulative)/3}
    result.update({"rouge_{}".format(i+1): value for i, value in enumerate(recalls)})
    result.update({"bleu_{}".format(i+1): value for i, value in enumerate(cumulative)})
    return result


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path, args):
    with open_text(path) as source:
        reader = csv.DictReader(source)
        for index, row in enumerate(reader, 1):
            prediction = row[args.pred_column]
            reference = row[args.ref_column]
            yield {
                "region": args.region or row.get("region", "unspecified"),
                "model": args.model or row.get("model", "unspecified"),
                "tissue": args.tissue or row.get("tissue", "all"),
                "test_sequence": row.get("test_sequence", str(index)),
                "input_cds": row.get("input_cds", ""),
                "reference_utr": dna(reference),
                "predicted_utr": dna(prediction, allow_empty=True),
            }


def read_pairs(args):
    with open_text(args.prediction_file) as pred, open_text(args.reference_file) as ref:
        predictions, references = pred.read().splitlines(), ref.read().splitlines()
    if len(predictions) != len(references):
        raise ValueError("Prediction/reference line counts differ")
    for index, (prediction, reference) in enumerate(zip(predictions, references), 1):
        yield {"region": args.region or "unspecified", "model": args.model or "unspecified",
               "tissue": args.tissue or "all", "test_sequence": str(index), "input_cds": "",
               "reference_utr": dna(reference), "predicted_utr": dna(prediction, allow_empty=True)}


def write_csv(path, rows, fields=None):
    rows = list(rows)
    if not rows:
        return
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open_text(path, "wt") as target:
        writer = csv.DictWriter(target, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def evaluate(rows, output, per_sequence=False):
    groups, scored, seen = defaultdict(list), [], set()
    for row in rows:
        identity = tuple(row[k] for k in KEYS) + (row["test_sequence"],)
        if identity in seen:
            raise ValueError("Duplicate region/model/tissue/test_sequence: {}".format(identity))
        seen.add(identity)
        result = dict(row)
        result.update(score(row["predicted_utr"], row["reference_utr"]))
        result["predicted_length_nt"] = len(row["predicted_utr"])
        result["reference_length_nt"] = len(row["reference_utr"])
        groups[tuple(row[k] for k in KEYS)].append(result)
        scored.append(result)
    if not scored:
        raise ValueError("No predictions found")
    tissue_rows = []
    for key, values in sorted(groups.items()):
        result = dict(zip(KEYS, key))
        result["total_samples"] = len(values)
        result.update({metric: sum(value[metric] for value in values)/len(values) for metric in METRICS})
        for name in ("predicted", "reference"):
            result["mean_{}_length_nt".format(name)] = sum(value[name+"_length_nt"] for value in values)/len(values)
        result["empty_predictions"] = sum(not value["predicted_utr"] for value in values)
        result["metric_version"] = VERSION
        tissue_rows.append(result)
    macro_groups = defaultdict(list)
    for row in tissue_rows:
        macro_groups[(row["region"], row["model"])].append(row)
    macro_rows = []
    for (region, model), values in sorted(macro_groups.items()):
        result = {"region": region, "model": model, "tissues": len(values),
                  "total_samples": sum(value["total_samples"] for value in values),
                  "aggregation": "equal_weight_per_tissue"}
        result.update({metric: sum(value[metric] for value in values)/len(values) for metric in METRICS})
        macro_rows.append(result)
    output = Path(output)
    write_csv(output/"per_tissue_metrics.csv", tissue_rows)
    write_csv(output/"macro_metrics.csv", macro_rows)
    if per_sequence:
        write_csv(output/"per_sequence_metrics.csv.gz", scored)
    # Strict, unrounded comparisons against each method in the same region.
    win_rows = []
    for (region, model), values in sorted(macro_groups.items()):
        left = {value["tissue"]: value for value in values}
        for (other_region, other_model), other_values in sorted(macro_groups.items()):
            if region != other_region or model == other_model:
                continue
            right = {value["tissue"]: value for value in other_values}
            common = sorted(set(left) & set(right))
            for metric in ("rouge", "bleu"):
                differences = [left[t][metric]-right[t][metric] for t in common]
                win_rows.append({"region": region, "model": model, "comparator": other_model,
                                 "metric": metric, "matched_tissues": len(common),
                                 "wins": sum(d > 0 for d in differences),
                                 "ties": sum(d == 0 for d in differences),
                                 "losses": sum(d < 0 for d in differences)})
    write_csv(output/"pairwise_tissue_wins.csv", win_rows)
    return tissue_rows, macro_rows, win_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--predictions", type=Path, nargs="+", help="CSV/CSV.gz with predicted_utr and reference_utr")
    group.add_argument("--prediction-file", type=Path, help="One predicted DNA sequence per line")
    parser.add_argument("--reference-file", type=Path, help="One reference DNA sequence per line; preserve empty prediction lines")
    parser.add_argument("--pred-column", default="predicted_utr")
    parser.add_argument("--ref-column", default="reference_utr")
    parser.add_argument("--region", choices=("5utr", "3utr"))
    parser.add_argument("--model")
    parser.add_argument("--tissue")
    parser.add_argument("--output-dir", type=Path, default=Path("results/utr"))
    parser.add_argument("--per-sequence", action="store_true")
    args = parser.parse_args()
    if bool(args.prediction_file) != bool(args.reference_file):
        parser.error("--prediction-file and --reference-file must be supplied together")
    if args.predictions:
        rows = [row for path in args.predictions for row in read_csv(path, args)]
    else:
        rows = list(read_pairs(args))
    tissues, macros, wins = evaluate(rows, args.output_dir, args.per_sequence)
    print("Scored {} records; {} tissue/model groups.".format(len(rows), len(tissues)))
    for row in macros:
        print("{region:4} {model:16} n_tissues={tissues} ROUGE={rouge:.9f} BLEU={bleu:.9f}".format(**row))
    print("Saved results to {}".format(args.output_dir))


if __name__ == "__main__":
    main()
