# Reproduce the UTR evaluation (Fig. 1D–E)

This directory contains the test-set predictions and scoring code for the
5′ and 3′ UTR comparison in the mRNAviewer Application Note. Three methods
receive the same held-out CDS inputs and are compared with the same reference
UTRs: **mRNAviewer BERT2BERT**, **mRNASyner**, and **original iDRO BART**.
The identifiers in CSV files are `bert2bert_best`, `mrnasyner`, and `bart_base`.

## Recompute all reported scores without model weights

From the repository root, using Python 3.8 or later:

```bash
python evaluation/utr/evaluate.py --archive --output-dir results/utr
```

No Python packages, network, GPU, or model weights are needed. The command
checks archive SHA-256 values, verifies that CDS/reference pairs match between
methods, and recomputes every score from the sequence strings. It produces:

- `per_tissue_metrics.csv`: 174 rows (2 regions × 3 methods × 29 tissues).
- `macro_metrics.csv`: six rows with the **equally weighted mean of the 29 tissue means**, as used by the black diamonds in Fig. 1D–E.
- `pairwise_tissue_wins.csv`: strict, unrounded ROUGE/BLEU wins, ties, and losses for each pair of methods.

The optional `--per-sequence` switch also writes a compressed per-sequence
score table. `published_results/` contains the outputs of this exact command.
`reference_per_tissue_metrics.csv` is an independently retained subset of the
original evaluation tables, for checking numerical agreement.
`audit_results.py` checks reproduction and the manuscript's rounded results:

```bash
python evaluation/utr/audit_results.py --results-dir results/utr
```

There are **4,156 5′ UTR examples** and **1,391 3′ UTR examples** per method.
Different tissues can contain the same gene; such examples are retained in
each tissue, as in the original per-tissue benchmark. Pooling all examples
instead of averaging tissue means gives a different statistic and does not
reproduce the figure.

The reproduced Fig. 1D–E means (rounded to three decimals) are:

| Region | Method | ROUGE ↑ | BLEU ↑ |
|---|---|---:|---:|
| 5′ UTR | mRNAviewer BERT2BERT | 0.772 | 0.541 |
| 5′ UTR | mRNASyner | 0.742 | 0.531 |
| 5′ UTR | original iDRO BART | 0.563 | 0.425 |
| 3′ UTR | mRNAviewer BERT2BERT | 0.828 | 0.699 |
| 3′ UTR | mRNASyner | 0.766 | 0.526 |
| 3′ UTR | original iDRO BART | 0.641 | 0.470 |

Against mRNASyner, BERT2BERT has higher ROUGE/BLEU in **23/16 tissues for
5′ UTR**, and **28/29 tissues for 3′ UTR**. The manuscript's statement of
28 ROUGE wins and 29 BLEU wins applies to 3′ UTR. Against original BART,
both scores are higher in all 29 tissues for both regions. Comparisons use
unrounded values.

## Metric definitions

All scores operate on DNA nucleotides `A/C/G/T`, using **overlapping** 1-, 2-,
and 3-mers. Each occurrence contributes to a count. For order *n*, let
`overlap_n = sum_g min(count_prediction(g), count_reference(g))`.

- **ROUGE-n** is `overlap_n / number_of_reference_nmers` (recall).
- **ROUGE** is the arithmetic mean of ROUGE-1, ROUGE-2, and ROUGE-3.
- Modified precision `p_n` is `overlap_n / number_of_prediction_nmers`.
- **BLEU-n** is `BP × (p_1 × … × p_n)^(1/n)`, with equal log weights, no smoothing, and standard `BP = exp(min(0, 1-reference_length/prediction_length))`.
- **BLEU** is the arithmetic mean of cumulative BLEU-1, BLEU-2, and BLEU-3. It is not BLEU-3 alone, nor the arithmetic mean of modified precisions.

An unavailable n-gram denominator gives that order a score of zero. An empty
prediction receives zero for every score. References must be nonempty. Scores
are calculated per example, averaged within each tissue, then averaged across
tissues. Scores are reported on a **0–1 scale**. This reproduces the
ROUGE/BLEU subset of `utr_v2_overlap_bleu_20261019`; it is not a corpus BLEU or
a natural-language whitespace-tokenized ROUGE implementation.

The benchmark scores the **raw generated UTR**, before the web application
adds the Kozak sequence or assembles the full mRNA. Input CDS and reference
sequences are not modified to improve scores.

## Score other predictions

A CSV/CSV.gz should contain `predicted_utr`, `reference_utr`, `tissue`, and
`test_sequence`; `region`, `model`, and `input_cds` are recommended. Row
identities `(region, model, tissue, test_sequence)` must be unique. Alternative
prediction/reference column names can be specified explicitly.

```bash
python evaluation/utr/evaluate.py \
  --predictions my_predictions.csv.gz \
  --region 5utr --model my_method --output-dir results/my_method
```

Alternatively, provide paired plain-text files with one sequence per line:

```bash
python evaluation/utr/evaluate.py \
  --prediction-file predicted.txt --reference-file reference.txt \
  --region 3utr --model my_method --tissue Brain \
  --output-dir results/brain
```

Do not remove blank prediction lines: they represent failed/empty outputs and
are scored as zero. Blank reference lines and invalid bases are rejected.

## Generate new BERT2BERT predictions

First extract the processed datasets using the instructions in
[`data/README.md`](../../data/README.md), restore the model assets using the
repository asset instructions, and activate the environment specified by
[`requirements-utr5.txt`](../../requirements-utr5.txt) (also used by 3′ UTR).
The default model and data paths are relative to the repository itself; the
commands can be run from another working directory.

```bash
python evaluation/utr/decode_bert2bert.py \
  --region 5utr --data-root data/extracted/utr_tissue_data \
  --model-root workspace/codon/utr_tissue_model --device cpu \
  --output results/5utr_bert2bert.csv.gz

python evaluation/utr/decode_bert2bert.py \
  --region 3utr --data-root data/extracted/utr_tissue_data \
  --model-root workspace/codon/utr_tissue_model --device cuda:0 \
  --output results/3utr_bert2bert.csv.gz

python evaluation/utr/evaluate.py \
  --predictions results/5utr_bert2bert.csv.gz results/3utr_bert2bert.csv.gz \
  --output-dir results/bert2bert
```

`--tissues Brain Lung` limits a run; otherwise all 29 tissues are decoded.
`--batch-size` defaults to 8 and `--threads` to 4. The device defaults to CPU;
when using shared hardware, choose a GPU explicitly. CUDA allocation is
limited to 45% of that GPU's memory. Model weights are loaded strictly from
local files; there is no automatic Hub download.

The decoder reads the **frozen per-tissue model and generation choices** in
`frozen_model_selection.json`, checks the restored `generation_config.json`,
and uses the same `workspace/codon/utr5_runtime` code as the web server.
`--verify-weights` additionally checks each weight file's SHA-256. The
manifest preserves checkpoint origins and selected epochs for reproducibility.
Neither test references nor their lengths choose a checkpoint, beam width,
or output length limit. The frozen 3′ UTR settings use 8 beams and length
penalty 2; 5′ UTR uses the per-tissue validated beam and nucleotide bounds
recorded in the manifest. All decoding uses deterministic beam search.

Progress is written after each batch to `<output>.partial.csv`; running the
same command again resumes completed examples and checks that the input and
reference strings have not changed. Keep the same model assets and parameters
when resuming. CPU and CUDA arithmetic or different library versions can
occasionally change nearly tied beam choices; the archived predictions
provide the exact inputs to the reported results.
`decoder_smoke_verification.json` records successful CPU checks of this
portable entry point against one archived Brain prediction for each region.

## Comparator and provenance records

The six compressed files in `predictions/` preserve the actual BERT2BERT,
mRNASyner, and BART-base outputs used in the comparison, not fabricated
outputs from a metric table. They contain the sequence strings and identities;
scores are intentionally recomputed by `evaluate.py`.
`prediction_manifest.json` records both archive and original-source SHA-256
values. `frozen_model_selection.json` preserves the deployment selection and
generation settings, including their original paths as provenance identifiers;
those historical paths are not required by the portable decoder.

The mRNASyner and original BART inference implementations and their large
weights are not vendored in this directory. Their archived predictions permit
the published sequence-level comparison to be reproduced without their
separate software environments. Regenerating comparator predictions requires
the corresponding upstream model, weights, and recorded settings, rather
than the BERT2BERT decoder above.

Run the count-overlap and brevity-penalty checks with:

```bash
python -m unittest discover -s evaluation/utr -p test_metrics.py -v
```
