#!/usr/bin/env python3
"""Verify and extract the bundled, checksum-indexed mRNAviewer datasets."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile


def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    base = Path(__file__).resolve().parent
    manifest = json.loads((base / "manifest.json").read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=base / "extracted")
    parser.add_argument("--verify-only", action="store_true", help="Check archives and every member without writing data.")
    parser.add_argument("--archive", action="append", choices=[r["file"] for r in manifest["archives"]],
                        help="Process just this archive; repeat to select multiple archives.")
    args = parser.parse_args()
    total = 0
    for archive in manifest["archives"]:
        if args.archive and archive["file"] not in args.archive:
            continue
        path = base / archive["file"]
        if path.stat().st_size != archive["bytes"] or digest_file(path) != archive["sha256"]:
            raise ValueError(f"Archive checksum/size mismatch: {path}")
        expected = {r["path"]: r for r in archive["members"]}
        seen = set()
        with tarfile.open(path, "r:gz") as tar:
            for member in tar:
                name = PurePosixPath(member.name)
                if name.is_absolute() or ".." in name.parts or not member.isfile():
                    raise ValueError(f"Unexpected archive entry: {member.name}")
                if member.name not in expected or member.name in seen:
                    raise ValueError(f"Unindexed or repeated archive entry: {member.name}")
                seen.add(member.name)
                data = tar.extractfile(member).read()
                record = expected[member.name]
                if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
                    raise ValueError(f"Member checksum/size mismatch: {member.name}")
                if not args.verify_only:
                    target = args.output / member.name
                    output_root = args.output.resolve()
                    try:
                        target.resolve().relative_to(output_root)
                    except ValueError:
                        raise ValueError(f"Output path leaves destination directory: {target}")
                    if target.exists() and (not target.is_file() or digest_file(target) != record["sha256"]):
                        raise FileExistsError(f"Existing different file; use a new --output directory: {target}")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                total += 1
        if seen != set(expected):
            raise ValueError(f"Missing indexed entries: {set(expected) - seen}")
        print(f"Verified {archive['file']}: {len(seen)} files")
    print(f"{'Verified' if args.verify_only else 'Verified and extracted'} {total} files" +
          ("" if args.verify_only else f" into {args.output.resolve()}"))


if __name__ == "__main__":
    main()
