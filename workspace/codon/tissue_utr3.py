"""Select a 3-prime tissue bundle and run it in the DNABERT2 environment."""
import json
import os
from pathlib import Path
import subprocess

from tissue_utr5 import inference_python as utr5_python, normalize_tissue

CODON_DIR = Path(__file__).resolve().parent
MODEL_ROOT = CODON_DIR / "utr_tissue_model/utr3"


def resolve_tissue_model(tissue):
    tissue = normalize_tissue(tissue)
    directory = MODEL_ROOT / tissue
    required = ("model.safetensors", "config.json", "generation_config.json", "tokenizer.json")
    if directory.is_symlink() or not all((directory / name).is_file() for name in required):
        raise FileNotFoundError("Missing 3′ UTR model bundle for tissue: "+tissue)
    return directory


def inference_python():
    return os.environ.get("MRNAVIEWER_UTR3_PYTHON") or utr5_python()


def generate_tissue_utr3(sequences, tissue, batch_size=8, use_gpu=True):
    directory = resolve_tissue_model(tissue)
    if not sequences:
        return []
    environment = os.environ.copy()
    if not use_gpu:
        environment["CUDA_VISIBLE_DEVICES"] = ""
    environment.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", TOKENIZERS_PARALLELISM="false")
    threads = environment.get("MRNAVIEWER_UTR3_THREADS", environment.get("MRNAVIEWER_UTR5_THREADS", "4"))
    environment.update(OMP_NUM_THREADS=threads, MKL_NUM_THREADS=threads, OPENBLAS_NUM_THREADS="1")
    result = subprocess.run(
        [inference_python(), str(CODON_DIR / "generate_tissue_utr3.py"),
         "--model-dir", str(directory), "--batch-size", str(batch_size)],
        input=json.dumps({"sequences": sequences}), text=True, capture_output=True,
        env=environment, cwd=str(CODON_DIR), timeout=600, check=False)
    if result.returncode:
        raise RuntimeError("Tissue 3′ UTR inference failed (requires the dna environment; "
                           "configure MRNAVIEWER_UTR3_PYTHON): "+result.stderr[-3000:])
    predictions = json.loads(result.stdout)["predictions"]
    if len(predictions) != len(sequences):
        raise ValueError("Tissue 3′ UTR generator returned an unexpected sequence count")
    if any(not isinstance(p, str) or not p or set(p)-set("ACGT") for p in predictions):
        raise ValueError("Tissue 3′ UTR generator returned invalid DNA")
    return predictions
