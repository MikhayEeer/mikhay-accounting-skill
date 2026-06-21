#!/usr/bin/env python3
"""Summarize assets, liabilities, installments, and repayment reminders."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any


ASSET_ACCOUNTS = {"建设银行", "工商银行", "招商银行", "微信钱包", "支付宝", "美团"}
LIABILITY_ACCOUNTS = {"白条", "花呗", "美团月付", "抖音月付"}


def money(value: Any) -> Decimal:
    return Decimal(str(value or "0"))


def fmt(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def load_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {
            "records": data,
            "asset_snapshots": [],
            "credit_accounts": [],
            "installment_plans": [],
            "repayment_reminders": [],
        }
    if isinstance(data, dict):
        return {
            "records": data.get("records", data.get("transactions", [])),
            "asset_snapshots": data.get("asset_snapshots", []),
            "credit_accounts": data.get("credit_accounts", []),
            "installment_plans": data.get("installment_plans", []),
            "repayment_reminders": data.get("repayment_reminders", []),
        }
    raise SystemExit(f"Unsupported JSON shape: {path}")


def account_kind(account: str, explicit: str = "") -> str:
    if explicit in {"资产", "负债"}:
        return explicit
    if account in LIABILITY_ACCOUNTS:
        return "负债"
    return "资产"


def latest_snapshots(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        account = str(row.get("账户", "")).strip()
        if not account:
            continue
        current_time = str(row.get("时间", ""))
        old_time = str(latest.get(account, {}).get("时间", ""))
        if account not in latest or current_time >= old_time:
            latest[account] = row
    return latest


def parse_target_account(note: str) -> str:
    match = re.search(r"(?:target_account|目标账户|还款账户)\s*[:=：]?\s*([^\s;；,，]+)", note)
    return match.group(1) if match else ""


def ledger_projection(records: list[dict[str, Any]]) -> dict[str, Decimal]:
    balances: dict[str, Decimal] = defaultdict(Decimal)
    for row in records:
        account = str(row.get("账户", "")).strip()
        if not account:
            continue
        tx_type = str(row.get("收支类型", "")).strip()
        amount = money(row.get("金额"))
        note = f"{row.get('note', '')} {row.get('备注', '')}"
        if tx_type == "收入":
            balances[account] += abs(amount)
        elif tx_type == "支出":
            balances[account] -= abs(amount)
        elif tx_type == "还款":
            balances[account] -= abs(amount)
            target = parse_target_account(note)
            if target:
                balances[target] += abs(amount)
        elif tx_type == "转账":
            target = parse_target_account(note)
            if target:
                balances[account] -= abs(amount)
                balances[target] += abs(amount)
    return balances


def parse_due(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize account assets, liabilities, installments, and reminders.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--as-of", help="Date for reminder status, YYYY-MM-DD. Default: today.")
    args = parser.parse_args()

    data = load_file(args.file)
    as_of = parse_due(args.as_of) if args.as_of else date.today()
    if as_of is None:
        raise SystemExit("--as-of must be YYYY-MM-DD")

    snapshots = latest_snapshots(data["asset_snapshots"])
    asset_balances: dict[str, Decimal] = {}
    liability_balances: dict[str, Decimal] = {}

    print(f"# 资产统计: {args.file.name}")
    print(f"日期: {as_of.isoformat()}")

    if snapshots:
        print("\n## 各账户余额")
        for account, row in sorted(snapshots.items()):
            amount = money(row.get("金额"))
            kind = account_kind(account, str(row.get("账户类型", "")))
            if kind == "负债":
                debt = abs(amount)
                liability_balances[account] = debt
                print(f"- {account}: -{fmt(debt)}")
            else:
                asset_balances[account] = amount
                print(f"- {account}: {fmt(amount)}")

    if data["credit_accounts"]:
        print("\n## 信贷账户")
        for row in sorted(data["credit_accounts"], key=lambda r: str(r.get("账户", ""))):
            account = str(row.get("账户", ""))
            debt = abs(money(row.get("欠款")))
            liability_balances[account] = debt
            limit = row.get("额度", "")
            available = row.get("可用额度", "")
            print(f"- {account}: 欠款 {fmt(debt)}, 额度 {limit}, 可用 {available}")

    asset_total = sum(asset_balances.values(), Decimal("0"))
    liability_total = sum(liability_balances.values(), Decimal("0"))

    print("\n## 汇总")
    print(f"- 总资产: {fmt(asset_total)}")
    print(f"- 总负债: {fmt(liability_total)}")
    print(f"- 净资产: {fmt(asset_total - liability_total)}")
    print(f"- 负资产: {fmt(liability_total)}")

    if data["installment_plans"]:
        print("\n## 分期计划")
        for row in sorted(data["installment_plans"], key=lambda r: str(r.get("下一还款日", ""))):
            principal = money(row.get("本金"))
            paid = int(row.get("已还期数", 0) or 0)
            total = int(row.get("总期数", 0) or 0)
            per_period = money(row.get("每期金额"))
            remaining_periods = max(total - paid, 0)
            remaining_amount = per_period * remaining_periods if per_period else principal
            print(f"- {row.get('id', '')} {row.get('账户', '')}: 剩余 {remaining_periods}/{total} 期, 待还 {fmt(remaining_amount)}, 下一还款日 {row.get('下一还款日', '')}")

    if data["repayment_reminders"]:
        print("\n## 还款提醒")
        for row in sorted(data["repayment_reminders"], key=lambda r: str(r.get("时间", ""))):
            due = parse_due(str(row.get("时间", "")))
            status = str(row.get("状态", ""))
            overdue = due is not None and due < as_of and status not in {"已还", "paid", "skipped"}
            prefix = "逾期" if overdue else status
            print(f"- {row.get('时间')} {row.get('账户')}: {fmt(money(row.get('金额')))} {prefix}")

    projection = ledger_projection(data["records"])
    if snapshots and projection:
        print("\n## 账本推演差额")
        for account in sorted(set(snapshots) | set(projection)):
            snapshot_amount = money(snapshots.get(account, {}).get("金额"))
            projected_amount = projection.get(account, Decimal("0"))
            diff = snapshot_amount - projected_amount
            if diff:
                print(f"- {account}: 快照 {fmt(snapshot_amount)}, 账本推演 {fmt(projected_amount)}, 差额 {fmt(diff)}")
        print("\n账本推演从 0 开始，主要用于发现净变动差额。")
        print("资产快照与账本推演不一致时，先询问用户是否创建调整记账项。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
