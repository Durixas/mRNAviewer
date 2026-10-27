# mRNAviewer

**A web server for tissue-specific full-length mRNA optimization and interactive visualization**

mRNAviewer converts a protein sequence into an optimized open reading frame
(ORF/CDS) and corresponding 5′ and 3′ untranslated regions (UTRs). Users select
**General** or one of **29 human tissues**. The interface connects sequence
and region selection to nucleotide composition, RNA secondary structure,
minimum free energy (MFE), and candidate miRNA/RBP binding sites.

**Web server:** <https://ccsm.uth.edu/mRNAviewer/> — freely available without registration.

This repository accompanies the Bioinformatics Application Note manuscript
*“mRNAviewer: a web server for tissue-specific full-length mRNA optimization
and interactive visualization”* by Hao Zhou, Kexin Huang, Jianguo Wen and
Xiaobo Zhou. It provides the web application, processed tissue datasets,
benchmark predictions, and evaluation code.

## Workflow

1. Submit one amino acid sequence and select a translation context.
2. The iDRO-derived **BiLSTM–CRF** predicts synonymous codon labels to form an ORF.
3. Separate **BERT2BERT** generators produce ORF-conditioned 5′ and 3′ UTRs using
   the selected context's model bundles and frozen decoding configurations.
4. The server assembles 5′ UTR–ORF–3′ UTR with the GCCACC Kozak sequence and
   tandem stop codons, and displays region boundaries.
5. Inspect the whole sequence or a selected interval, then download sequences
   and analysis tables.

Both UTR generators use the local DNABERT-2-based encoder/decoder runtime.
Each region has independent bundles for the 29 tissue contexts and General.
Model configurations, tokenizers and selection provenance are included in
[`workspace/codon/utr_tissue_model/`](workspace/codon/utr_tissue_model/).

RNAfold **2.7.2** computes structures and MFE (`-p -d2 --noLP`, 37 °C).
Selected intervals are folded as separate sequences. Candidate miRNA sites
are searched with BLAST+ **2.17.0** against human miRBase **23.1** databases.
RBP motif matching uses **RBPDB v1.3.1**, including overlapping matches,
IUPAC ambiguity codes, alternatives and bounded repeats. These annotations
support inspection and experimental planning.

## Processed datasets: all 29 tissues

The datasets derive from the [29-tissue protein/mRNA abundance atlas
(Wang et al., 2019)](https://doi.org/10.15252/msb.20188503). Genes were selected
independently within each tissue using the top 30% of protein-to-mRNA ratios,
with sequence annotations from Ensembl release 115 (GRCh38). Counts include
a gene each time it occurs in a tissue.

| Task | Paired examples | Held-out test examples |
| --- | ---: | ---: |
| Protein → ORF/CDS | 56,711 | 5,682 |
| ORF → 5′ UTR | 41,680 | 4,156 |
| ORF → 3′ UTR | 14,024 | 1,391 |

The release contains **actual train, validation and test files**, the original
UTR training pools, and the final frozen BERT2BERT adaptation splits. Valid
CDS sequences are shorter than 2,500 nt; reference UTRs are 50–500 nt.
Four checksummed archives total **137.29 MiB** (399.01 MiB extracted).

```bash
# Python 3.8+; run from the repository root.
python data/extract.py --verify-only
python data/extract.py
```

See [data formats and actual split definitions](data/README.md),
[per-tissue counts](data/dataset_summary.csv), and
[archive/member checksums](data/manifest.json). The synthetic terminal `X`
in BiLSTM–CRF data encodes a stop position; the paired CSV files retain the
original DNA stop codon and provide proteins without that synthetic residue.

## Reproduce the manuscript evaluation

Saved predictions and scoring code allow the benchmark to be checked with
**Python's standard library, without model weights or a GPU**:

```bash
python evaluation/reproduce.py
```

The command verifies and extracts the released data, recomputes comparator
CDS accuracy, summarizes the archived ORF results, and recalculates UTR scores.
Outputs are written under `results/`. See the
[evaluation guide](evaluation/README.md) for individual commands and fresh
checkpoint decoding.

### Metrics and aggregation

- **ORF codon accuracy:** correct codon positions divided by all assessed
  positions within a tissue, with the terminal stop position included.
- **UTR ROUGE:** arithmetic mean of overlapping nucleotide ROUGE-1, ROUGE-2
  and ROUGE-3 recall, using clipped occurrence counts.
- **UTR BLEU:** arithmetic mean of cumulative nucleotide BLEU-1, BLEU-2 and
  BLEU-3, using clipped precision, standard brevity penalty and no smoothing.

UTR scores are computed per sequence and averaged within each tissue.
Figure-level means give **equal weight to the 29 tissues** for both tasks.
UTR evaluation scores raw generated UTRs, before web assembly adds the Kozak
sequence. The [UTR guide](evaluation/utr/README.md) specifies the formulas,
fixed generation configurations and per-tissue comparisons.

### Manuscript benchmark means

| ORF method | Codon accuracy (%) |
| --- | ---: |
| mRNAviewer | 53.80 |
| General iDRO | 53.37 |
| mRNASyner | 52.92 |
| CodonTransformer | 50.50 |
| GEMORNA | 44.48 |

The mRNAviewer ORF column preserves the historical maximum test accuracy
reported over training epochs, at the precision retained in the original
logs. Fresh checkpoint evaluation is recorded separately; the
[CDS guide](evaluation/cds/README.md) documents this provenance and provides
a log-selection audit.

A [complete-test GPU follow-up](evaluation/cds/verification/gpu_deployed_20261026/README.md)
checks six deployed models (1,224 sequences). Four agree with the historical
table at four decimals and five at three decimals. Kidney differs at both
precisions; its independent CPU and GPU predictions are identical. All fresh
measurements are published alongside the historical results.

| UTR region | Method | ROUGE ↑ | BLEU ↑ |
| --- | --- | ---: | ---: |
| 5′ UTR | mRNAviewer BERT2BERT | **0.772** | **0.541** |
| 5′ UTR | mRNASyner | 0.742 | 0.531 |
| 5′ UTR | Original iDRO BART | 0.563 | 0.425 |
| 3′ UTR | mRNAviewer BERT2BERT | **0.828** | **0.699** |
| 3′ UTR | mRNASyner | 0.766 | 0.526 |
| 3′ UTR | Original iDRO BART | 0.641 | 0.470 |

Against mRNASyner, the 5′ UTR model has higher ROUGE in 23 tissues and higher
BLEU in 16; the corresponding 3′ UTR counts are 28 and 29. Full-precision
per-tissue and macro tables are included with the evaluation code.

## Install the web server or generate new predictions

See [installation and operation](docs/INSTALLATION.md) for the two Python
environments, external tools, configuration, startup, GPU scheduling and checks.
Runtime dependencies are pinned in
[`requirements-backend.txt`](requirements-backend.txt) and
[`requirements-utr5.txt`](requirements-utr5.txt) (shared by both UTR regions).

Runtime weights and BLAST indexes are separate assets, approximately
**53.35 GiB**. [`assets/manifest.json`](assets/manifest.json) records their
paths and SHA-256 values; [`scripts/restore_assets.py`](scripts/restore_assets.py)
restores them from a complete installation or a specified Hugging Face asset
repository. **A public model-weight download location has not yet been
configured.** Archived sequence-level evaluation is fully available here;
fresh inference additionally requires the corresponding model assets.

The standalone [CDS evaluator](evaluation/cds/README.md) and
[BERT2BERT UTR decoder](evaluation/utr/README.md#generate-new-bert2bert-predictions)
use the released test files and support explicitly selected CPU/GPU devices.
Comparator predictions are included with source hashes and decoding provenance;
regenerating those predictions requires the respective upstream models.

## Repository layout

```text
backend_server.py                  Flask API, queue and GPU scheduling
frontend/mRNAviewer/               Web interface
workspace/codon/                   CDS/UTR inference and model definitions
workspace/codon/utr_tissue_model/   Context bundles: configs and tokenizers
workspace/rnafold/, gen_image/     Folding and plotting scripts
workspace/blast/                   miRNA/RBP analysis and motif tables
data/                              Processed 29-tissue datasets and checksums
evaluation/cds/                    Codon accuracy, predictions and provenance
evaluation/utr/                    ROUGE/BLEU, predictions and decoding entry point
assets/, scripts/, deploy/         Asset restoration and deployment
tests/                             Web model-routing checks
```

## Citation and contact

**Hao Zhou, Kexin Huang, Jianguo Wen, Xiaobo Zhou.** *mRNAviewer: a web server
for tissue-specific full-length mRNA optimization and interactive
visualization.* Manuscript prepared for Bioinformatics; publication details
will be added when available.

The underlying iDRO method is described in
[Gong et al. (2023), Integrated mRNA sequence optimization using deep learning](https://doi.org/10.1093/bib/bbad001).
Please also cite the source atlas when reusing the processed datasets.
Third-party code notices are preserved in their respective directories.

Correspondence: [Xiaobo Zhou](mailto:Xiaobo.Zhou@uth.tmc.edu).
