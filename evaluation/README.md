# Evaluation

See the [root README](../README.md#run-evaluation) for complete commands.

- `cds/evaluate_checkpoint.py`: decode general or tissue BiLSTM–CRF models and calculate codon accuracy.
- `cds/score_predictions.py`: score an existing CDS prediction CSV.
- `utr/decode_bert2bert.py`: decode the 5′ or 3′ UTR models.
- `utr/evaluate.py`: calculate ROUGE/BLEU from UTR prediction CSVs or paired text files.

Training/test data are in `data/`; model weights are restored separately.
Write generated outputs under `results/`, which is excluded from Git.
