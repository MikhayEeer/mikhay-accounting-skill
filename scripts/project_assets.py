#!/usr/bin/env python3
"""Rebuild inferred asset balances from observed snapshots and later ledger items."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


LIABILITY_ACCOUNTS = {"白条", "花呗", "美团月付", "抖音月付"}


def parse_time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).strip())
    except ValueError:
        return None


def money(value: Any) -> Decimal:
    return Decimal(str(value or "0"))


def json_money(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_records(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        data = load_json(path)
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = data.get("records", data.get("transactions", []))
        else:
            raise SystemExit(f"Unsupported ledger shape: {path}")
        records.extend(row for row in rows if isinstance(row, dict))
    return records


def target_account(row: dict[str, Any]) -> str:
    direct = str(row.get("target_account", "")).strip()
    if direct:
        return direct
    text = f"{row.get('note', '')} {row.get('备注', '')}"
    match = re.search(r"(?:target_account|目标账户|还款账户)\s*[:=：]?\s*([^\s;；,，]+)", text)
    return match.group(1) if match else ""


def project(
    asset_data: dict[str, Any],
    records: list[dict[str, Any]],
    as_of: datetime | None,
) -> dict[str, Any]:
    latest: dict[str, dict[str, Any]] = {}
    latest_time: dict[str, datetime] = {}
    for row in asset_data.get("asset_snapshots", []):
        account = str(row.get("账户", "")).strip()
        stamp = parse_time(row.get("时间"))
        if not account or stamp is None or (as_of and stamp > as_of):
            continue
        if account not in latest_time or stamp >= latest_time[account]:
            latest[account] = row
            latest_time[account] = stamp

    balances: dict[str, Decimal] = {}
    kinds: dict[str, str] = {}
    for account, row in latest.items():
        balances[account] = money(row.get("余额", row.get("金额", 0)))
        explicit = str(row.get("账户类型", "")).strip()
        kinds[account] = explicit or ("负债" if account in LIABILITY_ACCOUNTS else "资产")

    unknown: set[str] = set()
    applied: set[int] = set()
    valid_records: list[tuple[datetime, int, dict[str, Any]]] = []
    for index, row in enumerate(records):
        stamp = parse_time(row.get("时间"))
        if stamp is not None and (as_of is None or stamp <= as_of):
            valid_records.append((stamp, index, row))
    valid_records.sort(key=lambda item: (item[0], item[1]))

    def apply(account: str, delta: Decimal, stamp: datetime, record_index: int) -> None:
        if not account:
            return
        if account not in balances:
            unknown.add(account)
            return
        if stamp > latest_time[account]:
            balances[account] += delta
            applied.add(record_index)

    for stamp, record_index, row in valid_records:
        account = str(row.get("账户", "")).strip()
        tx_type = str(row.get("收支类型", "")).strip()
        amount = abs(money(row.get("金额")))
        target = target_account(row)
        if tx_type == "支出":
            apply(account, -amount, stamp, record_index)
        elif tx_type == "收入":
            apply(account, amount, stamp, record_index)
        elif tx_type == "还款":
            apply(account, -amount, stamp, record_index)
            apply(target, amount, stamp, record_index)
        elif tx_type == "转账":
            apply(account, -amount, stamp, record_index)
            apply(target, amount, stamp, record_index)

    rows = []
    total_assets = Decimal("0")
    total_liabilities = Decimal("0")
    for account in sorted(balances):
        balance = balances[account]
        kind = kinds[account]
        rows.append(
            {
                "账户": account,
                "账户类型": kind,
                "余额": json_money(balance),
                "基准快照时间": latest_time[account].isoformat(sep=" ", timespec="minutes"),
            }
        )
        if kind == "负债":
            total_liabilities += max(-balance, Decimal("0"))
        else:
            total_assets += balance

    candidates = [*latest_time.values(), *(stamp for stamp, _, _ in valid_records)]
    inferred_time = as_of or (max(candidates) if candidates else datetime.now())
    return {
        "时间": inferred_time.isoformat(sep=" ", timespec="minutes"),
        "类型": "推理",
        "账户余额": rows,
        "总资产": json_money(total_assets),
        "总负债": json_money(total_liabilities),
        "净资产": json_money(total_assets - total_liabilities),
        "应用记账数": len(applied),
        "未建立基线账户": sorted(unknown),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild inferred asset snapshot.")
    parser.add_argument("assets", type=Path)
    parser.add_argument("ledger", nargs="*", type=Path)
    parser.add_argument("--as-of", help="Inference cutoff in ISO date or datetime format.")
    parser.add_argument("--write", action="store_true", help="Replace inferred_snapshot in the asset file.")
    args = parser.parse_args()

    asset_data = load_json(args.assets)
    if not isinstance(asset_data, dict):
        raise SystemExit("Assets file must be a JSON object")
    cutoff = parse_time(args.as_of) if args.as_of else None
    if args.as_of and cutoff is None:
        raise SystemExit("--as-of must be an ISO date or datetime")

    inferred = project(asset_data, load_records(args.ledger), cutoff)
    if args.write:
        asset_data["inferred_snapshot"] = inferred
        args.assets.write_text(json.dumps(asset_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"updated {args.assets}")
    print(json.dumps(inferred, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
