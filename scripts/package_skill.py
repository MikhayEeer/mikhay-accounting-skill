#!/usr/bin/env python3
"""Create portable handoff archives for this skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


SKILL_NAME = "mikhay-accounting-skill"
INCLUDE_DIRS = {"agents", "examples", "scripts"}
INCLUDE_FILES = {
    ".gitignore",
    "README.md",
    "HANDOFF.md",
    "SKILL.md",
    "schema.md",
    "categories.md",
    "accounts.md",
    "import_rules.md",
}
EXCLUDE_PARTS = {
    ".git",
    ".claude",
    ".codex",
    "__pycache__",
    "data",
    "raw",
    "exports",
    "private",
    "real",
    "reports",
    "dist",
}


def should_include(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_PARTS:
        return False
    if path.name.endswith(".pyc"):
        return False
    if len(path.parts) == 1:
        return path.name in INCLUDE_FILES
    return path.parts[0] in INCLUDE_DIRS


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_files(root: Path) -> list[Path]:
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root)
            if should_include(rel):
                files.append(rel)
    return files


def write_manifest(root: Path, files: list[Path], output: Path) -> Path:
    manifest = {
        "name": SKILL_NAME,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": [
            {"path": str(path).replace("\\", "/"), "sha256": digest(root / path)}
            for path in files
        ],
    }
    manifest_path = output / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def make_tar(root: Path, files: list[Path], manifest: Path, output: Path) -> Path:
    target = output / f"{SKILL_NAME}.tar.gz"
    with tarfile.open(target, "w:gz") as tar:
        for rel in files:
            tar.add(root / rel, arcname=f"{SKILL_NAME}/{rel.as_posix()}")
        tar.add(manifest, arcname=f"{SKILL_NAME}/MANIFEST.json")
    return target


def make_zip(root: Path, files: list[Path], manifest: Path, output: Path) -> Path:
    target = output / f"{SKILL_NAME}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for rel in files:
            archive.write(root / rel, arcname=f"{SKILL_NAME}/{rel.as_posix()}")
        archive.write(manifest, arcname=f"{SKILL_NAME}/MANIFEST.json")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Package this skill for agent handoff.")
    parser.add_argument("--output", default="dist", help="Output directory. Default: dist")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    output = (root / args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)

    files = collect_files(root)
    manifest = write_manifest(root, files, output)
    tar_path = make_tar(root, files, manifest, output)
    zip_path = make_zip(root, files, manifest, output)

    print(f"files: {len(files)}")
    print(f"tar: {tar_path}")
    print(f"zip: {zip_path}")
    print(f"manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
