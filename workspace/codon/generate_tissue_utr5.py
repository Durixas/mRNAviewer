#!/usr/bin/env python3
"""JSON stdin/stdout bridge, executed in the DNABERT2 environment."""
import argparse
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("batch-size must be positive")
    payload = json.load(sys.stdin)
    sources = payload["sequences"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("Expected a nonempty CDS list")
    sources = ["".join(seq.split()).upper() for seq in sources]
    if any(not seq or set(seq)-set("ACGT") for seq in sources):
        raise ValueError("CDS input must contain DNA nucleotides A/C/G/T")
    # Runtime diagnostics must not contaminate the JSON protocol.
    with redirect_stdout(sys.stderr):
        import torch
        from utr5_runtime.model import load_decoder
        torch.set_num_threads(int(os.environ.get("MRNAVIEWER_UTR5_THREADS", "4")))
        torch.set_num_interop_threads(1)
        torch.backends.cuda.matmul.allow_tf32 = False
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if device == "cuda":
            torch.cuda.set_per_process_memory_fraction(0.45, 0)
        decoder, config = load_decoder(args.model_dir, device)
        predictions = []
        for start in range(0, len(sources), args.batch_size):
            predictions.extend(decoder(sources[start:start+args.batch_size], config))
    json.dump({"predictions": predictions}, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
