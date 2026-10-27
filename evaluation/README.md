# Reproduce the sequence-level benchmarks

Run all commands from the repository root with Python 3.8 or newer.
The archived evaluation uses only Python's standard library.

```bash
python evaluation/reproduce.py
```

This verifies all processed data archives and members, extracts the original
splits, checks archived CDS predictions, the six-model GPU follow-up and training logs, and writes the
Fig. 1C ORF summary and Fig. 1D–E ROUGE/BLEU tables under `results/`.
Both figure summaries give the 29 tissues equal weight.
Existing differing extracted data are never overwritten.

Individual stages:

```bash
python data/extract.py
python evaluation/cds/verify_release.py
python evaluation/cds/audit_deployed.py --output-dir results/cds/deployed_gpu
python evaluation/cds/summarize_archived.py --output-dir results/cds
python evaluation/utr/evaluate.py --archive --output-dir results/utr
python evaluation/utr/audit_results.py --results-dir results/utr
```

- [CDS: accuracy, stop handling, historical score provenance, and new checkpoint evaluation](cds/README.md)
- [UTR: ROUGE/BLEU formulas, archived outputs, and BERT2BERT decoding](utr/README.md)
- [Dataset formats, counts, and actual training/validation/test partitions](../data/README.md)

UTR evaluation reports ROUGE and BLEU, including their 1-, 2-, and 3-gram
components. Scores are on a 0–1 scale. ORF summary tables also provide percent
accuracy. `evaluation/cds/results/` and `evaluation/utr/published_results/`
retain reference tables; the unified command writes fresh output under
`results/`.

The ORF mRNAviewer figure column is the archived maximum test score printed
across epochs, with four-decimal source precision. The selection audit
compares logged test maxima with logged validation selections; it does not
infer which historical epoch a deployed weight file represents. Fresh
checkpoint measurements are generated separately using the CDS evaluator.

The repository contains archived comparator predictions for exact rescoring.
Fresh mRNAviewer inference additionally requires its runtime assets and
pinned Python environments. Fresh comparator inference requires each
method's upstream software and weights.

Metric checks:

```bash
python -m unittest discover -s evaluation/cds -p 'test_*.py' -v
python -m unittest discover -s evaluation/utr -p test_metrics.py -v
```

The complete-test GPU follow-up reports **4/6 agreement at four decimals**
and **5/6 at three decimals**, with the underlying differences retained.
Its audit checks measurement integrity and score reproduction; historical
agreement is a separate field, not a prerequisite for an integrity pass.
