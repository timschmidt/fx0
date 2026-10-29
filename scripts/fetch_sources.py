#!/usr/bin/env python3
"""Fetch or verify the pinned public source subset used for Fx0 DTB checks."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def blob_hash(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def safe_path(cache, source, relative):
    path = PurePosixPath(relative)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", source) or path.is_absolute() or ".." in path.parts or ".git" in path.parts:
        raise ValueError("Unsafe source path in manifest")
    target = cache / source / relative
    if not target.parent.resolve().is_relative_to((cache / source).resolve()):
        raise ValueError("Source path escapes its cache")
    return target


def verify_item(path, item):
    if "symlink" in item:
        if not path.is_symlink():
            raise ValueError(f"Expected upstream symlink: {item['path']}")
        data = str(path.readlink()).encode()
    else:
        if path.is_symlink():
            raise ValueError(f"Unexpected source symlink: {item['path']}")
        data = path.read_bytes()
    if blob_hash(data) != item["git_blob"]:
        raise ValueError(f"Source hash mismatch: {item['source']}/{item['path']}")


def fetch(cache, manifest, verify_only=False):
    if manifest.get("schema") != 1:
        raise ValueError("Unsupported source manifest")
    # Materialize target files before their upstream symlinks.
    files = sorted(manifest["files"], key=lambda item: "symlink" in item)
    for item in files:
        source = manifest["sources"][item["source"]]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source["repository"]):
            raise ValueError("Invalid source repository")
        if not re.fullmatch(r"[0-9a-f]{40}", source["commit"]):
            raise ValueError("Source revision must be a full commit")
        path = safe_path(cache, item["source"], item["path"])
        if verify_only or path.exists() or path.is_symlink():
            verify_item(path, item)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if "symlink" in item:
            target = item["symlink"]
            resolved = (path.parent / target).resolve()
            if PurePosixPath(target).is_absolute() or not resolved.is_relative_to((cache / item["source"]).resolve()):
                raise ValueError("Upstream symlink escapes its source tree")
            if blob_hash(target.encode()) != item["git_blob"]:
                raise ValueError("Upstream symlink hash mismatch")
            path.symlink_to(target)
        else:
            url = f"https://raw.githubusercontent.com/{source['repository']}/{source['commit']}/{item['path']}"
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read(4 * 1024 * 1024 + 1)
            if len(data) > 4 * 1024 * 1024 or blob_hash(data) != item["git_blob"]:
                raise ValueError(f"Downloaded source failed hash verification: {item['path']}")
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
                temporary.write(data)
                partial = Path(temporary.name)
            partial.replace(path)
        verify_item(path, item)
    return len(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / "local/source-cache")
    parser.add_argument("--verify-only", action="store_true", help="Verify existing files without network access")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "manifests/source-files.json").read_text())
    count = fetch(args.cache.resolve(), manifest, args.verify_only)
    print(f"Verified {count} files and upstream symlinks at pinned Git blob hashes")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(f"fetch-sources: {error}", file=sys.stderr)
        sys.exit(1)
