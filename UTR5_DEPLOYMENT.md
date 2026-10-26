# 5′ UTR Bert2Bert deployment — 2026-10-26

## Models

`workspace/codon/utr_tissue_model/utr5/<tissue>/` follows the tissue directory
names in `cds_tissue_model`. There are30 independent bundles:29 tissues and
`general`, using about26.54 GiB for weights. No weight symlinks or hardlinks
are used, including the four original-weight fallbacks.

The29 tissue choices exactly follow the frozen validation selection in
`5utr_tissue_fullft_paired_20261026`:25 fine-tuned models and four original
Bert2Bert fallbacks (Adrenal_gland, Endometrium, Heart, Tonsil). Each directory
also stores its own tokenizer, architecture, generation settings and source
metadata. `model_manifest.json` stores source SHA256 values.

`general` also uses the original Bert2Bert, with the prior validation-first
short decoding configuration:beam8, length penalty2,120–210 nt,128 BPE tokens.
The old5′ BART is no longer selected for general requests. 3′ UTR has since
also moved to tissue/general Bert2Bert; see [its deployment guide](UTR3_DEPLOYMENT.md).

## Request path and GPU

`backend_server.py` selects a GPU using the existing scheduler (more free
memory first, lower utilization next, GPU1 for ties), reserves it for the
model phase and passes its UUID through `CUDA_VISIBLE_DEVICES` to `main.py`.
The5′ UTR subprocess inherits that same GPU. It uses the `dna` interpreter;
CDS keeps `bart_old`; 3′ UTR also uses `dna`. See `requirements-utr5.txt`
and the model README.

The backend now explicitly passes `--tissue`. For an existing backend worker
that has not reloaded, `main.py` also infers the tissue from the CDS model path
in decode.config. Because each request starts a fresh main.py process, new
requests use this routing without restarting the server or dropping its
in-memory task results. Both CLI and batch generation support explicit tissue.

The existing final Kozak/stop-codon decoration is retained. The final web5′ UTR
can therefore be up to six nt longer than the raw evaluated model prediction.

## Verification completed

- Six CPU routing regression tests passed:all30 bundles, fallback copies,
  general/tissue routing, backend argument propagation, batch generation,
  GPU UUID inheritance and explicit CPU mode.
- Brain, general and Tonsil each generated two benchmark CDS inputs through
  the deployed environment bridge. All six outputs exactly matched the
  saved evaluation sequences.
- During the initial 5′ deployment, real CPU end-to-end CDS→Bert2Bert5′ UTR→BART3′ UTR succeeded for general
  and Brain; Brain deliberately omitted `--tissue` to verify old-worker support.
- A real request to the running web service (`bf2f1aaf-f55`, Brain) finished
  successfully on the initially idle physical GPU1. nvidia-smi recorded both
  bart_old and dna processes on its UUID; GPU0 was occupied by another user.
  The output lengths were full671 nt /5′ UTR151 nt /CDS189 nt /3′ UTR331 nt,
  and all four RNAfold MFE values were returned.

Research-workspace verification records:
`mRNAviewer_compare/evaluation_results/UTR/utr5_web_deployment_20261026/`.

Run routing tests without allocating a GPU:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 \
  /path/to/bart_old/bin/python -m unittest discover -s mRNAoptimizer_1212/tests -v
```
