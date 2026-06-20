#!/usr/bin/env python3
"""Summarize Chinese personal ledger CSV/JSON files."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any


CATEGORY_ALIASES = {"健康医疗": "医疗健康"}
SUBCATEGORY_ALIASES = {"停车": "停车费", "高速费用": "高速费", "酒水饮料": "饮料酒水"}
LEGACY_PAIR_ALIASES = {("购物消费", "饮料酒水"): ("食品餐饮", "饮料酒水")}


def load_file(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return {"records": list(csv.DictReader(f)), "asset_snapshots": [], "repayment_reminders": []}
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return {"records": data, "asset_snapshots": [], "repayment_reminders": []}
        if isinstance(data, dict):
            return {
                "records": data.get("records", data.get("transactions", [])),
                "asset_snapshots": data.get("asset_snapshots", []),
                "repayment_reminders": data.get("repayment_reminders", []),
            }
    raise SystemExit(f"Unsupported file type: {path}")


def money(value: Any) -> Decimal:
    return Decimal(str(value or "0"))


def fmt(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def normalize(category: str, subcategory: str) -> tuple[str, str]:
    if (category, subcategory) in LEGACY_PAIR_ALIASES:
        category, subcategory = LEGACY_PAIR_ALIASES[(category, subcategory)]
    category = CATEGORY_ALIASES.get(category, category)
    subcategory = SUBCATEGORY_ALIASES.get(subcategory, subcategory)
    return category, subcategory


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Chinese personal ledger CSV/JSON files.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--month", help="Filter by YYYY-MM.")
    args = parser.parse_args()

    data = load_file(args.file)
    rows = data["records"]
    if args.month:
        rows = [r for r in rows if str(r.get("时间", "")).startswith(args.month)]

    totals: dict[str, Decimal] = defaultdict(Decimal)
    by_category: dict[str, Decimal] = defaultdict(Decimal)
    by_subcategory: dict[str, Decimal] = defaultdict(Decimal)
    repayment_by_account: dict[str, Decimal] = defaultdict(Decimal)
    by_account: dict[str, Decimal] = defaultdict(Decimal)

    for row in rows:
        amount = money(row.get("金额"))
        tx_type = str(row.get("收支类型", "")).strip()
        account = str(row.get("账户", "未填账户")).strip() or "未填账户"
        category = str(row.get("类别", "未分类")).strip() or "未分类"
        subcategory = str(row.get("子类", "未分类")).strip() or "未分类"
        category, subcategory = normalize(category, subcategory)

        display_amount = abs(amount) if tx_type in {"支出", "还款", "转账"} else amount
        totals[tx_type] += display_amount
        by_account[f"{account}/{tx_type}"] += amount
        if tx_type == "支出":
            by_category[category] += display_amount
            by_subcategory[f"{category}/{subcategory}"] += display_amount
        elif tx_type == "还款":
            repayment_by_account[account] += display_amount

    income = totals["收入"]
    expense = totals["支出"]
    repayment = totals["还款"]
    transfer = totals["转账"]

    print(f"# 记账统计: {args.file.name}")
    if args.month:
        print(f"月份: {args.month}")
    print()
    print(f"- 记录数: {len(rows)}")
    print(f"- 收入: {fmt(income)}")
    print(f"- 支出: {fmt(expense)}")
    print(f"- 还款: {fmt(repayment)}")
    print(f"- 转账: {fmt(transfer)}")
    print(f"- 结余(不含还款): {fmt(income - expense)}")
    print(f"- 现金流结余: {fmt(income - expense - repayment)}")

    if by_category:
        print("\n## 支出按类别")
        for name, value in sorted(by_category.items(), key=lambda item: item[1], reverse=True):
            print(f"- {name}: {fmt(value)}")

    if by_subcategory:
        print("\n## 支出Top子类")
        for name, value in sorted(by_subcategory.items(), key=lambda item: item[1], reverse=True)[:10]:
            print(f"- {name}: {fmt(value)}")

    if repayment_by_account:
        print("\n## 还款按账户")
        for name, value in sorted(repayment_by_account.items(), key=lambda item: item[1], reverse=True):
            print(f"- {name}: {fmt(value)}")

    if data["asset_snapshots"]:
        print("\n## 资产快照")
        asset_total = sum((money(r.get("金额")) for r in data["asset_snapshots"]), Decimal("0"))
        print(f"- 合计: {fmt(asset_total)}")

    if data["repayment_reminders"]:
        print("\n## 还款提醒")
        for row in sorted(data["repayment_reminders"], key=lambda r: str(r.get("时间", ""))):
            print(f"- {row.get('时间')} {row.get('账户')}: {fmt(money(row.get('金额')))} {row.get('状态', '')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
