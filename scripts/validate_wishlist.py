#!/usr/bin/env python3
"""Validate and list wishlist items without financial inference."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def load_items(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items", []), list):
        return data["items"]
    raise SystemExit(f"Unsupported wishlist shape: {path}")


def validate(items: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for index, item in enumerate(items, 1):
        if not str(item.get("名称", "")).strip():
            errors.append(f"wishlist[{index}]: missing 名称")
        if "预计金额" in item and str(item["预计金额"]).strip():
            try:
                if Decimal(str(item["预计金额"])) <= 0:
                    errors.append(f"wishlist[{index}]: 预计金额 must be positive")
            except (InvalidOperation, ValueError):
                errors.append(f"wishlist[{index}]: 预计金额 must be numeric")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and list wishlist items without price or financial inference.")
    parser.add_argument("wishlist", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    items = load_items(args.wishlist)
    errors = validate(items)
    if errors:
        print(f"INVALID: {args.wishlist}")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"OK: {args.wishlist}")
    print(f"items: {len(items)}")
    if not args.validate_only:
        for item in items:
            print(f"- {item.get('状态', '想买')} {item.get('名称', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
