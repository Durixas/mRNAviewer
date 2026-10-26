# 3′ UTR Bert2Bert deployment — 2026-10-26

## Model selection and files

`workspace/codon/utr_tissue_model/utr3/<tissue>/` matches the names used in
`cds_tissue_model/` and the 5′ UTR deployment. It contains 30 independent
bundles: 29 tissues and `general`, about 26.54 GiB of weights. Every tissue
has its own regular weight file, including the eight original-weight fallbacks.

The tissue choices come from the frozen validation selection for
`3utr_tissue_fullft_small_20261026`: 21 fine-tuned models and eight fallbacks
(Colon, Lymph_node, Rectum, Salivary_gland, Small_intestine, Smooth_muscle,
Stomach, Tonsil). No test results were used to change the choices.
`general` uses the original 3′ UTR Bert2Bert weights. Every bundle uses the
validated beam8, length penalty2, min_length0, max_length128 BPE configuration,
without the nucleotide bounds used for 5′ UTR.

Each bundle contains the complete weights, tokenizer, local architecture,
generation settings and selection metadata. `model_manifest.json` records
the source paths, validation selection hashes and copied weight SHA256 values.
Deployment needs neither the research directory nor Hugging Face caches.

## Request and batch routing

The backend passes `--tissue` to `main.py`. Existing workers that omit it are
supported through inference of the tissue from the CDS model path. A request
loads both its 5′ and 3′ UTR bundles through `UTR.get_single_sequence`.
`main_batch.py` and the file-based `get_full_sequence` also select both regions
by tissue. `general` uses general Bert2Bert for both regions.

The Web/CLI CDS decoder produces a coding ORF before `main.decorate` appends
TGA. The 3′ UTR generator is conditioned on that ORF plus TGA, matching the
CDS actually emitted. The raw JSON bridge takes its provided CDS unchanged;
the file-based full-sequence helper also uses its already supplied CDS.
The existing 5′ UTR generation and final GCCACC decoration are preserved.

New requests start a fresh `main.py`, so this routing takes effect without
restarting the backend or discarding its in-memory task results.

## Environment and GPU

The backend and CDS use `bart_old`; both UTR generators use the separate
`dna` environment. 3′ UTR uses `MRNAVIEWER_UTR3_PYTHON` when set, otherwise
the existing `MRNAVIEWER_UTR5_PYTHON` or a sibling conda environment named
`dna`. Install [requirements-utr3.txt](requirements-utr3.txt), which includes
the same pinned dependencies as 5′ UTR. No additional packages are required
in the existing DNA environment.

The local encoder and both beam decoders are shared in
`workspace/codon/utr5_runtime/`; the directory name is kept for compatibility.
Weights load strictly and all tokenizer/config reads are local.

GPU scheduling remains in `backend_server.py`: among GPUs not reserved by
this service, choose more free VRAM, then lower utilization, then GPU1 for
ties. GPUs used by other users remain eligible. Both UTR subprocesses inherit
the selected UUID via `CUDA_VISIBLE_DEVICES`. They run sequentially, use a
45% CUDA allocator limit, and default to four CPU threads.
`MRNAVIEWER_UTR3_THREADS` can override the 3′ UTR thread count, falling back
to `MRNAVIEWER_UTR5_THREADS`. Batch `--cpu` disables CUDA for both children.

## Reproduction and verification

Re-export from the research workspace:

```bash
CUDA_VISIBLE_DEVICES='' /path/to/dna/bin/python mRNAviewer_compare/export_3utr_tissue_models.py
```

Routing and bundle checks without GPU allocation:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /path/to/bart_old/bin/python -m unittest discover -s mRNAoptimizer_1212/tests -v
```

Compare representative deployed models with saved evaluation predictions:

```bash
CUDA_VISIBLE_DEVICES=GPU-<selected-uuid> OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 \
  /path/to/bart_old/bin/python mRNAviewer_compare/verify_3utr_web_models.py
```

Verification records, including the live service check, are stored in the
research workspace under
`mRNAviewer_compare/evaluation_results/UTR/utr3_web_deployment_20261026/`.

### Completed verification

- All nine routing/bundle regression checks passed without GPU allocation.
- All 30 weight files have matching parameter names and shapes, independent
  inodes and verified copied SHA256 values.
- Brain (fine-tuned), Colon (fallback), and general each generated two saved
  3′ UTR benchmark inputs. All six predictions exactly matched evaluation;
  both selected Brain examples differ from the general predictions.
- Two 5′ UTR Brain benchmark outputs also still matched evaluation exactly.
- Real requests to the existing service succeeded for Brain (`1188dbcc-26f`)
  and general (`96359006-79a`), without restarting the backend. Process
  observations confirmed the correct `utr3/<tissue>` model on physical GPU1,
  selected while GPU0 was occupied. Both returned all four RNAfold MFE values.
  Output lengths (full/5′/CDS/3′) were 483/151/189/143 nt for Brain and
  611/216/189/206 nt for general. GPU1 was released after verification.
