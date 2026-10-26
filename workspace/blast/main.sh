set -euo pipefail
mkdir -p output
tr 'uU' 'TT' < query.fa > query_dna.fa

# The title field contains the miRBase accession for each hit.
fields='6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore stitle'
DEFAULT_BLASTN=blastn
if [[ ! -x "$DEFAULT_BLASTN" ]]; then DEFAULT_BLASTN=blastn; fi
BLASTN_BIN="${MRNAVIEWER_BLASTN_BIN:-$DEFAULT_BLASTN}"
DB_DIR="${MRNAVIEWER_MIRBASE_DB_DIR:-mibase/releases/23.1}"
"$BLASTN_BIN" -query query_dna.fa -db "$DB_DIR/hairpin_hsa" -out output/hairpin_raw.out -outfmt "$fields" -strand minus -dust no -word_size 7 -max_target_seqs 3000
"$BLASTN_BIN" -query query_dna.fa -db "$DB_DIR/mature_hsa" -out output/mature_raw.out -outfmt "$fields" -strand minus -dust no -word_size 7 -max_target_seqs 3000

python3 mirna_results.py
python3 rbp_results.py
