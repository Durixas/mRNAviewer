# Runtime assets

`manifest.json` lists model weights and database files with their expected
paths, sizes and SHA-256 checksums.

```bash
python scripts/restore_assets.py --source /path/to/mRNAoptimizer_1212
python scripts/restore_assets.py --check --verify
```

See the [root README](../README.md#setup) for setup.
