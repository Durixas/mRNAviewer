#!/usr/bin/env python3
"""Decode the frozen tissue-selected BERT2BERT generators on UTR test inputs.

Uses the same repository runtime, weights and generation_config.json as the
web server. No reference lengths or test scores are used to choose settings.
"""
import argparse
import csv
import gc
import json
from pathlib import Path
import sys

from evaluate import dna, open_text, sha256

ROOT = Path(__file__).resolve().parents[2]


def read_records(data_root, region, tissues):
    c_file, u_file = ("eval_c5.txt", "eval_5u.txt") if region == "5utr" else ("eval_c3.txt", "eval_3u.txt")
    result = []
    for tissue in tissues:
        sources = (data_root/tissue/c_file).read_text().splitlines()
        targets = (data_root/tissue/u_file).read_text().splitlines()
        if not sources or len(sources) != len(targets):
            raise ValueError("Unpaired or empty test files for {}".format(tissue))
        for index, (source, target) in enumerate(zip(sources, targets), 1):
            result.append({"region": region, "model": "bert2bert_best", "tissue": tissue,
                           "test_sequence": str(index), "input_cds": dna(source),
                           "reference_utr": dna(target)})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True, choices=("5utr", "3utr"))
    parser.add_argument("--data-root", type=Path, default=ROOT/"data/extracted/utr_tissue_data")
    parser.add_argument("--model-root", type=Path, default=ROOT/"workspace/codon/utr_tissue_model",
                        help="Common utr_tissue_model root, or region-specific utr5/utr3 root")
    parser.add_argument("--device", default="cpu", help="cpu, cuda, or cuda:N; default cpu")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--tissues", nargs="+", help="Default: all 29 tissues in the frozen manifest")
    parser.add_argument("--output", type=Path, required=True, help="CSV or CSV.gz output; partial file supports resume")
    parser.add_argument("--verify-weights", action="store_true", help="Hash restored model weights before loading")
    args = parser.parse_args()
    if args.batch_size < 1 or args.threads < 1:
        parser.error("batch-size and threads must be positive")
    frozen = json.loads((Path(__file__).parent/"frozen_model_selection.json").read_text())[args.region]
    tissues = args.tissues or list(frozen["tissues"])
    if len(tissues) != len(set(tissues)) or any(t not in frozen["tissues"] for t in tissues):
        parser.error("Tissues must be unique entries in the frozen 29-tissue model manifest")
    region_dir = "utr5" if args.region == "5utr" else "utr3"
    model_root = args.model_root/region_dir if (args.model_root/region_dir).is_dir() else args.model_root
    records = read_records(args.data_root, args.region, tissues)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Plain-text append-only working file is intentionally separate from final gzip.
    partial = args.output.with_name(args.output.name+".partial.csv")
    identity = lambda r: (r["region"], r["tissue"], r["test_sequence"])
    existing = {}
    if partial.exists():
        with partial.open(newline="", encoding="utf-8") as source:
            existing = {identity(row): row for row in csv.DictReader(source)}
    for row in records:
        previous = existing.get(identity(row))
        if previous and any(previous[k] != row[k] for k in row):
            raise ValueError("Resume inputs differ from existing partial predictions")
    sys.path.insert(0, str(ROOT/"workspace/codon"))
    import torch
    from utr5_runtime.model import load_decoder
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32 = False
    if args.device.startswith("cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("Requested CUDA device is unavailable; use --device cpu")
        torch.cuda.set_device(torch.device(args.device))
        torch.cuda.set_per_process_memory_fraction(0.45, torch.cuda.current_device())
    fields = list(records[0])+["predicted_utr"]
    with partial.open("a", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        if target.tell() == 0:
            writer.writeheader()
        for tissue in tissues:
            pending = [r for r in records if r["tissue"] == tissue and identity(r) not in existing]
            if not pending:
                continue
            directory, selected = model_root/tissue, frozen["tissues"][tissue]
            generation = json.loads((directory/"generation_config.json").read_text())
            if generation != selected["generation_config"]:
                raise ValueError("Generation configuration differs from frozen selection: "+tissue)
            weights = directory/"model.safetensors"
            if weights.stat().st_size != selected["weights_bytes"]:
                raise ValueError("Restored model has incorrect size: "+tissue)
            if args.verify_weights and sha256(weights) != selected["weights_sha256"]:
                raise ValueError("Restored model has incorrect hash: "+tissue)
            print("Decoding {} {}: {} remaining records".format(args.region, tissue, len(pending)), file=sys.stderr, flush=True)
            decoder, generation = load_decoder(directory, args.device)
            for start in range(0, len(pending), args.batch_size):
                batch = pending[start:start+args.batch_size]
                predictions = decoder([r["input_cds"] for r in batch], generation)
                if len(predictions) != len(batch):
                    raise ValueError("Decoder returned incorrect number of predictions")
                for row, prediction in zip(batch, predictions):
                    result = dict(row, predicted_utr=dna(prediction, allow_empty=True))
                    writer.writerow(result)
                    existing[identity(row)] = result
                target.flush()
            del decoder
            gc.collect()
            if args.device.startswith("cuda"):
                torch.cuda.empty_cache()
    with open_text(args.output, "wt") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(existing[identity(row)] for row in records)
    print("Saved {} predictions to {}".format(len(records), args.output))


if __name__ == "__main__":
    main()
