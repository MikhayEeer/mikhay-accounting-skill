#!/usr/bin/env python3
"""Validate Chinese personal ledger CSV/JSON files."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


TYPES = {"支出", "收入", "还款", "转账"}
ACCOUNTS = {"白条", "花呗", "美团月付", "抖音月付", "建设银行", "工商银行", "招商银行", "微信钱包", "支付宝", "美团"}
REQUIRED_RECORD = ["时间", "收支类型", "金额", "类别", "子类", "账户", "备注"]

CATEGORY_MAP = {
    "食品餐饮": {"早餐", "午餐", "晚餐", "正餐", "外卖", "快餐", "小吃", "夜宵", "零食", "休闲零食", "水果", "生鲜", "饮料", "饮料酒水", "聚餐", "请客吃饭"},
    "出行交通": {"打车", "公交地铁", "加油", "充电", "火车", "飞机", "租车", "停车费", "高速费", "通行费", "酒店住宿", "景区门票"},
    "购物消费": {"服饰运动", "数码", "手机数码", "日常家居", "家居用品", "日用百货", "礼品", "纪念品", "祭祀用品", "虚拟充值", "外汇", "交通工具", "邮寄"},
    "服饰美容": {"服装"},
    "居家生活": {"住宿", "水费", "洗护", "政务", "邮寄"},
    "生活服务": {"超市", "快递", "清洁用品", "燃气费"},
    "医疗健康": {"挂号", "门诊", "检查费", "药品", "买药", "医院看病"},
    "休闲娱乐": {"旅游度假", "棋牌桌游", "酒吧", "游戏", "游戏充值", "游戏购买"},
    "收入": {"工资", "报销", "补贴", "其他"},
    "还款": {"白条还款", "月付还款"},
    "转账": {"个人转账"},
}

CATEGORY_ALIASES = {"健康医疗": "医疗健康"}
SUBCATEGORY_ALIASES = {"停车": "停车费", "高速费用": "高速费", "酒水饮料": "饮料酒水"}
LEGACY_PAIR_ALIASES = {
    ("购物消费", "饮料酒水"): ("食品餐饮", "饮料酒水"),
}


def is_datetime(value: Any) -> bool:
    try:
        datetime.fromisoformat(str(value))
        return True
    except ValueError:
        return False


def decimal_value(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


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


def normalize_pair(category: str, subcategory: str) -> tuple[str, str, list[str]]:
    warnings: list[str] = []
    original = (category, subcategory)
    if original in LEGACY_PAIR_ALIASES:
        category, subcategory = LEGACY_PAIR_ALIASES[original]
        warnings.append(f"legacy pair {original[0]}/{original[1]} -> {category}/{subcategory}")
    if category in CATEGORY_ALIASES:
        warnings.append(f"category alias {category} -> {CATEGORY_ALIASES[category]}")
        category = CATEGORY_ALIASES[category]
    if subcategory in SUBCATEGORY_ALIASES:
        warnings.append(f"subcategory alias {subcategory} -> {SUBCATEGORY_ALIASES[subcategory]}")
        subcategory = SUBCATEGORY_ALIASES[subcategory]
    return category, subcategory, warnings


def validate_records(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for i, row in enumerate(rows, 1):
        prefix = f"record[{i}]"
        for field in REQUIRED_RECORD:
            if str(row.get(field, "")).strip() == "":
                errors.append(f"{prefix}: missing {field}")
        tx_type = str(row.get("收支类型", "")).strip()
        amount = decimal_value(row.get("金额"))
        account = str(row.get("账户", "")).strip()
        category = str(row.get("类别", "")).strip()
        subcategory = str(row.get("子类", "")).strip()
        norm_category, norm_subcategory, pair_warnings = normalize_pair(category, subcategory)
        warnings.extend(f"{prefix}: {w}" for w in pair_warnings)

        if not is_datetime(row.get("时间")):
            errors.append(f"{prefix}: invalid 时间")
        if tx_type not in TYPES:
            errors.append(f"{prefix}: invalid 收支类型 {tx_type!r}")
        if amount is None:
            errors.append(f"{prefix}: 金额 must be numeric")
        elif amount == 0:
            errors.append(f"{prefix}: 金额 cannot be zero")
        elif tx_type == "支出" and amount > 0:
            warnings.append(f"{prefix}: 支出 usually uses a negative 金额")
        elif tx_type in {"收入", "还款", "转账"} and amount < 0:
            warnings.append(f"{prefix}: {tx_type} usually uses a positive 金额")
        if account not in ACCOUNTS:
            errors.append(f"{prefix}: invalid 账户 {account!r}")
        if norm_category not in CATEGORY_MAP:
            errors.append(f"{prefix}: invalid 类别 {category!r}")
        elif norm_subcategory not in CATEGORY_MAP[norm_category]:
            errors.append(f"{prefix}: invalid 子类 {subcategory!r} for 类别 {category!r}")

        expected_category = {"收入": "收入", "还款": "还款", "转账": "转账"}.get(tx_type)
        if expected_category and norm_category != expected_category:
            errors.append(f"{prefix}: 收支类型 {tx_type} should use 类别 {expected_category}")
        if tx_type == "支出" and norm_category in {"收入", "还款", "转账"}:
            errors.append(f"{prefix}: 支出 cannot use 类别 {norm_category}")
    return errors, warnings


def validate_assets(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for i, row in enumerate(rows, 1):
        prefix = f"asset_snapshot[{i}]"
        for field in ["时间", "账户", "金额"]:
            if str(row.get(field, "")).strip() == "":
                errors.append(f"{prefix}: missing {field}")
        if not is_datetime(row.get("时间")):
            errors.append(f"{prefix}: invalid 时间")
        if str(row.get("账户", "")).strip() not in ACCOUNTS:
            errors.append(f"{prefix}: invalid 账户")
        try:
            Decimal(str(row.get("金额")))
        except (InvalidOperation, ValueError):
            errors.append(f"{prefix}: 金额 must be numeric")
    return errors, warnings


def validate_reminders(rows: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for i, row in enumerate(rows, 1):
        prefix = f"repayment_reminder[{i}]"
        for field in ["时间", "账户", "金额", "状态"]:
            if str(row.get(field, "")).strip() == "":
                errors.append(f"{prefix}: missing {field}")
        if not is_datetime(row.get("时间")):
            errors.append(f"{prefix}: invalid 时间")
        if str(row.get("账户", "")).strip() not in ACCOUNTS:
            errors.append(f"{prefix}: invalid 账户")
        amount = decimal_value(row.get("金额"))
        if amount is None or amount <= 0:
            errors.append(f"{prefix}: 金额 must be positive")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Chinese personal ledger CSV/JSON files.")
    parser.add_argument("file", type=Path)
    args = parser.parse_args()

    data = load_file(args.file)
    errors, warnings = validate_records(data["records"])
    asset_errors, asset_warnings = validate_assets(data["asset_snapshots"])
    reminder_errors, reminder_warnings = validate_reminders(data["repayment_reminders"])
    errors.extend(asset_errors)
    errors.extend(reminder_errors)
    warnings.extend(asset_warnings)
    warnings.extend(reminder_warnings)

    if errors:
        print(f"INVALID: {args.file}")
        for error in errors:
            print(f"- {error}")
        if warnings:
            print("WARNINGS:")
            for warning in warnings[:50]:
                print(f"- {warning}")
            if len(warnings) > 50:
                print(f"- ... {len(warnings) - 50} more warnings")
        return 1

    print(f"OK: {args.file}")
    print(f"records: {len(data['records'])}")
    print(f"asset_snapshots: {len(data['asset_snapshots'])}")
    print(f"repayment_reminders: {len(data['repayment_reminders'])}")
    if warnings:
        print(f"warnings: {len(warnings)}")
        for warning in warnings[:20]:
            print(f"- {warning}")
        if len(warnings) > 20:
            print(f"- ... {len(warnings) - 20} more warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
