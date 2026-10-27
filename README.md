# mRNAviewer

A web server for tissue-specific full-length mRNA optimization and interactive
visualization. Protein sequences are converted to an ORF and 5′/3′ UTRs using
General or one of 29 human tissue contexts.

Web server: <https://ccsm.uth.edu/mRNAviewer/>

Run the following commands from the repository root.

## Setup

```bash
conda create -n mrnaviewer-backend python=3.8.20 -y
conda run -n mrnaviewer-backend python -m pip install -r requirements-backend.txt
conda create -n mrnaviewer-dna python=3.8.20 -y
conda run -n mrnaviewer-dna python -m pip install -r requirements-utr5.txt
```

Install RNAfold 2.7.2, BLAST+ 2.17.0, Ghostscript and Perl. Both UTR regions
use the DNA environment. Model weights and miRBase indexes are installed
separately using the asset inventory:

```bash
python scripts/restore_assets.py --source /path/to/mRNAoptimizer_1212
cp .env.example .env
# Edit .env with your Python and external-tool executable paths.
source .env
```

## Run the web server

```bash
bash scripts/run_server.sh
```

Open <http://127.0.0.1:5000>. The launcher runs one server worker in the foreground.

## Run evaluation

Extract the released CDS/UTR training and test datasets for all 29 tissues:

```bash
python data/extract.py
```

### CDS: codon accuracy

```bash
CUDA_VISIBLE_DEVICES=1 "$MRNAVIEWER_BACKEND_PYTHON" evaluation/cds/evaluate_checkpoint.py \
  --context tissue --device cuda:0 \
  --output results/cds_tissue.csv --predictions results/cds_tissue_predictions.csv.gz

CUDA_VISIBLE_DEVICES=1 "$MRNAVIEWER_BACKEND_PYTHON" evaluation/cds/evaluate_checkpoint.py \
  --context general --device cuda:0 \
  --output results/cds_general.csv --predictions results/cds_general_predictions.csv.gz
```

### UTR: ROUGE and BLEU

```bash
CUDA_VISIBLE_DEVICES=1 "$MRNAVIEWER_UTR5_PYTHON" evaluation/utr/decode_bert2bert.py \
  --region 5utr --device cuda:0 --output results/5utr_predictions.csv.gz

CUDA_VISIBLE_DEVICES=1 "$MRNAVIEWER_UTR3_PYTHON" evaluation/utr/decode_bert2bert.py \
  --region 3utr --device cuda:0 --output results/3utr_predictions.csv.gz

python evaluation/utr/evaluate.py \
  --predictions results/5utr_predictions.csv.gz results/3utr_predictions.csv.gz \
  --output-dir results/utr
```

Choose an available GPU by changing `CUDA_VISIBLE_DEVICES`; use `--device cpu`
for CPU execution. Add `--tissues Brain Lung` to a decoding command to evaluate
a subset. UTR ROUGE/BLEU each average 1-, 2- and 3-gram scores; summary means
give equal weight to tissues. Generated outputs go to `results/`, excluded
from Git. Use `--help` on an evaluation script for additional options.
