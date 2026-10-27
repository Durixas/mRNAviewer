# Processed data for 29 human tissues

This directory contains the processed data underlying the ORF/CDS and UTR
benchmarks in the mRNAviewer application note. Tissues are listed in
[`tissues.txt`](tissues.txt). Counts are sums across tissues: a gene or sequence
can occur in several tissues, so these are **not counts of unique genes**.

The source abundance atlas is Wang et al. (2019),
[doi:10.15252/msb.20188503](https://doi.org/10.15252/msb.20188503).
These are processed sequence datasets, not the original abundance measurements.
The preprocessing and selection described in the application note should be
cited together with the source atlas when reusing them.

## Extract or check the data

Only Python's standard library is needed (Python 3.8 or newer):

```bash
# From the repository root; verify the compressed archives and each member.
python data/extract.py --verify-only

# Extract all data under data/extracted/.
python data/extract.py
```

Archives can be selected with `--archive`, for example
`python data/extract.py --archive utr_tissue_data.tar.gz`.
Use `--output /path/to/data` to choose another destination. Extraction checks
SHA-256 values against [`manifest.json`](manifest.json), preserves record order,
and refuses to replace existing files with different contents. The extracted
copy is excluded from Git; the compressed source files are versioned.

## Included files

| Archive | Contents after extraction |
| --- | --- |
| `cds_tissue_data.tar.gz` | `cds_tissue_data/<tissue>/{train,dev,test}.txt`: the exact BiLSTM–CRF input files used for tissue adaptation and evaluation. |
| `cds_sequence_pairs.tar.gz` | `cds_sequence_pairs/<tissue>/{train,dev,test}.csv`: protein/CDS pairs validated against each TXT record; `cds_original_csv/<tissue>/{train,val,test}.csv`: original input CSV files, unchanged. |
| `utr_tissue_data.tar.gz` | `utr_tissue_data/<tissue>/tran_c{5,3}.txt`, `tran_{5,3}u.txt`, `eval_c{5,3}.txt`, `eval_{5,3}u.txt`, and `tran_b{5,3}.txt`: original paired CDS/UTR files plus codon-box inputs used by the original BART baseline. |
| `bert2bert_frozen_splits.tar.gz` | `bert2bert/{5utr,3utr}/<tissue>/{train,validation,test}.csv`: the exact final BERT2BERT adaptation splits and matched test sets; original frozen JSON splits, provenance, split counts, and the earlier 128-record validation sets are also included. `data_preparation_provenance/` retains the original data preparation source files. |

[`dataset_summary.csv`](dataset_summary.csv) provides counts for every tissue,
[`data_audit.json`](data_audit.json) gives totals and length checks, and
[`manifest.json`](manifest.json) lists every archive member's size and SHA-256.
Entries copied from the research workspace also name their original relative
source path. Original source files are preserved byte for byte; derived CSV
exports are explicitly marked in the manifest.

## Dataset sizes and actual partitions

| Task | Original train or training pool | Original validation | Test | Total |
| --- | ---: | ---: | ---: | ---: |
| CDS | 45,357 train | 5,672 dev | 5,682 | 56,711 |
| 5′ UTR | 37,524 in `tran_*` pool | See below | 4,156 | 41,680 |
| 3′ UTR | 12,633 in `tran_*` pool | See below | 1,391 | 14,024 |

CDS has pre-existing train/dev/test files with approximately 80%/10%/10%
allocation. The UTR `tran_*` files are a training **pool**, not a training split
with validation already removed. The original UTR preparation code holds out
10% per tissue (rounding down) into `eval_*`, which is the test set used in the
benchmarks. The original BART adaptation code subsequently uses a seeded
90%/10% split of the remaining pool (`torch.Generator().manual_seed(42)`).
Thus its actual allocation is approximately **81%/9%/10%**, with 33,758/3,766
training/validation examples for 5′ UTR and 11,358/1,275 for 3′ UTR. There are
no separate original `val_*` UTR text files.

The final BERT2BERT adaptation experiments use the following **frozen** subsets
of those original pools, rather than inventing or regenerating a new 8:1:1
partition:

| Final BERT2BERT experiment | Train | Validation | Matched test |
| --- | ---: | ---: | ---: |
| 5′ UTR | 7,034 | 1,244 | 4,156 |
| 3′ UTR | 2,140 | 697 | 1,391 |

All CDS inputs and UTR targets appearing in any tissue's test set or in the
earlier 128-example validation set are excluded from these new training and
validation subsets. Within each tissue, repeated CDS inputs are deduplicated
(the first paired target is retained if targets conflict). The remaining CDS
inputs are sorted by SHA-256 of `seed:CDS`, and validation targets are excluded
from training:

- 5′ UTR: seed `20261025`, 15% validation, bounded to 32–64 records per tissue.
- 3′ UTR: seed `20261026`, 20% validation, bounded to 24–48 records per tissue.

The frozen JSON and CSV files, rather than an approximate ratio stated in prose,
are authoritative for reproducing the final adaptation experiments. These
exclusions explain why the final adaptation subsets are smaller than the
original pools. No test score is used to construct these subsets.

## Sequence formats and stop codons

Each CDS TXT block is one sequence, separated from the next by a blank line.
Each nonempty line contains `amino_acid codon_box_label`, separated by a space.
The terminal stop position is encoded as `X w`; this `X` is a synthetic symbol,
not an amino acid to feed to a protein encoder. The mapping for all 64 codons
is given in [`codon_box_mapping.json`](codon_box_mapping.json).

All three stop codons share `X w` in the model format. To preserve the actual
reference stop codon for DNA-level comparisons, use the validated
`cds_sequence_pairs` CSV exports. They contain `tissue`, `sequence_id` (1-based
TXT block order), `source_csv_line`, `protein` (without the terminal synthetic
X), and `reference_cds`. The unmodified original CSVs contain 97 records rejected
by the original converter; those rejected records are absent from both the TXT
files and validated exports. No rejected row has been silently added back.

Each UTR text file contains one DNA sequence per line; the input and target
with the same line number form a pair. `c5`/`c3` denotes the CDS input and
`5u`/`3u` the reference UTR. `b5`/`b3` denotes the codon-box representation used
by the original BART pipeline. The BERT2BERT CSV exports use `tissue`,
`sequence_id`, `input_cds`, and `reference_utr`; order matches the frozen JSON
or original test-file order. The original JSON field `test_sequence` is a
1-based local record index even when the enclosing partition is train or
validation; it does not imply that those records belong to the test set.

All valid CDS sequences in the public splits are shorter than 2,500 nt
(maximum 2,499 nt); all reference UTRs are 50–500 nt inclusive.

## Evaluation aggregation

ORF accuracy pools assessed codon positions within each tissue. ROUGE and BLEU
are averaged over UTR sequences within each tissue. Figure-level summary means
give **equal weight to each of the 29 tissues**, rather than pooling sequences
across tissues. The repository's `evaluation/` scripts reproduce these metrics.
