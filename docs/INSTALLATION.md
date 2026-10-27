# Install and operate mRNAviewer

## Installation

### 1. Python environments

The working server uses Python 3.8.20 and PyTorch 2.4.1. Backend/CDS and UTR
inference use separate environments because their Transformers versions differ.
Use a PyTorch build compatible with the target machine's CUDA driver.

```bash
conda create -n mrnaviewer-backend python=3.8.20 -y
conda run -n mrnaviewer-backend python -m pip install -r requirements-backend.txt
conda create -n mrnaviewer-dna python=3.8.20 -y
conda run -n mrnaviewer-dna python -m pip install -r requirements-utr5.txt
```

Both UTR regions use the same DNA environment; `requirements-utr3.txt`
includes the same dependency pins. Existing compatible environments can be reused.

### 2. External tools

Install RNAfold (the validated server uses ViennaRNA 2.7.2), NCBI BLAST+ 2.17.0,
Ghostscript and Perl. Set their executable paths in the configuration below.
The repository preserves the RNAfold plotting script, but carries no compiled
RNAfold/Ghostscript/BLAST executables.

### 3. Restore runtime assets

The full inventory is approximately **53.35 GiB**, of which **53.08 GiB** is
UTR weights. It also includes CDS weights, the required
`lstmcrf_1500.dset` alphabets/settings, and the human miRBase 23.1 BLAST
database. The paper linked from the tutorial is an optional external asset.

From an existing complete installation, copying only the listed assets:

```bash
python scripts/restore_assets.py --source /path/to/mRNAoptimizer_1212
python scripts/restore_assets.py --check --verify
```

If the asset inventory has been hosted in a Hugging Face model repository
with the same relative paths:

```bash
python scripts/restore_assets.py --hf-repo YOUR_HF_NAME/mRNAviewer-assets --revision COMMIT_OR_TAG --verify
```

The asset repository ID/revision is supplied by the deployer. No public asset
URL is configured yet. SHA256 verification reads all asset bytes. Existing
files are checked rather than overwritten by local restoration.

### 4. Configure and start

```bash
cp .env.example .env
# Edit .env with the two Python executables and installed tool paths.
source .env
bash scripts/run_server.sh
```

Default URL: `http://127.0.0.1:5000`. Configure `MRNAVIEWER_BIND` to change
the host/port. The frontend and API are served by the same application.
A host Nginx example is in [deploy/nginx.conf.example](../deploy/nginx.conf.example).

Use **one Gunicorn worker**, as in the launcher: task storage, tool locks and
GPU reservations are in-process. The worker uses four request threads.

## GPU behavior

The scheduler chooses among physical GPUs 0 and 1: more free VRAM, then lower
utilization, then GPU1 for ties. GPUs running other users' tasks remain eligible;
GPUs already reserved by this Web service are queued appropriately. Both UTR
subprocesses inherit the selected UUID through `CUDA_VISIBLE_DEVICES` and run
sequentially, with a 45% CUDA allocator limit per child and four CPU threads.

`MRNAVIEWER_UTR5_PYTHON` selects the DNA interpreter;
`MRNAVIEWER_UTR3_PYTHON` can override it for 3′ UTR.
`MRNAVIEWER_UTR5_THREADS`/`MRNAVIEWER_UTR3_THREADS` override child thread counts.

The assembled coding segment terminates in TAA followed by TGA. The Web
pipeline conditions 3′ UTR on that emitted segment and adds GCCACC before the
start codon when assembling the 5′ UTR and ORF.
Batch inference also supports explicit CPU execution via `main_batch.py --cpu`.

## Checks and maintenance

With runtime assets restored, run the routing and bundle checks on CPU:

```bash
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  /path/to/backend/bin/python -m unittest discover -s tests -v
```

Run commands from the repository root. The checks validate context routing,
model bundle configuration, batch requests, and device propagation. Benchmark
scoring and fresh model inference are documented in
[the evaluation guide](../evaluation/README.md).

Results are retained for 24 hours after completion by default. A cron request
can invoke the server's managed cleanup:

```cron
*/30 * * * * curl -fsS -X POST http://127.0.0.1:5000/backend/executor/retiring >/dev/null
```

The release includes sequence optimization, folding, miRNA and RBP analyses.
Legacy VDJ API placeholders do not perform an analysis. Third-party notices
are preserved beside the frontend, CDS code and local DNABERT2 encoder.
