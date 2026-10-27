# 3′ UTR BERT2BERT deployment

## Context bundles

`workspace/codon/utr_tissue_model/utr3/<context>/` holds 30 independent
bundles: the 29 human tissues and `general`. Model directories match the CDS
context names. Each bundle carries its tokenizer, architecture, generation
configuration and selection provenance. `model_manifest.json` records copied
weight SHA-256 values and the frozen validation selection.

The repository versions configurations and tokenizers. Weight restoration is
described in [installation and operation](docs/INSTALLATION.md); the region's
weights occupy approximately 26.54 GiB. Runtime reads local files and loads
weights strictly.

Generation uses 8 beams, length penalty 2, and a 128 BPE-token limit.
There are no explicit nucleotide-length bounds for this region.

## Request and batch routing

`backend_server.py` passes `--tissue` to `workspace/codon/main.py`. The selected
context determines both UTR bundles, and `general` uses the General BERT2BERT
bundle for each region. Callers that omit `--tissue` can use the tissue name
encoded in the CDS model path. `main_batch.py` and the file-based
`UTR.get_full_sequence` helper also route both regions by context.

Each request starts a new inference process. The web application assembles
GCCACC before the start codon and tandem TAA/TGA stops at the coding-region
end. The 3′ UTR generator receives the coding segment including the appended
TGA, while benchmark decoding receives the supplied test CDS unchanged.
Raw benchmark UTRs are scored before assembly.

## Environment and GPU

The backend/CDS and DNA environments have separate dependency pins in
`requirements-backend.txt` and `requirements-utr5.txt`. Both UTR regions use
the DNA environment; `requirements-utr3.txt` includes the same pins.
Set `MRNAVIEWER_UTR5_PYTHON` to its Python executable;
`MRNAVIEWER_UTR3_PYTHON` can override the interpreter for 3′ UTR.

The backend selects among physical GPUs 0 and 1 that are not reserved by
this service, using more free VRAM, then lower utilization, then GPU1 for
ties. Devices running other users' tasks remain eligible. Inference children
inherit the reserved UUID via `CUDA_VISIBLE_DEVICES`. UTR children run
sequentially with a 45% CUDA allocator limit and four CPU threads by default.
`MRNAVIEWER_UTR3_THREADS` overrides this region's thread count.
Batch `--cpu` disables CUDA for both UTR children.

## Evaluation and verification

The [portable UTR decoder](evaluation/utr/README.md#generate-new-bert2bert-predictions)
uses these same local runtime modules and frozen configurations. Archived
predictions and ROUGE/BLEU code are included under `evaluation/utr/`.
`evaluation/utr/decoder_smoke_verification.json` records a CPU decoding check
against an archived Brain prediction for each region.

With model assets restored, run the routing checks from the repository root:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /path/to/backend/bin/python -m unittest discover -s tests -v
```

These checks validate context selection, independent model bundles, backend
arguments, batch routing and GPU/CPU device propagation.
