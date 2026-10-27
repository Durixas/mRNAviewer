# UTR evaluation

The [root README](../../README.md#utr-rouge-and-bleu) provides model decoding and evaluation commands.

To score predictions from another method:

```bash
python evaluation/utr/evaluate.py \
  --predictions results/my_utr_predictions.csv.gz --region 5utr --model my_method \
  --output-dir results/my_utr_metrics
```

CSV columns: `tissue`, `test_sequence`, `predicted_utr`, `reference_utr`.
ROUGE averages overlapping nucleotide ROUGE-1/2/3 recall. BLEU averages
cumulative BLEU-1/2/3 with standard brevity penalty and no smoothing.
Scores are averaged within tissue, then equally across tissues.
Use `--help` for paired text input and other options.
