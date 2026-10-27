#!/usr/bin/env python3
"""Restore separately distributed runtime assets and check their inventory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8*1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source", type=Path, help="Existing complete application directory")
    source.add_argument("--hf-repo", help="HF model repo with the paths in assets/manifest.json")
    source.add_argument("--check", action="store_true", help="Check existing assets without copying")
    parser.add_argument("--revision", default="main", help="HF model repository revision")
    parser.add_argument("--verify", action="store_true", help="Read all assets and verify SHA256 (about 53 GiB)")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "assets/manifest.json").read_text())
    for entry in manifest["files"]:
        path = Path(entry["path"])
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Invalid asset path")
    if args.hf_repo:
        from huggingface_hub import snapshot_download
        snapshot_download(args.hf_repo, repo_type="model", revision=args.revision,
                          allow_patterns=[e["path"] for e in manifest["files"] if not e.get("bundled_in_git")],
                          local_dir=str(ROOT))
    elif args.source:
        for entry in manifest["files"]:
            target = ROOT / entry["path"]
            if target.exists():
                continue
            origin = args.source / entry["path"]
            if not origin.is_file():
                if entry.get("optional"):
                    continue
                raise FileNotFoundError(origin)
            if origin.stat().st_size != entry["bytes"]:
                raise ValueError("Source asset size mismatch: "+entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            pending = target.with_name(target.name+".copying")
            shutil.copy2(origin, pending)
            os.replace(pending, target)
            print("RESTORED", entry["path"], flush=True)
    checked, problems = 0, []
    for entry in manifest["files"]:
        path = ROOT / entry["path"]
        if not path.is_file():
            if not entry.get("optional"):
                problems.append("missing: "+entry["path"])
            continue
        if path.stat().st_size != entry["bytes"]:
            problems.append("size mismatch: "+entry["path"])
        elif args.verify and digest(path) != entry["sha256"]:
            problems.append("SHA256 mismatch: "+entry["path"])
        checked += 1
    if problems:
        raise SystemExit("\n".join(problems))
    print(f"PASS: {checked} assets; SHA256 {'verified' if args.verify else 'not requested'}")


if __name__ == "__main__":
    main()
