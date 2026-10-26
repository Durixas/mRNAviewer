"""Select a tissue bundle and bridge the legacy BART environment to DNABERT2."""
import json
import os
from pathlib import Path
import subprocess
import sys

CODON_DIR = Path(__file__).resolve().parent
MODEL_ROOT = CODON_DIR / "utr_tissue_model/utr5"


def normalize_tissue(tissue):
    if tissue is None or tissue in ("general", "0"):
        return "general"
    if not isinstance(tissue, str) or Path(tissue).name != tissue or tissue in (".", ".."):
        raise ValueError("Invalid tissue name")
    return tissue


def tissue_from_cds_model(model_path):
    """Also support callers using an older backend without --tissue."""
    parent = Path(model_path).parent
    return normalize_tissue(parent.name) if parent.parent.name == "cds_tissue_model" else "general"


def resolve_tissue_model(tissue):
    tissue = normalize_tissue(tissue)
    directory = MODEL_ROOT / tissue
    required = ("model.safetensors", "config.json", "generation_config.json", "tokenizer.json")
    if directory.is_symlink() or not all((directory / name).is_file() for name in required):
        raise FileNotFoundError("Missing 5′ UTR model bundle for tissue: "+tissue)
    return directory


def inference_python():
    configured = os.environ.get("MRNAVIEWER_UTR5_PYTHON")
    if configured:
        return configured
    # Existing deployment: bart_old and dna are sibling conda environments.
    sibling = Path(sys.prefix).parent / "dna/bin/python"
    return str(sibling) if sibling.is_file() else sys.executable


def generate_tissue_utr5(sequences, tissue, batch_size=8, use_gpu=True):
    directory = resolve_tissue_model(tissue)
    if not sequences:
        return []
    environment = os.environ.copy()
    if not use_gpu:
        environment["CUDA_VISIBLE_DEVICES"] = ""
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    threads = environment.get("MRNAVIEWER_UTR5_THREADS", "4")
    environment.update(OMP_NUM_THREADS=threads, MKL_NUM_THREADS=threads, OPENBLAS_NUM_THREADS="1")
    result = subprocess.run(
        [inference_python(), str(CODON_DIR / "generate_tissue_utr5.py"),
         "--model-dir", str(directory), "--batch-size", str(batch_size)],
        input=json.dumps({"sequences": sequences}), text=True, capture_output=True,
        env=environment, cwd=str(CODON_DIR), timeout=600, check=False)
    if result.returncode:
        raise RuntimeError("Tissue 5′ UTR inference failed (requires the dna environment; "
                           "configure MRNAVIEWER_UTR5_PYTHON): "+result.stderr[-3000:])
    predictions = json.loads(result.stdout)["predictions"]
    if len(predictions) != len(sequences):
        raise ValueError("Tissue generator returned an unexpected sequence count")
    bounds = json.loads((directory / "generation_config.json").read_text())
    for prediction in predictions:
        if not prediction or set(prediction)-set("ACGT") or not bounds["min_nt"] <= len(prediction) <= bounds["max_nt"]:
            raise ValueError("Tissue generator returned an invalid/bounds-violating DNA sequence")
    return predictions
