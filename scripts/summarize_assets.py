#!/usr/bin/env python3
"""Show observed and inferred asset snapshots without mixing credit schedules."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any


LIABILITY_ACCOUNTS = {"白条", "花呗", "美团月付", "抖音月付"}


def money(value: Any) -> Decimal:
    return Decimal(str(value or "0"))


def fmt(value: Any) -> str:
    return f"{money(value).quantize(Decimal('0.01'))}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Show observed and inferred asset snapshots.")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()

    data = json.loads(args.file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Assets file must be a JSON object")

    latest: dict[str, dict[str, Any]] = {}
    for row in data.get("asset_snapshots", []):
        account = str(row.get("账户", "")).strip()
        if account and str(row.get("时间", "")) >= str(latest.get(account, {}).get("时间", "")):
            latest[account] = row

    print("# 真实资产快照")
    for account, row in sorted(latest.items()):
        print(f"- {account}: {fmt(row.get('余额', row.get('金额')))} @ {row.get('时间', '')}")

    inferred = data.get("inferred_snapshot")
    if isinstance(inferred, dict):
        print("\n# 推理资产快照")
        print(f"- 时间: {inferred.get('时间', '')}")
        print(f"- 总资产: {fmt(inferred.get('总资产'))}")
        print(f"- 总负债: {fmt(inferred.get('总负债'))}")
        print(f"- 净资产: {fmt(inferred.get('净资产'))}")
        unknown = inferred.get("未建立基线账户", [])
        if unknown:
            print(f"- 未建立基线账户: {', '.join(map(str, unknown))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
