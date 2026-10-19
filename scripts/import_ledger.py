#!/usr/bin/env python3
"""Import CSV/XLSX bills into the standard Chinese ledger JSON format."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from ledgerlib import SCHEMA_VERSION, shard_key
from validate_ledger import (
    ACCOUNTS,
    CATEGORY_ALIASES,
    CATEGORY_MAP,
    LEGACY_PAIR_ALIASES,
    SUBCATEGORY_ALIASES,
    validate_records,
)


FIELDS = [
    "时间",
    "收支类型",
    "金额",
    "类别",
    "子类",
    "账户",
    "备注",
    "tags",
    "note",
    "id",
    "refund_of",
    "pairid",
    "target_account",
    "currency",
    "original_amount",
    "fx_rate",
    "cny_amount",
]
DEFAULT_ACCOUNT_BY_SOURCE = {
    "alipay": "支付宝",
    "wechat": "微信钱包",
    "meituan": "美团",
}
COLUMN_ALIASES = {
    "时间": ["时间", "交易时间", "交易创建时间", "付款时间", "日期", "交易日期", "time", "date"],
    "收支类型": ["收支类型", "收/支", "收支", "类型", "交易类型", "direction"],
    "金额": ["金额", "金额(元)", "金额（元）", "交易金额", "amount"],
    "收入金额": ["收入金额", "收入", "入账金额"],
    "支出金额": ["支出金额", "支出", "出账金额"],
    "类别": ["类别", "分类", "一级分类", "category"],
    "子类": ["子类", "二级分类", "subcategory"],
    "账户": ["账户", "支付方式", "付款方式", "收/付款方式", "account"],
    "备注": ["备注", "商品", "商品说明", "交易对方", "商户", "摘要", "说明", "description", "note"],
    "tags": ["tags", "标签"],
    "note": ["note", "导入备注"],
    "id": ["id", "交易单号"],
    "refund_of": ["refund_of", "退款关联"],
    "reimburse_of": ["reimburse_of", "报销关联"],
    "报销状态": ["报销状态"],
    "预计报销": ["预计报销"],
    "pairid": ["pairid", "配对号"],
    "target_account": ["target_account", "目标账户", "对方账户"],
    "currency": ["currency", "币种"],
    "original_amount": ["original_amount", "原币金额"],
    "fx_rate": ["fx_rate", "汇率"],
    "cny_amount": ["cny_amount", "人民币金额"],
}
KEYWORD_RULES = [
    ("收入", "工资", ["工资", "薪资", "salary"]),
    ("收入", "报销", ["报销"]),
    ("收入", "补贴", ["补贴", "津贴"]),
    ("食品餐饮", "外卖", ["外卖", "饿了么", "美团外卖"]),
    ("食品餐饮", "早餐", ["早餐"]),
    ("食品餐饮", "午餐", ["午餐"]),
    ("食品餐饮", "晚餐", ["晚餐"]),
    ("食品餐饮", "饮料酒水", ["饮料", "奶茶", "咖啡", "酒水"]),
    ("食品餐饮", "水果", ["水果"]),
    ("食品餐饮", "生鲜", ["生鲜", "买菜"]),
    ("食品餐饮", "正餐", ["餐厅", "饭店", "正餐", "吃饭"]),
    ("出行交通", "打车", ["打车", "滴滴", "出租车", "网约车"]),
    ("出行交通", "公交地铁", ["公交", "地铁", "交通卡"]),
    ("出行交通", "火车", ["火车", "高铁", "动车"]),
    ("出行交通", "飞机", ["飞机", "机票", "航班"]),
    ("出行交通", "加油", ["加油"]),
    ("出行交通", "停车费", ["停车"]),
    ("出行交通", "高速费", ["高速", "通行费"]),
    ("医疗健康", "挂号", ["挂号"]),
    ("医疗健康", "药品", ["药", "药房", "买药"]),
    ("医疗健康", "门诊", ["医院", "门诊"]),
    ("购物消费", "数码", ["数码", "电脑", "键盘", "鼠标", "手机"]),
    ("购物消费", "服饰运动", ["服装", "衣服", "鞋", "运动"]),
    ("生活服务", "快递", ["快递", "邮费"]),
    ("生活服务", "超市", ["超市", "便利店"]),
    ("居家生活", "水费", ["水费"]),
    ("居家生活", "电费", ["电费"]),
    ("居家生活", "住宿", ["住宿", "房租"]),
    ("出行交通", "维修", ["维修", "保养"]),
    ("休闲娱乐", "游戏", ["游戏"]),
    ("休闲娱乐", "KTV", ["KTV", "卡拉OK", "卡拉 OK"]),
    ("休闲娱乐", "旅游度假", ["旅游", "度假"]),
]


def read_csv(path: Path) -> list[dict[str, str]]:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Cannot decode CSV: {path}")


def column_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    total = 0
    for ch in letters:
        total = total * 26 + ord(ch.upper()) - ord("A") + 1
    return total - 1


def read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    values = []
    for si in root.findall("x:si", ns):
        parts = [node.text or "" for node in si.findall(".//x:t", ns)]
        values.append("".join(parts))
    return values


def read_xlsx(path: Path) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as zf:
        shared = read_shared_strings(zf)
        sheet_name = "xl/worksheets/sheet1.xml"
        root = ET.fromstring(zf.read(sheet_name))
    ns = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    table: list[list[str]] = []
    for row in root.findall(".//x:sheetData/x:row", ns):
        values: list[str] = []
        for cell in row.findall("x:c", ns):
            idx = column_index(cell.attrib.get("r", "A1"))
            while len(values) <= idx:
                values.append("")
            cell_type = cell.attrib.get("t")
            value_node = cell.find("x:v", ns)
            inline_node = cell.find("x:is/x:t", ns)
            if cell_type == "s" and value_node is not None:
                value = shared[int(value_node.text or "0")]
            elif inline_node is not None:
                value = inline_node.text or ""
            elif value_node is not None:
                value = value_node.text or ""
            else:
                value = ""
            values[idx] = value
        table.append(values)
    if not table:
        return []
    headers = [str(v).strip() for v in table[0]]
    return [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in table[1:] if any(row)]


def load_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return read_csv(path)
    if suffix == ".xlsx":
        return read_xlsx(path)
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("records", data.get("transactions", []))
    raise SystemExit(f"Unsupported input file: {path}")


def get_value(row: dict[str, Any], field: str) -> str:
    lowered = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in COLUMN_ALIASES[field]:
        if alias.lower() in lowered:
            value = lowered[alias.lower()]
            if value is not None and str(value).strip() != "":
                return str(value).strip()
    return ""


def parse_amount(value: str) -> Decimal | None:
    cleaned = value.strip().replace(",", "")
    cleaned = cleaned.replace("￥", "").replace("¥", "").replace("元", "")
    cleaned = cleaned.replace("+", "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def normalize_time(value: str) -> str:
    value = value.strip().replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value[:19], fmt)
            return parsed.strftime("%Y-%m-%d %H:%M") if " " in fmt else parsed.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return value


def normalize_type(raw_type: str, amount: Decimal | None, text: str) -> str:
    stripped = raw_type.strip()
    if stripped in {"支出", "收入", "还款", "转账", "退款", "报销", "投资"}:
        return stripped
    raw = raw_type.lower()
    text_lower = text.lower()
    if "退款" in raw or (not raw and "退款" in text_lower):
        return "退款"
    if "还款" in raw:
        return "还款"
    if any(word in raw for word in ["转账", "提现", "不计收支"]):
        return "转账"
    if any(word in raw for word in ["收入", "收款", "入账", "入金"]):
        return "收入"
    if any(word in raw for word in ["支出", "付款", "消费", "扣款"]):
        return "支出"
    if "还款" in text_lower:
        return "还款"
    if any(word in text_lower for word in ["转账", "提现", "不计收支"]):
        return "转账"
    if any(word in text_lower for word in ["收入", "收款", "入账", "入金"]):
        return "收入"
    if any(word in text_lower for word in ["支出", "付款", "消费", "扣款"]):
        return "支出"
    if amount is not None and amount < 0:
        return "支出"
    return "收入"


def normalize_pair(category: str, subcategory: str) -> tuple[str, str]:
    if (category, subcategory) in LEGACY_PAIR_ALIASES:
        category, subcategory = LEGACY_PAIR_ALIASES[(category, subcategory)]
    category = CATEGORY_ALIASES.get(category, category)
    subcategory = SUBCATEGORY_ALIASES.get(subcategory, subcategory)
    return category, subcategory


def classify(row: dict[str, Any], tx_type: str, text: str, account: str) -> tuple[str, str, bool]:
    raw_category = get_value(row, "类别")
    raw_subcategory = get_value(row, "子类")
    category, subcategory = normalize_pair(raw_category, raw_subcategory)
    if category in CATEGORY_MAP and subcategory in CATEGORY_MAP[category]:
        return category, subcategory, False
    if tx_type == "退款":
        lowered = text.lower()
        for category, subcategory, keywords in KEYWORD_RULES:
            if category not in {"收入"} and any(keyword.lower() in lowered for keyword in keywords):
                return category, subcategory, False
        return "退款", "退款", False
    if tx_type == "报销":
        if category in CATEGORY_MAP and subcategory in CATEGORY_MAP.get(category, ()):
            return category, subcategory, False
        return "报销", "其他", False
    if tx_type == "投资":
        if category in CATEGORY_MAP and subcategory in CATEGORY_MAP.get(category, ()):
            return category, subcategory, False
        return "投资", "理财", False
    if tx_type == "收入":
        for category, subcategory, keywords in KEYWORD_RULES:
            if category == "收入" and any(k.lower() in text.lower() for k in keywords):
                return category, subcategory, False
        return "收入", "其他", raw_category != "收入"
    if tx_type == "还款":
        return "还款", "白条还款" if account == "白条" else "月付还款", False
    if tx_type == "转账":
        return "转账", "个人转账", False
    lowered = text.lower()
    for category, subcategory, keywords in KEYWORD_RULES:
        if category != "收入" and any(k.lower() in lowered for k in keywords):
            return category, subcategory, False
    return "购物消费", "日用百货", True


def normalize_account(raw_account: str, source: str, fallback: str | None) -> str:
    for account in ACCOUNTS:
        if account in raw_account:
            return account
    if fallback:
        return fallback
    return DEFAULT_ACCOUNT_BY_SOURCE.get(source, "支付宝")


def normalize_record(row: dict[str, Any], source: str, fallback_account: str | None) -> dict[str, Any]:
    remark_parts = [get_value(row, "备注"), get_value(row, "note")]
    text = " ".join(part for part in remark_parts if part)
    raw_amount = get_value(row, "金额")
    amount = parse_amount(raw_amount)
    income_amount = parse_amount(get_value(row, "收入金额"))
    expense_amount = parse_amount(get_value(row, "支出金额"))
    if amount is None and income_amount is not None:
        amount = abs(income_amount)
    if amount is None and expense_amount is not None:
        amount = -abs(expense_amount)
    if amount is None:
        amount = Decimal("0")
    tx_type = normalize_type(get_value(row, "收支类型"), amount, text)
    if tx_type == "支出":
        signed_amount = -abs(amount)
    elif tx_type == "投资":
        signed_amount = amount
    else:
        signed_amount = abs(amount)
    currency = get_value(row, "currency").upper() or "CNY"
    original_amount = parse_amount(get_value(row, "original_amount"))
    fx_rate = parse_amount(get_value(row, "fx_rate"))
    cny_amount = parse_amount(get_value(row, "cny_amount"))
    if original_amount is not None:
        original_amount = -abs(original_amount) if tx_type == "支出" else abs(original_amount)
    if currency != "CNY" and original_amount is not None and fx_rate is not None:
        signed_amount = (original_amount * fx_rate).quantize(Decimal("0.01"))
    elif cny_amount is not None and currency != "CNY":
        signed_amount = -abs(cny_amount) if tx_type == "支出" else abs(cny_amount)
    account = normalize_account(get_value(row, "账户"), source, fallback_account)
    category, subcategory, pending = classify(row, tx_type, text, account)
    note_parts = []
    existing_note = get_value(row, "note")
    if existing_note:
        note_parts.append(existing_note)
    if source != "auto":
        note_parts.append(f"source={source}")
    if pending:
        note_parts.append("待确认分类")
    record = {
        "时间": normalize_time(get_value(row, "时间")),
        "收支类型": tx_type,
        "金额": float(signed_amount) if signed_amount % 1 else int(signed_amount),
        "类别": category,
        "子类": subcategory,
        "账户": account,
        "备注": get_value(row, "备注") or text or "导入记录",
        "tags": get_value(row, "tags"),
        "note": "; ".join(note_parts),
    }
    for field in ("id", "refund_of", "reimburse_of", "报销状态", "预计报销", "pairid", "target_account"):
        value = get_value(row, field)
        if value:
            record[field] = value
    if currency and currency != "CNY":
        record["currency"] = currency
        if original_amount is not None:
            record["original_amount"] = float(original_amount) if original_amount % 1 else int(original_amount)
        if fx_rate is not None:
            record["fx_rate"] = float(fx_rate) if fx_rate % 1 else int(fx_rate)
        record["cny_amount"] = record["金额"]
    elif get_value(row, "currency"):
        record["currency"] = "CNY"
    return record


def month_of(record: dict[str, Any]) -> str:
    return str(record["时间"])[:7]


def write_json(
    path: Path,
    records: list[dict[str, Any]],
    month: str | None = None,
    *,
    overwrite: bool = False,
) -> None:
    """Write one ledger shard. Existing files are refused unless overwrite is set."""
    if path.exists() and not overwrite:
        raise SystemExit(
            f"Refusing to overwrite existing ledger file: {path}. "
            "No further files will be written. Back up the ledger and pass --overwrite to replace it."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": SCHEMA_VERSION, "month": month or "mixed", "records": records}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def existing_ledger_paths(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


def refuse_existing_targets(paths: list[Path], overwrite: bool) -> None:
    """Abort the whole batch before any write when a target already exists."""
    if overwrite:
        return
    existing = existing_ledger_paths(paths)
    if not existing:
        return
    print(
        "Refusing to overwrite existing ledger files. No files were written.\n"
        "Re-import replaces each target file and drops records that are not in the new bill.\n"
        "Back up the ledger, then re-run with --overwrite only to replace these files:",
        file=sys.stderr,
    )
    for path in existing:
        print(f"- {path}", file=sys.stderr)
    raise SystemExit(1)


def output_path_for(args: argparse.Namespace, records: list[dict[str, Any]]) -> Path:
    if args.output:
        return Path(args.output)
    months = sorted({month_of(record) for record in records})
    if len(months) == 1:
        return Path("data") / f"{months[0]}.json"
    return Path("data") / "imported.json"


def record_shard_key(record: dict[str, Any], mode: str) -> str:
    text = str(record.get("时间", ""))
    if mode == "day":
        return text[:10]
    return text[:7]


def shard_output_path(out_dir: Path, key: str, year_dirs: bool, mode: str) -> Path:
    # The filename itself is the shard key so os.path.basename can recover it.
    filename = f"{key}.json"
    if mode == "day":
        if year_dirs:
            return out_dir / key[:4] / key[:7] / filename
        return out_dir / filename
    if year_dirs:
        return out_dir / key[:4] / filename
    return out_dir / filename


def monthly_output_path(out_dir: Path, month: str, year_dirs: bool) -> Path:
    return shard_output_path(out_dir, month, year_dirs, "month")


def main() -> int:
    parser = argparse.ArgumentParser(description="Import CSV/XLSX bills into standard ledger JSON.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", "-o", help="Output file or directory. Default: data/<month>.json or data/imported.json")
    parser.add_argument("--source", default="auto", choices=["auto", "standard", "alipay", "wechat", "meituan", "bank"])
    parser.add_argument("--account", help="Fallback account when the source file has no account column.")
    parser.add_argument("--month", help="Only import records whose 时间 starts with YYYY-MM.")
    parser.add_argument("--split-by-month", action="store_true", help="Write one JSON file per month.")
    parser.add_argument("--shard", choices=["day", "month"], help="Write one JSON file per day or month. Keys use the file basename.")
    parser.add_argument("--year-dirs", action="store_true", help="Nest shard files under YYYY/ (and YYYY-MM/ for days).")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help=(
            "Replace existing ledger files. Without this flag, any existing target aborts the "
            "whole batch and nothing is written. Back up the ledger first; records missing from "
            "the new bill are dropped."
        ),
    )
    args = parser.parse_args()

    if args.split_by_month and args.shard == "day":
        raise SystemExit("--split-by-month cannot be combined with --shard day")
    if args.split_by_month and args.shard is None:
        args.shard = "month"
    if args.year_dirs and not args.shard:
        raise SystemExit("--year-dirs requires --split-by-month or --shard")
    if args.account and args.account not in ACCOUNTS:
        raise SystemExit(f"Invalid fallback account: {args.account}")
    rows = load_rows(args.input)
    records = [normalize_record(row, args.source, args.account) for row in rows]
    if args.month:
        records = [record for record in records if str(record["时间"]).startswith(args.month)]
    errors, warnings = validate_records(records)
    if errors:
        print("INVALID IMPORT", file=sys.stderr)
        for error in errors[:50]:
            print(f"- {error}", file=sys.stderr)
        return 1
    planned: list[tuple[Path, list[dict[str, Any]], str | None, str | None]] = []
    if args.shard:
        out_dir = Path(args.output or "data")
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            grouped[record_shard_key(record, args.shard)].append(record)
        for key, shard_records in sorted(grouped.items()):
            out = shard_output_path(out_dir, key, args.year_dirs, args.shard)
            month = key if args.shard == "month" else key[:7]
            planned.append((out, shard_records, month, key))
    else:
        out = output_path_for(args, records)
        month = args.month or (month_of(records[0]) if records else None)
        planned.append((out, records, month, None))

    refuse_existing_targets([path for path, _records, _month, _key in planned], args.overwrite)
    for out, shard_records, month, key in planned:
        write_json(out, shard_records, month, overwrite=args.overwrite)
        if key is None:
            print(f"wrote {out} records={len(shard_records)} warnings={len(warnings)}")
            continue
        written_key = shard_key(out, args.shard)
        if written_key != key:
            raise SystemExit(f"shard key mismatch for {out}: basename key {written_key!r} != {key!r}")
        print(f"wrote {out} records={len(shard_records)} shard={written_key} warnings={len(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
