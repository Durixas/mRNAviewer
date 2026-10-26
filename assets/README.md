# External runtime assets

`manifest.json` identifies 110 files by application-relative path, size and
SHA256. The complete inventory is approximately53.35 GiB. Model weights,
serialized CDS alphabets/settings, miRBase BLAST indexes and an optional
website paper are excluded from Git.

UTR checksums come from the verified deployment manifests. The published
code contains every bundle's architecture, tokenizer, generation config
and source metadata. No public asset repository URL has been selected yet.

Restore from a complete installation using `scripts/restore_assets.py --source`,
or from a model repository using `--hf-repo` after the assets are hosted.
Use `--check --verify` for a full SHA256 audit. See the root README for setup.
