#!/usr/bin/env python3
"""Re-score the GPU deployment checks and optionally verify restored weights."""
import argparse
import csv
import json
from pathlib import Path

from metrics import DEFAULT_DATA, REPOSITORY, load_records, open_text, score_rows, sha256, write_csv

HERE = Path(__file__).resolve().parent


def read_csv(path):
    with open_text(path) as handle:
        return list(csv.DictReader(handle))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=HERE / "verification/gpu_deployed_20261026")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--model-root", type=Path,
                        help="Optionally verify all tested checkpoints under this directory")
    parser.add_argument("--require-historical-match", choices=("3dp", "4dp"),
                        help="Additionally fail if fresh and historical scores differ at this precision")
    parser.add_argument("--output-dir", type=Path,
                        help="Defaults to the verification run directory")
    args = parser.parse_args()
    run = args.run_dir
    output = args.output_dir or run
    metadata = json.loads((run / "run_metadata.json").read_text())
    for name, digest in metadata["files_sha256"].items():
        if Path(name).name != name or sha256(run / name) != digest:
            raise ValueError("Verification file checksum differs: {}".format(name))
    provenance = json.loads((run / "metrics.csv.provenance.json").read_text())
    if provenance["device"] != "cuda:0" or provenance["partial_pilot"]:
        raise ValueError("Expected a complete CUDA run")
    if sha256(HERE / "model_config.json") != provenance["model_config_sha256"]:
        raise ValueError("Model architecture/vocabulary checksum differs")
    saved = read_csv(run / "metrics.csv")
    tissues = sorted(row["tissue"] for row in saved)
    if tissues != sorted(metadata["tissues"]) or len(set(tissues)) != len(tissues):
        raise ValueError("Unexpected deployment-check tissues")
    records = load_records(args.data_root, tissues)
    rescored, _ = score_rows(records, read_csv(run / "predictions.csv.gz"), "iDRO_tissue")
    fresh = {row["tissue"]: row for row in rescored}
    historical_path = HERE / "archived/metrics/cds_max_test_acc.csv"
    if sha256(historical_path) != metadata["historical_table_sha256"]:
        raise ValueError("Historical comparison table checksum differs")
    historical = {row["tissue"]: row for row in read_csv(historical_path)}
    assets = json.loads((REPOSITORY / "assets/manifest.json").read_text())
    assets = {row["path"]: row for row in assets["files"]}
    cpu_brain = read_csv(HERE / "verification/cds_checkpoint_Brain.csv")[0]
    # The separately computed CPU Kidney predictions test GPU/CPU agreement.
    gpu_predictions = {(r["tissue"], int(r["test_sequence"])): r
                       for r in read_csv(run / "predictions.csv.gz")}
    cpu_kidney_predictions = read_csv(run / "kidney_cpu_predictions.csv.gz")
    cpu_kidney_metrics, _ = score_rows(
        [r for r in records if r["tissue"] == "Kidney"], cpu_kidney_predictions, "iDRO_tissue")
    cpu_kidney = read_csv(run / "kidney_cpu.csv")[0]
    for key in ("correct_positions", "total_positions", "test_sequences"):
        if int(cpu_kidney[key]) != cpu_kidney_metrics[0][key] or int(cpu_kidney[key]) != fresh["Kidney"][key]:
            raise ValueError("Kidney CPU/GPU integer counts differ")
    for row in cpu_kidney_predictions:
        gpu = gpu_predictions[(row["tissue"], int(row["test_sequence"]))]
        if any(row[key] != gpu[key] for key in ("predicted_labels", "predicted_cds")):
            raise ValueError("Kidney CPU/GPU prediction strings differ")
    rows = []
    for row in saved:
        tissue = row["tissue"]
        calculated = fresh[tissue]
        for key in ("correct_positions", "total_positions", "test_sequences",
                    "coding_correct_codons", "coding_total_codons", "stop_correct_sequences"):
            if calculated[key] != int(row[key]):
                raise ValueError("Prediction counts differ: {} {}".format(tissue, key))
        if row["partial_pilot"].lower() != "false" or abs(calculated["test_acc"] - float(row["test_acc"])) > 1e-14:
            raise ValueError("Incomplete or inaccurate saved metrics: {}".format(tissue))
        if sha256(args.data_root / tissue / "test.txt") != provenance["test_files_sha256"][tissue]:
            raise ValueError("Test partition checksum differs: {}".format(tissue))
        relative_weight = "workspace/codon/cds_tissue_model/{}/lstmcrf.model".format(tissue)
        weight_hash = assets[relative_weight]["sha256"]
        source_hashes = [digest for source, digest in provenance["weight_files_sha256"].items()
                         if Path(source).parts[-2:] == (tissue, "lstmcrf.model")]
        if source_hashes != [weight_hash]:
            raise ValueError("Deployed weight checksum differs from asset manifest: {}".format(tissue))
        if args.model_root and sha256(args.model_root / tissue / "lstmcrf.model") != weight_hash:
            raise ValueError("Local/deployed weight checksum differs: {}".format(tissue))
        accuracy = calculated["test_acc"]
        archived = float(historical[tissue]["max_test_acc"])
        brain_equal = ""
        if tissue == "Brain":
            brain_equal = all(int(cpu_brain[k]) == calculated[k] for k in
                              ("correct_positions", "total_positions", "test_sequences"))
            if not brain_equal:
                raise ValueError("Brain GPU and CPU complete-test counts differ")
        rows.append({"tissue": tissue, "test_sequences": calculated["test_sequences"],
                     "correct_positions": calculated["correct_positions"],
                     "total_positions": calculated["total_positions"],
                     "gpu_test_acc": accuracy, "archived_max_test_acc": archived,
                     "gpu_acc_4dp": "{:.4f}".format(accuracy),
                     "archived_acc_4dp": "{:.4f}".format(archived),
                     "matches_at_4dp": "{:.4f}".format(accuracy) == "{:.4f}".format(archived),
                     "gpu_acc_3dp": "{:.3f}".format(accuracy),
                     "archived_acc_3dp": "{:.3f}".format(archived),
                     "matches_at_3dp": "{:.3f}".format(accuracy) == "{:.3f}".format(archived),
                     "cpu_gpu_integer_counts_identical": brain_equal if tissue == "Brain" else (True if tissue == "Kidney" else ""),
                     "weight_path": relative_weight, "weight_sha256": weight_hash})
    write_csv(output / "comparison.csv", rows)
    report = {"status": "passed",
              "tissues": tissues, "complete_test_sequences": len(records),
              "all_prediction_counts_recomputed": True,
              "all_recorded_weights_match_asset_manifest": True,
              "local_weights_verified": len(tissues) if args.model_root else 0,
              "matches_historical_table_at_3dp": sum(r["matches_at_3dp"] for r in rows),
              "matches_historical_table_at_4dp": sum(r["matches_at_4dp"] for r in rows),
              "all_match_historical_table_at_3dp": all(r["matches_at_3dp"] for r in rows),
              "all_match_historical_table_at_4dp": all(r["matches_at_4dp"] for r in rows),
              "brain_cpu_gpu_integer_counts_identical": next(
                  (r["cpu_gpu_integer_counts_identical"] for r in rows if r["tissue"] == "Brain"), None),
              "kidney_cpu_gpu_predictions_identical": True,
              "scope": "Six complete tissue tests; the remaining 23 tissues have not been remeasured here.",
              "interpretation": "Passed denotes integrity and score reproduction. It does not assert agreement with the historical maximum-test table."}
    output.mkdir(parents=True, exist_ok=True)
    (output / "audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if args.require_historical_match and not all(row["matches_at_" + args.require_historical_match] for row in rows):
        raise SystemExit("At least one deployed checkpoint differs at " + args.require_historical_match)



if __name__ == "__main__":
    main()
