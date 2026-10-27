#!/usr/bin/env python3
"""Evaluate restored iDRO general/tissue BiLSTM-CRF weights on released test.txt.

Defaults to CPU. For a chosen GPU, set CUDA_VISIBLE_DEVICES before starting and
pass --device cuda:0. This script never overrides GPU visibility or schedules jobs.
"""
import argparse
import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from metrics import CODONS, DEFAULT_DATA, REPOSITORY, load_records, score_rows, sha256, write_csv


class FrozenAlphabet:
    def __init__(self, instances):
        self.instances = instances
        self.instance2index = {word: i for i, word in enumerate(instances, 1)}

    def size(self):
        return len(self.instances) + 1

    def get_index(self, value):
        if value not in self.instance2index:
            raise ValueError("Unknown input symbol: {}".format(value))
        return self.instance2index[value]


def model_settings(config_path, batch_size, gpu=False):
    values = json.loads(config_path.read_text())
    words, labels = values.pop("word_instances"), values.pop("label_instances")
    values.pop("description", None)
    values.update(HP_gpu=gpu, HP_batch_size=batch_size,
                  pretrain_word_embedding=None, pretrain_feature_embeddings=[],
                  word_alphabet=FrozenAlphabet(words), label_alphabet=FrozenAlphabet(labels))
    return SimpleNamespace(**values)


def configure_device(torch_module, requested):
    device = torch_module.device(requested)
    if device.type not in ("cpu", "cuda"):
        raise ValueError("Only cpu and cuda devices are supported by the legacy CRF")
    if device.type == "cuda":
        if not torch_module.cuda.is_available():
            raise ValueError("CUDA requested but unavailable")
        # Legacy CRF internals call .cuda() without a device argument.
        torch_module.cuda.set_device(device.index if device.index is not None else 0)
    return device


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context", choices=("general", "tissue"), required=True)
    parser.add_argument("--checkpoint", help="Override path; use {tissue} in a tissue checkpoint template")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("model_config.json"))
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--tissues", nargs="+")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--max-sequences-per-tissue", type=int,
                        help="Pilot only; output is explicitly marked incomplete")
    args = parser.parse_args()
    if args.batch_size < 1 or args.threads < 1 or (args.max_sequences_per_tissue is not None and args.max_sequences_per_tissue < 1):
        parser.error("batch-size, threads and pilot limit must be positive")
    import torch
    torch.set_num_threads(args.threads)
    torch.manual_seed(42)
    torch.backends.cudnn.enabled = False  # Match historical CDS evaluation.
    try:
        device = configure_device(torch, args.device)
    except ValueError as error:
        parser.error(str(error))
    sys.path.insert(0, str(REPOSITORY / "workspace/codon"))
    from model.seqmodel import SeqModel

    records = load_records(args.data_root, args.tissues)
    tissues = sorted({record["tissue"] for record in records})
    predictions, output_metrics, weight_hashes = [], [], {}
    model, active_checkpoint = None, None
    for tissue in tissues:
        template = args.checkpoint or str(REPOSITORY / "workspace/codon" /
                    ("lstmcrf.113.model" if args.context == "general" else "cds_tissue_model/{tissue}/lstmcrf.model"))
        checkpoint = Path(template.format(tissue=tissue))
        if not checkpoint.is_file():
            raise FileNotFoundError("Restore model assets first: {}".format(checkpoint))
        if active_checkpoint != checkpoint:
            # SeqModel increments label_alphabet_size during construction; always use a fresh config.
            settings = model_settings(args.config, args.batch_size, gpu=device.type == "cuda")
            model = SeqModel(settings)
            model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True), strict=True)
            model.to(device).eval()
            active_checkpoint = checkpoint
            weight_hashes[str(checkpoint)] = sha256(checkpoint)
        subset = [record for record in records if record["tissue"] == tissue]
        if args.max_sequences_per_tissue:
            subset = subset[:args.max_sequences_per_tissue]
        tissue_predictions = []
        with torch.inference_mode():
            for start in range(0, len(subset), args.batch_size):
                batch = sorted(subset[start:start + args.batch_size], key=lambda r: len(r["protein"]), reverse=True)
                lengths = torch.tensor([len(r["protein"]) + 1 for r in batch], dtype=torch.long, device=device)
                words = torch.zeros((len(batch), int(lengths[0])), dtype=torch.long, device=device)
                mask = torch.zeros_like(words, dtype=torch.uint8)
                for i, record in enumerate(batch):
                    sequence = record["protein"] + "X"
                    words[i, :len(sequence)] = torch.tensor([settings.word_alphabet.get_index(aa) for aa in sequence], device=device)
                    mask[i, :len(sequence)] = 1
                tags = model(words, [], lengths, mask).cpu().tolist()
                for i, record in enumerate(batch):
                    ids = tags[i][:len(record["protein"]) + 1]
                    label_names = settings.label_alphabet.instances
                    labels = "".join(label_names[index - 1] if 1 <= index <= len(label_names) else "?" for index in ids)
                    # NNN preserves positions if a CRF tag cannot map to a synonymous codon.
                    cds = "".join(CODONS[aa].get(label, "NNN") for aa, label in zip(record["protein"] + "X", labels))
                    tissue_predictions.append({"tissue": tissue, "test_sequence": record["test_sequence"],
                                               "protein": record["protein"], "reference_cds": record["reference_cds"],
                                               "predicted_labels": labels, "predicted_cds": cds})
        metrics, scored = score_rows(subset, tissue_predictions, "iDRO_" + args.context)
        metrics[0]["checkpoint"] = str(checkpoint)
        metrics[0]["partial_pilot"] = bool(args.max_sequences_per_tissue)
        output_metrics.extend(metrics)
        predictions.extend(scored)
        print("{}: {}/{} = {:.8f}".format(tissue, metrics[0]["correct_positions"], metrics[0]["total_positions"], metrics[0]["test_acc"]), flush=True)
    predictions.sort(key=lambda row: (row["tissue"], row["test_sequence"]))
    write_csv(args.output, output_metrics)
    write_csv(args.predictions, predictions)
    provenance = {"context": args.context, "device": str(device), "torch": torch.__version__,
                  "model_config_sha256": sha256(args.config), "weight_files_sha256": weight_hashes,
                  "partial_pilot": bool(args.max_sequences_per_tissue),
                  "test_files_sha256": {t: sha256(args.data_root / t / "test.txt") for t in tissues},
                  "macro_test_acc": sum(row["test_acc"] for row in output_metrics) / len(output_metrics),
                  "note": "Current checkpoint evaluation; not the historical maximum over test epochs."}
    args.output.with_suffix(args.output.suffix + ".provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


if __name__ == "__main__":
    main()
