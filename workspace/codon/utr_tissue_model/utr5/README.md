# 5′ UTR Bert2Bert models

This directory contains 30 independent model bundles: `general` and 29 tissues,
matching the names in `cds_tissue_model/`. All weights are regular copied files;
the four tissue fallbacks and `general` have separate copies of the original
Bert2Bert weights. Total weight size is about 26.54 GiB.

Each bundle contains:

- `model.safetensors`: complete encoder, decoder and LM-head weights.
- `config.json`: local encoder/decoder architecture and special token IDs.
- `tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`.
- `generation_config.json`: the exact validation-selected beam and nt bounds.
- `selection_metadata.json`: source, selected epoch, strategy and SHA256.

`model_manifest.json` records all bundles. Tissue choices come from the frozen
`5utr_tissue_fullft_paired_20261026` validation selection: 25 fine-tuned, four
original-weight fallbacks (Adrenal_gland, Endometrium, Heart, Tonsil).
`general` uses the original Bert2Bert weights and the prior validation-first
short decoding configuration `b8_lp2_nt120_210`: beam8, length penalty2,
120–210 nt, at most128 BPE tokens. No test-based model reselection was performed.

The shared runtime lives in `../../utr5_runtime/`. It includes the same
no-Flash DNABERT2 encoder, real HF beam search and nucleotide-bound decoder
used during evaluation. Runtime loading is local and strict; it needs neither
`mRNAviewer_compare`, training model directories nor Hugging Face caches.

The legacy server/CDS environment remains `bart_old`. Subprocesses load
both UTR regions using the separate `dna` environment. Configure
`MRNAVIEWER_UTR5_PYTHON=/path/to/dna/bin/python`; by default a sibling conda
environment named `dna` is detected. Dependency pins are in the web project's
`requirements-utr5.txt`. The child inherits the GPU reserved by the backend,
limits its own GPU allocator to45% and uses four CPU threads by default
(`MRNAVIEWER_UTR5_THREADS` can override). CPU execution is supported.

`backend_server.py` passes `--tissue` to `main.py`; older callers can omit it,
in which case the tissue is inferred from the CDS model path in decode.config.
Both `general` and tissue requests use Bert2Bert for both UTR regions; see
the [3′ UTR models](../utr3/README.md) for its separate bundles and settings.
The existing final `GCCACC`/stop-codon decoration remains in `main.decorate`,
so final web output lengths can be up to six nt longer than raw evaluated UTRs.

Re-export from the research workspace:

```bash
CUDA_VISIBLE_DEVICES='' /path/to/dna/bin/python mRNAviewer_compare/export_5utr_tissue_models.py
```

Routing tests (no GPU or real inference):

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=4 /path/to/bart_old/bin/python -m unittest discover -s mRNAoptimizer_1212/tests -v
```
