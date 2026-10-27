# CDS evaluation

The [root README](../../README.md#cds-codon-accuracy) provides checkpoint evaluation commands.

To score predictions from another method:

```bash
python evaluation/cds/score_predictions.py \
  --predictions results/my_cds_predictions.csv.gz --model my_method \
  --output results/my_cds_metrics.csv
```

Required CSV columns: `tissue`, `test_sequence` (1-based test record), `predicted_cds`.
Accuracy pools codon positions within each tissue, including the terminal
stop position. The three stop codons are equivalent at that position.
Use `--help` for tissue filtering and checkpoint path options.
