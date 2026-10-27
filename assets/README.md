# Runtime assets

`manifest.json` lists model weights and database files with their expected
paths, sizes and SHA-256 checksums. Human miRBase files are already included
in Git. Download the model archives from
[Zenodo](https://doi.org/10.5281/zenodo.23681525) and follow its `readme.txt`
to reconstruct and extract them into the repository root. Public downloads
become available when the Zenodo record is published. Then verify the assets:

```bash
python scripts/restore_assets.py --check --verify
```

See the [root README](../README.md#setup) for setup.
