# ORF/CDS evaluation: manuscript Fig. 1C

These scripts evaluate the 29 released tissue test partitions and reproduce the
archived ORF comparison in the mRNAviewer Application Note. Run commands below
from the repository root. Paths are resolved from this repository; the original
research workspace is not required.

## 1. Extract the test partitions

```bash
python data/extract.py --archive cds_tissue_data.tar.gz --archive cds_sequence_pairs.tar.gz
```

The default test input is `data/extracted/cds_tissue_data/<tissue>/test.txt`:
one amino acid and one codon-box label per line, with blank lines separating
sequences. A final `X w` is a dummy amino acid representing the stop codon.
There are **5,682 test sequences in 29 tissues**. Training and validation splits
are released alongside these test files. The matching
`data/extracted/cds_sequence_pairs/<tissue>/test.csv` preserves the original DNA,
including the specific terminal stop, and has a one-based `sequence_id` matching
the TXT block order. See [the dataset documentation](../../data/README.md).

## 2. Reproduce the reported Fig. 1C comparison without model inference

Python 3.8 or newer is sufficient; no third-party packages or GPU are needed.

```bash
python evaluation/cds/verify_release.py
python evaluation/cds/summarize_archived.py
```

The first command verifies the checksums of all archived files, then recomputes
all per-tissue integer counts and accuracies from the released predictions for
GEMORNA, CodonTransformer and mRNASyner. An additional native mRNASyner result is
included as a diagnostic. The second command writes:

- `evaluation/cds/results/fig1c_per_tissue.csv`: the 29-tissue table, in fractions.
- `evaluation/cds/results/fig1c_macro_accuracy.csv`: equally weighted tissue means.
- `evaluation/cds/results/checkpoint_selection_audit.csv`: the historical training
  log selection comparison (maximum test versus last validation-selected epoch).

The archived means reproduce the manuscript's two-decimal percentages:

| Method | Mean codon accuracy (%) |
| --- | ---: |
| mRNAviewer, archived maximum test score | 53.79862069 |
| General iDRO | 53.37150345 |
| mRNASyner, synonymous codon constraint | 52.92028621 |
| CodonTransformer | 50.50460690 |
| GEMORNA | 44.47750000 |

### Historical scores and current model inference

The mRNAviewer Fig. 1C values originate from `cds_max_test_acc.csv`: the largest
**test** accuracy printed during the 10 training epochs, recorded to four decimal
places. They are not a new evaluation of the currently restored model weights.
Training saved a checkpoint when validation accuracy improved. The maximum-test
score differs from the last validation-selected epoch's logged test score in
**26 of 29 tissues**. This is a comparison of two choices within the historical
training logs; it does **not** establish which epoch was subsequently renamed
and deployed as `lstmcrf.model`. The audit table preserves both logged values and
their epochs. A single evaluation of a restored tissue checkpoint must therefore
be measured, rather than inferred from this log comparison. For example, a CPU
check of the current Brain checkpoint gave `43537/80211 = 0.5427809153`, which
rounds to its archived maximum `0.5428`; its last validation-selected epoch had
a logged test score of `0.5418`. This check is recorded in `verification/`.
The unrounded per-epoch test scores are not recoverable from the four-decimal log
alone.

Use the inference workflow below to report current-checkpoint performance
separately. No script selects a new checkpoint using the released test set.

The original training logs specify `optim.Adam`, learning rate `3e-4`, 10 epochs,
batch size 32, full-parameter updates and `weight_decay=1e-8`. This differs from
the manuscript draft's optimizer name “AdamW”; the archived logs are preserved
for provenance.

### Complete-test GPU follow-up on six deployed models

A subsequent single-GPU run tested Adrenal gland, Brain, Kidney, Lung,
Placenta and Tonsil: **1,224 complete-test sequences**. Four tissues match
historical maxima at four decimal places, and five match at three decimals.
Kidney is 0.5570335 versus historical 0.5579, with identical complete CPU/GPU
predictions. Tonsil is 0.5470560 versus historical 0.5472; both round to 0.547.
Brain's GPU counts exactly match its complete CPU test.

The [full GPU verification record](verification/gpu_deployed_20261026/README.md)
contains every prediction, exact count, weight/test hash and comparison.
Recompute it without weights or a GPU:

```bash
python evaluation/cds/audit_deployed.py
```

This audit separates measurement integrity from historical-score agreement.
It neither replaces the archived figure column nor establishes agreement
for the remaining 23 tissues. Model weights remain separate assets.

## 3. Re-score any saved CDS predictions

Example using the archived GEMORNA output:

```bash
python evaluation/cds/score_predictions.py \
  --predictions evaluation/cds/archived/predictions/gemorna_cds_predictions.csv.gz \
  --model GEMORNA \
  --output evaluation/cds/results/gemorna_recomputed.csv
```

CSV and gzip-compressed CSV are supported. Required columns are `tissue`,
`test_sequence` (the one-based TXT block index) and `predicted_cds`. Optional
`protein` and `reference_cds` columns are verified against the released test set.
`predicted_labels` may be supplied by the BiLSTM-CRF evaluator; when present,
label accuracy is scored directly. Unknown labels remain incorrect.

All requested test records must have exactly one prediction. To audit a small
pilot explicitly, pass `--tissues Brain` and, if needed, `--allow-subset`.
Incomplete outputs must not be used as full tissue benchmark scores.

Each scoring run writes a `.provenance.json` with prediction and test file
checksums, sample count and macro accuracy. The original paths retained inside
the archived metric CSVs are historical metadata, not script dependencies.

## 4. Evaluate the restored general or tissue BiLSTM-CRF checkpoints

Restore runtime model assets according to [the main README](../../README.md).
The compact `model_config.json` contains the frozen vocabulary and architecture
settings needed for inference, so this evaluator does not need to load the large
legacy `.dset` pickle. No model weights are bundled in this evaluation directory.

Install `evaluation/cds/requirements.txt`, or use the documented backend/CDS
environment. A CPU run is the default:

```bash
python evaluation/cds/evaluate_checkpoint.py \
  --context general --device cpu --threads 4 \
  --output evaluation/cds/results/general_checkpoint.csv \
  --predictions evaluation/cds/results/general_checkpoint_predictions.csv.gz

python evaluation/cds/evaluate_checkpoint.py \
  --context tissue --device cpu --threads 4 \
  --output evaluation/cds/results/tissue_checkpoints.csv \
  --predictions evaluation/cds/results/tissue_checkpoint_predictions.csv.gz
```

Default checkpoint paths are:

- General: `workspace/codon/lstmcrf.113.model`.
- Tissue: `workspace/codon/cds_tissue_model/<tissue>/lstmcrf.model`.

Override with `--checkpoint /path/to/general.model` or a quoted template such as
`--checkpoint '/path/to/models/{tissue}/lstmcrf.model'`. CPU and CUDA use the same
checkpoint and test parser. A selected GPU can be used explicitly:

```bash
CUDA_VISIBLE_DEVICES=1 python evaluation/cds/evaluate_checkpoint.py \
  --context tissue --device cuda:0 --batch-size 1 \
  --output evaluation/cds/results/tissue_checkpoints_gpu.csv \
  --predictions evaluation/cds/results/tissue_checkpoint_gpu_predictions.csv.gz
```

`cuda:0` refers to the first *visible* GPU. This standalone script does not choose
or reserve a GPU; select a suitable device on a shared machine. CPU is used unless
`--device` is supplied. `--tissues Brain Lung` limits the run. The explicit
`--max-sequences-per-tissue 2` option is for a pilot and marks outputs incomplete.

Compare fresh checkpoint scores with the archived results without replacing them:

```bash
python evaluation/cds/summarize_archived.py \
  --checkpoint-metrics evaluation/cds/results/tissue_checkpoints.csv
```

## Accuracy definition and comparator adaptations

Within each tissue, correct codon positions are pooled across all test sequences
and divided by all reference codon positions. The displayed cross-tissue mean
is the arithmetic mean of 29 tissue accuracies, not the pooled accuracy across
all tissues.

Coding positions require exact codon identity. The final dummy `X/w` contributes
one assessed position; **TAA, TAG and TGA are equivalent at this stop position**.
When a reference CDS is reconstructed from TXT alone its stop is represented as
TAA; this does not affect stop-equivalent scoring. The original stop is preserved
in the separate sequence-pair CSV. A missing stop is incorrect. Predictions are
compared at their original codon offsets: no sequence alignment is performed,
missing or incomplete codons are wrong, and extra codons beyond the reference
length do not enlarge the denominator. Coding-only accuracy is provided in an
additional output column.

For BiLSTM-CRF, the main score compares predicted and reference codon-box labels,
including `X/w`. The saved `predicted_cds` uses NNN for a tag that does not map to a
synonymous codon, preserving offsets; scoring uses `predicted_labels` for these
records and does not silently drop positions or repair the prediction.

The archived comparator predictions were produced with:

- **GEMORNA:** pretrained CDS model, protein input with the dummy X removed;
  the saved decoded CDS is scored as emitted. Repeated proteins share a cached
  prediction across tissues.
- **CodonTransformer:** `adibvafa/CodonTransformer`, revision
  `9744dcc920d813066391fc828d7a590207f148e8`, human/Homo sapiens context;
  `attention_type="original_full"`, `deterministic=True` and `match_protein=True`.
  Repeated proteins share a cached prediction.
- **mRNASyner:** pretrained `CDS_opt` model with reference protein and terminal X,
  450-amino-acid core windows and 30-amino-acid context. The primary comparison
  constrains the output tag to a codon compatible with the input amino acid.
  Invalid native tags are replaced using the highest-emission compatible tag.
  This preserves the encoded protein and differs from the native `box2cds`
  behavior, which omits unmappable tags. The latter is archived as
  `mrnasyner_native_cds_predictions.csv.gz` and is excluded from Fig. 1C means.

This release supports fresh inference of the mRNAviewer/general iDRO checkpoints
and complete re-scoring of the archived comparator predictions. Comparator
model training and fresh comparator decoding require their respective upstream
software and pretrained checkpoints; those checkpoints are not bundled here.

## Packaged provenance and checks

`archived/provenance.json` lists original and packaged SHA-256 checksums for the
six original metric CSVs, four prediction tables and 29 training logs. Prediction
tables and logs are losslessly gzip-compressed. The archived metric CSV contents
are unchanged. Scoring and summary scripts write new results separately.

```bash
python -m unittest discover -s evaluation/cds -p 'test_*.py' -v
```

The checks cover stop equivalence, missing/partial codons, ignored extra codons,
fixed offsets and synonymous codon differences. The released comparator audit
also verifies all integer counts against the original 29-tissue metric tables.
Device selection and the legacy CRF's CUDA flags are tested with mocks; these
tests do not allocate or reserve a GPU.
