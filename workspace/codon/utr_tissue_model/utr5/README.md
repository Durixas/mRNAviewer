# 5′ UTR BERT2BERT model bundles

This directory provides independent context bundles for General and the
29 human tissues. Tissue names match `cds_tissue_model/`. Bundle configurations
and decoding choices follow the frozen validation selection.

Each complete runtime bundle contains:

- `model.safetensors`: encoder, decoder and language-model head weights.
- `config.json`: local architecture and special-token settings.
- `tokenizer.json`, `tokenizer_config.json`, `special_tokens_map.json`.
- `generation_config.json`: the validated decoding configuration.
- `selection_metadata.json`: checkpoint source and selection provenance.

`model_manifest.json` records source identifiers, copied weight hashes and
validation-selection metadata. Weights are external assets, approximately
26.54 GiB for this region; restore them using the
[installation guide](../../../../docs/INSTALLATION.md).

Generation uses the frozen per-tissue beam settings and nucleotide-length
bounds recorded in each `generation_config.json`. General uses beam search
with 8 beams, length penalty 2, a 128 BPE-token limit, and 120–210 nt bounds.

The shared local runtime is in `../../utr5_runtime/` for both regions.
The backend and CDS use the backend environment; UTR subprocesses use the
DNA environment with pinned dependencies in `requirements-utr5.txt` at the
repository root. They inherit the backend-selected device and support CPU
execution.

See the [deployment guide](../../../../UTR5_DEPLOYMENT.md) for routing
and device settings and the [UTR evaluation guide](../../../../evaluation/utr/README.md)
for frozen prediction decoding and ROUGE/BLEU scoring. The benchmark evaluates
raw UTR predictions; the web server adds GCCACC during final assembly.
