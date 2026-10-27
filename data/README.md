# Data for 29 human tissues

```bash
python data/extract.py
```

Files are extracted under `data/extracted/`:

- `cds_tissue_data/<tissue>/{train,dev,test}.txt`: BiLSTM–CRF inputs; a terminal `X w` represents the stop position.
- `cds_sequence_pairs/<tissue>/{train,dev,test}.csv`: matching protein/CDS pairs with the original stop codon.
- `utr_tissue_data/<tissue>/`: paired `tran_*` training pools and `eval_*` test files (`c5`/`c3` are CDS inputs, `5u`/`3u` are UTR targets).
- `bert2bert/{5utr,3utr}/<tissue>/{train,validation,test}.csv`: frozen BERT2BERT partitions.

[Tissue names](tissues.txt), [per-tissue counts](dataset_summary.csv) and
[archive/member checksums](manifest.json) are included.
Data source: [Wang et al. (2019)](https://doi.org/10.15252/msb.20188503).
