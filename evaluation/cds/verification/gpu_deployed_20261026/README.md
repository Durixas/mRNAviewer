# Complete-test GPU checks of deployed CDS models

Six tissue models from the existing web installation were evaluated on their
**complete released test sets**, totaling **1,224 sequences**. Tissues were
chosen before inspecting this run, and all six results are retained.
No model weights or manuscript benchmark columns were changed.

Inference used a single Tesla V100-PCIE-32GB (physical GPU1), PyTorch 2.4.1,
batch size 1, four CPU threads, seed 42 and disabled cuDNN, as recorded in
`run_metadata.json` and `metrics.csv.provenance.json`. Observed GPU process
memory was approximately 400 MiB. GPU0 was unused by this run; the process
exited and released GPU1 on completion.

## Results

| Tissue | Test sequences | Correct/total positions | GPU accuracy | Archived max test | Match at 4 dp | Match at 3 dp |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Adrenal_gland | 208 | 44262/81700 | 0.541762546 | 0.5418 | True | True |
| Brain | 207 | 43537/80211 | 0.542780915 | 0.5428 | True | True |
| Kidney | 188 | 39951/71721 | 0.557033505 | 0.5579 | False | False |
| Lung | 222 | 49629/93631 | 0.530048809 | 0.5300 | True | True |
| Placenta | 200 | 42986/80317 | 0.535204253 | 0.5352 | True | True |
| Tonsil | 199 | 43259/79076 | 0.547055997 | 0.5472 | False | True |

**Four of six** reproduce the archived score at four decimal places;
**five of six** agree at three decimal places. The comparison preserves
both precisions and full count-derived accuracy.

- **Brain:** GPU counts are identical to the earlier complete CPU test,
  `43537/80211 = 0.5427809153`; this rounds to 0.5428 or 0.543.
- **Kidney:** independent complete CPU inference also gives
  `39951/71721 = 0.5570335048`. All 188 CPU and GPU prediction strings are
  identical. This is a measured checkpoint/table difference. The historic
  maximum is 0.5579 at epoch 7 (1-based), while the log's last saved
  validation-selected epoch is 8, with test score 0.5570. The present score
  agrees with the latter at four decimals; score agreement alone does not
  prove an epoch identity.
- **Tonsil:** fresh accuracy is 0.5470559968, which rounds to 0.5471;
  the archived maximum is 0.5472. Both display as 0.547 at three decimals.

These observations do not establish agreement for the other 23 tissues.
The manuscript's historical maximum-test table is retained separately.
Model weights remain external runtime assets because this sample did not
satisfy agreement of every tested checkpoint with that table.

## Included artifacts

- `metrics.csv`: fresh full-test GPU metrics and counts.
- `predictions.csv.gz`: all 1,224 GPU predictions, proteins, reference labels
  and position counts.
- `metrics.csv.provenance.json`: model/test SHA-256, architecture hash,
  PyTorch version and device.
- `kidney_cpu.csv`, its provenance JSON and `kidney_cpu_predictions.csv.gz`:
  the independent full CPU cross-check.
- `run_metadata.json`: selected tissues, hardware, inference parameters and
  artifact checksums.
- `comparison.csv`, `audit.json`: recomputed agreement and integrity checks.
- `capture_weight_audit.json`: successful hash verification of all six actual
  deployment weight files at the time of this measurement.

## Reproduce without models or a GPU

From the repository root after extracting the released CDS data:

```bash
python data/extract.py --archive cds_tissue_data.tar.gz
python evaluation/cds/audit_deployed.py
```

The audit verifies file hashes, recomputes all GPU counts from saved
predictions, compares Brain with its CPU metrics, and independently rescores
and compares the Kidney CPU/GPU prediction strings. It verifies the recorded
checkpoint hashes against `assets/manifest.json`. If the runtime weights are
available, additionally check the actual files:

```bash
python evaluation/cds/audit_deployed.py \
  --model-root workspace/codon/cds_tissue_model
```

An audit status of `passed` means that files and reported measurements
reproduce. Historical-score agreement is reported in separate fields.
A strict agreement gate is optional and **fails for this recorded run**:

```bash
python evaluation/cds/audit_deployed.py --require-historical-match 3dp
```

## Generate a new GPU run

Use the backend/CDS environment and the restored original deployment weights:

```bash
CUDA_VISIBLE_DEVICES=1 OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 \
python evaluation/cds/evaluate_checkpoint.py \
  --context tissue --device cuda:0 --threads 4 --batch-size 1 \
  --tissues Adrenal_gland Brain Kidney Lung Placenta Tonsil \
  --output results/deployed_gpu/metrics.csv \
  --predictions results/deployed_gpu/predictions.csv.gz
```

Choose an available GPU explicitly on shared hardware. Supply `--checkpoint`
with a quoted `{tissue}` path template when weights are located elsewhere.
Fresh output is kept separate from these archived verification artifacts.
