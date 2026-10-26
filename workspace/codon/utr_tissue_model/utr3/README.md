# 3′ UTR tissue models

30 independent bundles are stored here: `general` and the 29 tissues named
in `cds_tissue_model/`. Each includes full `model.safetensors`, `config.json`,
three tokenizer files, `generation_config.json` and `selection_metadata.json`.
Total weight size is about 26.54 GiB. `model_manifest.json` records source
weights, SHA256 values and the frozen validation selection.

21 tissue bundles use fine-tuned weights. Colon, Lymph_node, Rectum,
Salivary_gland, Small_intestine, Smooth_muscle, Stomach and Tonsil each have
their own copy of the original 3′ UTR Bert2Bert weights, as does `general`.
All use beam8, length penalty2 and a 128 BPE-token limit, with no nucleotide
length bounds. Choices were frozen before test evaluation.

The shared runtime is in `../../utr5_runtime/`. It loads the local DNABERT2
encoder and BERT decoder strictly without Hub access. Both UTR generators
use the `dna` environment; CDS/backend stay in `bart_old`.

See [the deployment guide](../../../../UTR3_DEPLOYMENT.md) for environment
variables, GPU scheduling, request routing, export and verification commands.
