#!/usr/bin/env python3
"""Build a versioned, allowlisted skill installation ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path


SKILL_NAME = "mikhay-accounting-skill"
INCLUDE_DIRS = {"agents", "assets", "scripts"}
INCLUDE_FILES = {
    ".gitignore",
    "VERSION",
    "SKILL.md",
    "schema.md",
    "categories.md",
    "accounts.md",
    "credit.md",
    "wishlist.md",
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
    "packages",
    "tests",
    "examples",
}


def should_include(path: Path) -> bool:
    if set(path.parts) & EXCLUDE_PARTS or path.suffix == ".pyc":
        return False
    if len(path.parts) == 1:
        return path.name in INCLUDE_FILES
    return path.parts[0] in INCLUDE_DIRS


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def collect_files(root: Path) -> list[Path]:
    return [
        path.relative_to(root)
        for path in sorted(root.rglob("*"))
        if path.is_file() and should_include(path.relative_to(root))
    ]


def build_package(root: Path, output: Path) -> Path:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    files = collect_files(root)
    manifest = {
        "name": SKILL_NAME,
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": [
            {"path": path.as_posix(), "sha256": digest(root / path)}
            for path in files
        ],
    }

    output.mkdir(parents=True, exist_ok=True)
    target = output / f"{SKILL_NAME}-v{version}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(root / path, arcname=f"{SKILL_NAME}/{path.as_posix()}")
        archive.writestr(
            f"{SKILL_NAME}/MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the versioned skill installation ZIP.")
    parser.add_argument("--output", default="packages", type=Path)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    target = build_package(root, (root / args.output).resolve())
    print(f"package: {target}")
    print(f"sha256: {digest(target)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
