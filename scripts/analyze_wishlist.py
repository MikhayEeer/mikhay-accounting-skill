#!/usr/bin/env python3
"""Analyze purchase wishlist pressure and priority."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = ["名称", "预计金额", "类型", "优先级", "状态"]
PRIORITIES = {"P0", "P1", "P2", "P3"}
STATUSES = {"想买", "观望", "计划购买", "已购买", "放弃"}
ACTIVE_STATUSES = {"想买", "观望", "计划购买"}
LIABILITY_ACCOUNTS = {"白条", "花呗", "美团月付", "抖音月付"}
NEED_TYPES = {"健康", "医疗", "工作", "学习", "必需", "维修"}


def decimal_value(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def money(value: Any) -> Decimal:
    return decimal_value(value) or Decimal("0")


def fmt(value: Decimal | None) -> str:
    if value is None:
        return "未知"
    return f"{value.quantize(Decimal('0.01'))}"


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是", "可", "可以"}


def load_wishlist(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        items = data.get("items", data.get("wishlist", []))
        if isinstance(items, list):
            return items
    raise SystemExit(f"Unsupported wishlist JSON shape: {path}")


def load_ledger(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("records", data.get("transactions", []))
    raise SystemExit(f"Unsupported ledger file: {path}")


def validate_items(items: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for i, item in enumerate(items, 1):
        prefix = f"wishlist[{i}]"
        for field in REQUIRED_FIELDS:
            if str(item.get(field, "")).strip() == "":
                errors.append(f"{prefix}: missing {field}")
        amount = decimal_value(item.get("预计金额"))
        if amount is None or amount <= 0:
            errors.append(f"{prefix}: 预计金额 must be positive")
        priority = str(item.get("优先级", "")).strip()
        if priority and priority not in PRIORITIES:
            errors.append(f"{prefix}: 优先级 must be P0/P1/P2/P3")
        status = str(item.get("状态", "")).strip()
        if status and status not in STATUSES:
            errors.append(f"{prefix}: invalid 状态 {status!r}")
        target = str(item.get("目标日期", "")).strip()
        if target:
            try:
                datetime.fromisoformat(target)
            except ValueError:
                errors.append(f"{prefix}: invalid 目标日期")
        if status in {"已购买", "放弃"}:
            warnings.append(f"{prefix}: 状态={status}, analysis will skip buy recommendation")
    return errors, warnings


def ledger_context(paths: list[Path]) -> tuple[Decimal | None, Decimal, Decimal, Decimal]:
    if not paths:
        return None, Decimal("0"), Decimal("0"), Decimal("0")
    totals: dict[str, Decimal] = defaultdict(Decimal)
    for path in paths:
        for row in load_ledger(path):
            tx_type = str(row.get("收支类型", "")).strip()
            amount = abs(money(row.get("金额")))
            if tx_type:
                totals[tx_type] += amount
    income = totals["收入"]
    expense = totals["支出"]
    repayment = totals["还款"]
    return income - expense - repayment, income, expense, repayment


def asset_context(path: Path | None) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if path is None:
        return None, None, None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None, None, None
    assets: dict[str, Decimal] = {}
    liabilities: dict[str, Decimal] = {}
    for row in data.get("asset_snapshots", []):
        account = str(row.get("账户", "")).strip()
        amount = money(row.get("金额"))
        kind = str(row.get("账户类型", "")).strip()
        if kind == "负债" or account in LIABILITY_ACCOUNTS:
            liabilities[account] = abs(amount)
        else:
            assets[account] = amount
    for row in data.get("credit_accounts", []):
        account = str(row.get("账户", "")).strip()
        liabilities[account] = abs(money(row.get("欠款")))
    asset_total = sum(assets.values(), Decimal("0"))
    liability_total = sum(liabilities.values(), Decimal("0"))
    return asset_total - liability_total, asset_total, liability_total


def pressure(amount: Decimal, surplus: Decimal | None, net_assets: Decimal | None) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if surplus is None and net_assets is None:
        return "未知", ["缺少账本或资产上下文"]
    if surplus is not None:
        if surplus <= 0:
            reasons.append("月现金流为负或为零")
            return "高", reasons
        ratio = amount / surplus
        if ratio >= Decimal("1.5"):
            reasons.append("预计金额超过 1.5 个月现金流结余")
            return "高", reasons
        if ratio >= Decimal("0.5"):
            reasons.append("预计金额超过半个月现金流结余")
            return "中", reasons
    if net_assets is not None:
        if net_assets <= 0:
            reasons.append("净资产为负或为零")
            return "高", reasons
        ratio = amount / net_assets
        if ratio >= Decimal("0.20"):
            reasons.append("预计金额超过净资产 20%")
            return "高", reasons
        if ratio >= Decimal("0.10"):
            reasons.append("预计金额超过净资产 10%")
            return "中", reasons
    return "低", reasons or ["金额相对现金流和净资产可控"]


def suggested_priority(item: dict[str, Any], pressure_level: str) -> str:
    priority = str(item.get("优先级", "")).strip()
    item_type = str(item.get("类型", "")).strip()
    deferrable = truthy(item.get("可延期", False))
    if priority == "P0":
        return "P0"
    if priority == "P1" and (item_type in NEED_TYPES or not deferrable):
        return "P1"
    if item_type in NEED_TYPES and pressure_level != "高":
        return "P1"
    if item_type in NEED_TYPES:
        return "P2"
    if pressure_level == "高":
        return "P3" if deferrable else "P2"
    if pressure_level == "中":
        return priority if priority in {"P1", "P2"} else "P2"
    return priority or "P2"


def recommendation(item: dict[str, Any], pressure_level: str, priority: str) -> tuple[str, str]:
    status = str(item.get("状态", "")).strip()
    if status == "已购买":
        return "已购买", "无需重复购买"
    if status == "放弃":
        return "不建议", "已标记放弃"
    deferrable = truthy(item.get("可延期", False))
    if priority in {"P0", "P1"} and pressure_level != "高":
        return "建议", "必要性较高且压力可控"
    if pressure_level == "高":
        return "不建议" if deferrable else "观望", "经济压力较高"
    if pressure_level == "中":
        return "观望", "建议等现金流更充裕或降价"
    if deferrable and priority == "P3":
        return "观望", "可延期且优先级较低"
    return "建议", "压力较低"


def suggested_time(decision: str, pressure_level: str) -> str:
    if decision == "建议":
        return "现在或目标日期前"
    if pressure_level == "高":
        return "还款后或现金流转正后"
    if pressure_level == "中":
        return "下月或降价后"
    return "目标日期前"


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze purchase wishlist pressure and priority.")
    parser.add_argument("wishlist", type=Path)
    parser.add_argument("--ledger", action="append", type=Path, default=[], help="Ledger CSV/JSON file. Can be repeated.")
    parser.add_argument("--assets", type=Path, help="Assets JSON file.")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    items = load_wishlist(args.wishlist)
    errors, warnings = validate_items(items)
    if errors:
        print(f"INVALID: {args.wishlist}")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"OK: {args.wishlist}")
    print(f"items: {len(items)}")
    if warnings:
        print(f"warnings: {len(warnings)}")
        for warning in warnings[:20]:
            print(f"- {warning}")
    if args.validate_only:
        return 0

    surplus, income, expense, repayment = ledger_context(args.ledger)
    net_assets, asset_total, liability_total = asset_context(args.assets)

    print("\n## 财务上下文")
    print(f"- 月现金流结余: {fmt(surplus)}")
    print(f"- 收入/支出/还款: {fmt(income)} / {fmt(expense)} / {fmt(repayment)}")
    print(f"- 总资产/总负债/净资产: {fmt(asset_total)} / {fmt(liability_total)} / {fmt(net_assets)}")

    print("\n## 预购建议")
    active_items = [item for item in items if str(item.get("状态", "")).strip() in ACTIVE_STATUSES]
    rows = []
    for item in active_items:
        amount = money(item.get("预计金额"))
        pressure_level, reasons = pressure(amount, surplus, net_assets)
        priority = suggested_priority(item, pressure_level)
        decision, decision_reason = recommendation(item, pressure_level, priority)
        rows.append((priority, pressure_level, item, decision, decision_reason, reasons))

    pressure_order = {"高": 0, "中": 1, "低": 2, "未知": 3}
    rows.sort(key=lambda row: (row[0], pressure_order.get(row[1], 9), str(row[2].get("名称", ""))))
    for priority, pressure_level, item, decision, decision_reason, reasons in rows:
        name = item.get("名称", "")
        amount = money(item.get("预计金额"))
        when = suggested_time(decision, pressure_level)
        reason_text = "；".join([decision_reason, *reasons])
        print(f"- {name}: {fmt(amount)}，{decision}，压力={pressure_level}，优先级={priority}，建议时间={when}，原因={reason_text}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
