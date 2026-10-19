#!/usr/bin/env python3
"""Shared deterministic helpers for ledger scripts.

Shard keys always come from os.path.basename. Slicing a full path such as
``data/ledger/2026/2026-06.json`` can capture the bogus key ``r/202`` from the
``ledger/2026`` directory prefix.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "0.3.0"
# Empty and 0.2.0 books stay valid. Other values still warn.
ACCEPTED_SCHEMA_VERSIONS = {"", "0.2.0", "0.3.0"}
TAG_PREFIXES = ("trip:", "event:", "person:", "nature:")
TYPES = {"支出", "收入", "还款", "转账", "退款", "报销", "投资"}
ACCOUNT_KINDS = {"资产", "负债"}
INCLUDE_FLAGS = {"included", "excluded"}
REIMBURSE_STATUSES = {"待报销", "已报销", "不报销"}
CREDIT_MODES = {"debt_only", "with_limit"}
INVEST_OUT_SUBCATEGORY = "赎回"

INCLUDED_ASSETS = {"建设银行", "工商银行", "招商银行", "微信钱包", "支付宝", "美团"}
INCLUDED_LIABILITIES = {"白条", "花呗", "美团月付", "抖音月付"}
CREDIT_CARDS = {"白条", "花呗", "美团月付", "抖音月付", "Apple Card"}
# 备查 accounts stay out of headline net worth unless a policy overrides them.
EXCLUDED_ACCOUNTS = {
    "Apple Card": "负债",
    "公积金": "资产",
    "助学贷款": "负债",
    "加密货币": "资产",
}

CATEGORY_MAP = {
    "食品餐饮": {"早餐", "午餐", "晚餐", "正餐", "外卖", "快餐", "小吃", "夜宵", "零食", "休闲零食", "水果", "生鲜", "饮料", "饮料酒水", "聚餐", "请客吃饭"},
    "出行交通": {"打车", "公交地铁", "加油", "充电", "火车", "飞机", "租车", "停车费", "高速费", "通行费", "酒店住宿", "景区门票", "维修"},
    "购物消费": {"服饰运动", "数码", "手机数码", "日常家居", "家居用品", "日用百货", "礼品", "纪念品", "祭祀用品", "虚拟充值", "外汇", "交通工具", "邮寄"},
    "服饰美容": {"服装"},
    "居家生活": {"住宿", "水费", "洗护", "政务", "邮寄", "电费"},
    "生活服务": {"超市", "快递", "清洁用品", "燃气费"},
    "医疗健康": {"挂号", "门诊", "检查费", "药品", "买药", "医院看病"},
    "休闲娱乐": {"旅游度假", "棋牌桌游", "酒吧", "游戏", "游戏充值", "游戏购买", "KTV"},
    "收入": {"工资", "报销", "补贴", "其他"},
    "还款": {"白条还款", "月付还款"},
    "转账": {"个人转账"},
    "退款": {"退款", "其他"},
    "报销": {"AI订阅", "差旅", "其他"},
    "投资": {"定投", "证券入金", "赎回", "理财"},
}

CATEGORY_ALIASES = {"健康医疗": "医疗健康"}
SUBCATEGORY_ALIASES = {"停车": "停车费", "高速费用": "高速费", "酒水饮料": "饮料酒水"}
LEGACY_PAIR_ALIASES = {
    ("购物消费", "饮料酒水"): ("食品餐饮", "饮料酒水"),
}

SPEND_CATEGORIES = set(CATEGORY_MAP) - {"收入", "还款", "转账", "报销", "投资"}
LEDGER_SUFFIXES = {".json", ".csv"}
DECIMAL_RE = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?")
CURRENCY_RE = re.compile(r"[A-Z]{3}")
TAG_SUFFIX_RE = re.compile(r"[\w.-]+")
TARGET_RE = re.compile(r"(?:target_account|目标账户|还款账户)\s*[:=：]?\s*([^\s;；,，]+)")

CC_METHOD_A = "A（最近快照+快照后新增）"
CC_METHOD_B = "B（账本从零重放）"


def default_account_catalog() -> dict[str, dict[str, str]]:
    catalog: dict[str, dict[str, str]] = {}
    for name in INCLUDED_ASSETS:
        catalog[name] = {"kind": "资产", "include": "included"}
    for name in INCLUDED_LIABILITIES:
        catalog[name] = {"kind": "负债", "include": "included"}
    for name, kind in EXCLUDED_ACCOUNTS.items():
        catalog[name] = {"kind": kind, "include": "excluded"}
    return catalog


def known_accounts() -> set[str]:
    return set(default_account_catalog())


def normalize_include(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"excluded", "exclude", "备查", "true", "yes", "1"}:
        return "excluded"
    if text in {"included", "include", "计入", "false", "no", "0"}:
        return "included"
    return ""


def merge_account_policy(rows: Iterable[dict[str, Any]] | None) -> tuple[dict[str, dict[str, str]], list[str]]:
    catalog = default_account_catalog()
    errors: list[str] = []
    for i, row in enumerate(rows or [], 1):
        prefix = f"account_policy[{i}]"
        name = str(row.get("账户", "")).strip()
        if not name:
            errors.append(f"{prefix}: missing 账户")
            continue
        current = catalog.get(name, {"kind": "", "include": "included"})
        kind = str(row.get("账户类型", "")).strip() or current["kind"]
        if kind and kind not in ACCOUNT_KINDS:
            errors.append(f"{prefix}: 账户类型 must be 资产 or 负债")
        include = normalize_include(row.get("纳入", row.get("include", "")))
        if not include and "备查" in row:
            include = "excluded" if truthy(row.get("备查")) else "included"
        if row.get("纳入") not in (None, "") or row.get("include") not in (None, ""):
            if not include:
                errors.append(f"{prefix}: 纳入 must be included or excluded")
        catalog[name] = {"kind": kind or "资产", "include": include or current.get("include") or "included"}
    return catalog, errors


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


def shard_key(path: str | os.PathLike[str], mode: str) -> str:
    """Return a day or month key from the file basename only."""
    if mode not in {"day", "month"}:
        raise ValueError(f"shard must be day or month, got {mode!r}")
    base = os.path.basename(os.fspath(path))
    pattern = r"^(\d{4}-\d{2}-\d{2})" if mode == "day" else r"^(\d{4}-\d{2})"
    matched = re.match(pattern, base)
    return matched.group(1) if matched else ""


def index_shard_files(paths: Iterable[Path], mode: str) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = {}
    for path in paths:
        key = shard_key(path, mode) or "unkeyed"
        grouped.setdefault(key, []).append(path)
    return grouped


def iter_ledger_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in LEDGER_SUFFIXES]
    return sorted(files)


def loads_json(text: str) -> Any:
    return json.loads(text, parse_float=Decimal, parse_int=int)


def empty_book() -> dict[str, Any]:
    return {
        "schema_version": "",
        "records": [],
        "asset_snapshots": [],
        "credit_accounts": [],
        "installment_plans": [],
        "repayment_reminders": [],
        "account_policy": [],
        "credit_policy": {},
        "inferred_snapshot": None,
        "is_ledger": True,
    }


def looks_like_ledger(data: Any) -> bool:
    if isinstance(data, list):
        return True
    if not isinstance(data, dict):
        return False
    keys = {
        "records",
        "transactions",
        "asset_snapshots",
        "credit_accounts",
        "installment_plans",
        "repayment_reminders",
        "account_policy",
        "credit_policy",
        "month",
        "schema_version",
    }
    return bool(keys & set(data))


def load_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8-sig")
    if not text.strip():
        return [], [f"empty CSV: {path}"]
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader)
    except StopIteration:
        return [], [f"empty CSV: {path}"]
    names = [cell.strip() for cell in header]
    if any(not name for name in names):
        errors.append("CSV header has an empty column name")
    if len(names) != len(set(names)):
        errors.append("CSV header has duplicate column names")
    rows: list[dict[str, str]] = []
    for line_no, cols in enumerate(reader, 2):
        if not any(str(col).strip() for col in cols):
            continue
        if len(cols) != len(names):
            errors.append(f"CSV line {line_no}: expected {len(names)} columns, got {len(cols)}")
            continue
        rows.append({name: value.strip() for name, value in zip(names, cols) if name})
    return rows, errors


def load_file(path: Path) -> tuple[dict[str, Any], list[str]]:
    book = empty_book()
    errors: list[str] = []
    suffix = path.suffix.lower()
    if suffix == ".csv":
        rows, csv_errors = load_csv_rows(path)
        errors.extend(csv_errors)
        book["records"] = rows
        return book, errors
    if suffix == ".json":
        try:
            data = loads_json(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return book, [f"invalid JSON: {exc}"]
        if isinstance(data, list):
            book["records"] = data
            return book, errors
        if isinstance(data, dict):
            if not looks_like_ledger(data):
                book["is_ledger"] = False
                return book, [f"not a ledger file: {path}"]
            book["schema_version"] = str(data.get("schema_version", "") or "")
            book["records"] = data.get("records", data.get("transactions", []))
            book["asset_snapshots"] = data.get("asset_snapshots", [])
            book["credit_accounts"] = data.get("credit_accounts", [])
            book["installment_plans"] = data.get("installment_plans", [])
            book["repayment_reminders"] = data.get("repayment_reminders", [])
            book["account_policy"] = data.get("account_policy", [])
            policy = data.get("credit_policy") or {}
            book["credit_policy"] = policy if isinstance(policy, dict) else {}
            book["inferred_snapshot"] = data.get("inferred_snapshot")
            book["month"] = data.get("month", "")
            return book, errors
        return book, [f"unsupported JSON shape: {path}"]
    return book, [f"unsupported file type: {path}"]


def decimal_value(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        text = str(value)
    elif isinstance(value, float):
        text = format(value, "f")
    else:
        text = str(value).strip()
    if not DECIMAL_RE.fullmatch(text):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def money(value: Any) -> Decimal:
    parsed = decimal_value(value)
    return parsed if parsed is not None else Decimal("0")


def fmt(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def fmt_pct(part: Decimal, whole: Decimal) -> str:
    if whole == 0:
        return "0.00%"
    pct = (part / whole * Decimal("100")).quantize(Decimal("0.01"))
    return f"{pct}%"


def parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def default_max_date(today: date | None = None) -> date:
    today = today or date.today()
    return today + timedelta(days=366)


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


def parse_tags(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        parts = [str(item).strip() for item in value]
    else:
        text = str(value).strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                loaded = json.loads(text)
            except json.JSONDecodeError:
                loaded = None
            if isinstance(loaded, list):
                parts = [str(item).strip() for item in loaded]
            else:
                parts = [text]
        else:
            parts = re.split(r"[;；,，\s]+", text)
    return [part for part in parts if part]


def tag_namespace(tag: str) -> str:
    for prefix in TAG_PREFIXES:
        if tag.startswith(prefix):
            return prefix[:-1]
    return ""


def check_tag(tag: str) -> tuple[str, str]:
    """Return ('ok'|'legacy'|'error', message)."""
    namespace = tag_namespace(tag)
    if namespace:
        suffix = tag.split(":", 1)[1]
        if suffix and TAG_SUFFIX_RE.fullmatch(suffix):
            return "ok", ""
        return "error", f"invalid tag {tag!r}"
    if ":" in tag:
        return "error", f"tag {tag!r} is outside trip:/event:/person:/nature:"
    return "legacy", f"legacy tag {tag!r}; prefer trip:, event:, person:, or nature:"


def is_refund(row: dict[str, Any]) -> bool:
    if str(row.get("收支类型", "")).strip() == "退款":
        return True
    return bool(str(row.get("refund_of", "")).strip())


def reimburse_ref(row: dict[str, Any]) -> str:
    return str(row.get("reimburse_of", "")).strip()


def reimburse_status(row: dict[str, Any]) -> str:
    """Missing status means the expense is not waiting on reimbursement."""
    text = str(row.get("报销状态", "") or "").strip()
    return text or "不报销"


def credit_mode(row: dict[str, Any] | None, policy: Any = None) -> str:
    """Resolve debt_only vs with_limit. Default is debt_only."""
    row_mode = str((row or {}).get("mode") or "").strip()
    if row_mode in CREDIT_MODES:
        return row_mode
    if isinstance(policy, dict):
        policy_mode = str(policy.get("mode") or "").strip()
        if policy_mode in CREDIT_MODES:
            return policy_mode
    return "debt_only"


def target_account(row: dict[str, Any]) -> str:
    direct = str(row.get("target_account", "")).strip()
    if direct:
        return direct
    text = f"{row.get('note', '')} {row.get('备注', '')}"
    match = TARGET_RE.search(text)
    return match.group(1) if match else ""


def record_id(row: dict[str, Any]) -> str:
    return str(row.get("id", "")).strip()


def pair_id(row: dict[str, Any]) -> str:
    return str(row.get("pairid", "")).strip()


def currency_of(row: dict[str, Any]) -> str:
    text = str(row.get("currency", "") or "").strip().upper()
    return text or "CNY"


def json_money(value: Decimal) -> int | float:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def last_working_day(year: int, month: int) -> date:
    """Last Monday–Friday of the month. Holidays are not subtracted."""
    import calendar

    day = calendar.monthrange(year, month)[1]
    current = date(year, month, day)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + (month - 1) + delta
    return index // 12, index % 12 + 1


def clamp_day(year: int, month: int, day: int) -> date:
    import calendar

    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(day, 1), last))


def cycle_start(as_of: date, bill_day: int) -> date:
    candidate = clamp_day(as_of.year, as_of.month, bill_day)
    if candidate <= as_of:
        return candidate
    year, month = shift_month(as_of.year, as_of.month, -1)
    return clamp_day(year, month, bill_day)


def previous_cycle_start(start: date, bill_day: int) -> date:
    year, month = shift_month(start.year, start.month, -1)
    return clamp_day(year, month, bill_day)


def due_date_for_cycle(start: date, due_day: int, bill_day: int) -> date:
    if due_day > bill_day:
        return clamp_day(start.year, start.month, due_day)
    year, month = shift_month(start.year, start.month, 1)
    return clamp_day(year, month, due_day)


def load_buckets(path: Path) -> list[tuple[str, set[str] | None]]:
    data = loads_json(path.read_text(encoding="utf-8"))
    mapping = data.get("buckets", data) if isinstance(data, dict) else None
    if not isinstance(mapping, dict):
        raise SystemExit(f"buckets config must be a JSON object: {path}")
    buckets: list[tuple[str, set[str] | None]] = []
    seen: set[str] = set()
    star = 0
    for name, categories in mapping.items():
        if not isinstance(categories, list) or not categories:
            raise SystemExit(f"bucket {name!r} must list categories")
        if categories == ["*"] or set(categories) == {"*"}:
            star += 1
            buckets.append((str(name), None))
            continue
        cleaned = {str(item).strip() for item in categories}
        if "*" in cleaned:
            raise SystemExit(f"bucket {name!r} cannot mix * with named categories")
        overlap = cleaned & seen
        if overlap:
            raise SystemExit(f"bucket categories overlap: {', '.join(sorted(overlap))}")
        seen |= cleaned
        buckets.append((str(name), cleaned))
    if star > 1:
        raise SystemExit("only one bucket may use *")
    return buckets


def apply_buckets(
    net_by_category: dict[str, Decimal],
    buckets: list[tuple[str, set[str] | None]],
) -> list[tuple[str, Decimal]]:
    remaining = dict(net_by_category)
    rows: list[tuple[str, Decimal]] = []
    star_name = ""
    for name, categories in buckets:
        if categories is None:
            star_name = name
            continue
        total = sum((remaining.pop(category, Decimal("0")) for category in categories), Decimal("0"))
        rows.append((name, total))
    if star_name:
        rows.append((star_name, sum(remaining.values(), Decimal("0"))))
    return rows


class FlowTotals:
    def __init__(self) -> None:
        self.count = 0
        self.income = Decimal("0")
        self.expense_gross = Decimal("0")
        self.refunds = Decimal("0")
        self.reimbursed = Decimal("0")
        self.pending_reimburse = Decimal("0")
        self.pending_items: list[dict[str, Any]] = []
        self.invest_in = Decimal("0")
        self.invest_out = Decimal("0")
        self.invest_by_account: dict[str, Decimal] = defaultdict(Decimal)
        self.invest_accounts: set[str] = set()
        self.repayment = Decimal("0")
        self.transfer_legs = Decimal("0")
        self.internal_transfer = Decimal("0")
        self.by_category_gross: dict[str, Decimal] = defaultdict(Decimal)
        self.by_category_refund: dict[str, Decimal] = defaultdict(Decimal)
        self.by_category_reimburse: dict[str, Decimal] = defaultdict(Decimal)
        self.by_subcategory: dict[str, Decimal] = defaultdict(Decimal)
        self.by_subcategory_refund: dict[str, Decimal] = defaultdict(Decimal)
        self.by_subcategory_reimburse: dict[str, Decimal] = defaultdict(Decimal)
        self.repayment_by_account: dict[str, Decimal] = defaultdict(Decimal)
        self.cash_expense_net = Decimal("0")

    @property
    def expense_net(self) -> Decimal:
        """实际花销. Pending reimbursement stays in this number until cash arrives."""
        return self.expense_gross - self.refunds - self.reimbursed

    @property
    def investment_net(self) -> Decimal:
        """投入 − 赎回. Not spending and not income."""
        return self.invest_in - self.invest_out


def _category_of(row: dict[str, Any]) -> tuple[str, str]:
    category = str(row.get("类别", "")).strip() or "未分类"
    subcategory = str(row.get("子类", "")).strip() or "未分类"
    category, subcategory, _ = normalize_pair(category, subcategory)
    return category, subcategory


def _note_investment_leg(totals: FlowTotals, row: dict[str, Any], *, count_flow: bool) -> None:
    amount = money(row.get("金额"))
    account = str(row.get("账户", "")).strip()
    if account:
        totals.invest_by_account[account] += amount
    _, subcategory = _category_of(row)
    if count_flow:
        magnitude = abs(amount)
        if subcategory == INVEST_OUT_SUBCATEGORY:
            totals.invest_out += magnitude
        else:
            totals.invest_in += magnitude
    if target_account(row) and not pair_id(row):
        target = target_account(row)
        totals.invest_by_account[target] -= amount
        totals.invest_accounts.add(target)
        return
    if subcategory == INVEST_OUT_SUBCATEGORY and amount < 0 and account:
        totals.invest_accounts.add(account)
    elif subcategory != INVEST_OUT_SUBCATEGORY and amount > 0 and account:
        totals.invest_accounts.add(account)


def _collect_pending(totals: FlowTotals, rows: list[dict[str, Any]]) -> None:
    received: dict[str, Decimal] = defaultdict(Decimal)
    for row in rows:
        if str(row.get("收支类型", "")).strip() != "报销":
            continue
        ref = reimburse_ref(row)
        if ref:
            received[ref] += abs(money(row.get("金额")))
    for row in rows:
        if str(row.get("收支类型", "")).strip() != "支出":
            continue
        if reimburse_status(row) != "待报销":
            continue
        raw_expected = row.get("预计报销", "")
        if raw_expected is None or str(raw_expected).strip() == "":
            expected = abs(money(row.get("金额")))
        else:
            expected = abs(money(raw_expected))
        pending = expected - received.get(record_id(row), Decimal("0"))
        if pending <= 0:
            continue
        totals.pending_reimburse += pending
        stamp = parse_time(row.get("时间"))
        totals.pending_items.append(
            {
                "时间": stamp.date().isoformat() if stamp else "",
                "金额": pending,
                "备注": str(row.get("备注", "")).strip(),
                "账户": str(row.get("账户", "")).strip(),
                "id": record_id(row),
            }
        )


def accumulate(rows: list[dict[str, Any]], catalog: dict[str, dict[str, str]] | None = None) -> FlowTotals:
    """花销 counts spending net of refunds and received reimbursements.

    待报销 stays inside 实际花销 until a 报销 row arrives. 投资 is neither
    spending nor income. 内部转账 counts each pair once.
    """
    totals = FlowTotals()
    totals.count = len(rows)
    catalog = catalog or default_account_catalog()
    by_id = {record_id(row): row for row in rows if record_id(row)}
    pair_legs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    invest_legs: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        tx_type = str(row.get("收支类型", "")).strip()
        amount = money(row.get("金额"))
        magnitude = abs(amount)
        account = str(row.get("账户", "")).strip()
        category, subcategory = _category_of(row)
        kind = catalog.get(account, {}).get("kind", "")
        if is_refund(row):
            target = by_id.get(str(row.get("refund_of", "")).strip())
            if target is not None:
                category, subcategory = _category_of(target)
            totals.refunds += magnitude
            totals.by_category_refund[category] += magnitude
            totals.by_subcategory_refund[f"{category}/{subcategory}"] += magnitude
            if kind != "负债":
                totals.cash_expense_net -= magnitude
            continue
        if tx_type == "收入":
            totals.income += magnitude
        elif tx_type == "支出":
            totals.expense_gross += magnitude
            totals.by_category_gross[category] += magnitude
            totals.by_subcategory[f"{category}/{subcategory}"] += magnitude
            if kind != "负债":
                totals.cash_expense_net += magnitude
        elif tx_type == "报销":
            target = by_id.get(reimburse_ref(row))
            if target is not None:
                category, subcategory = _category_of(target)
                totals.by_category_reimburse[category] += magnitude
                totals.by_subcategory_reimburse[f"{category}/{subcategory}"] += magnitude
            totals.reimbursed += magnitude
            if kind != "负债":
                totals.cash_expense_net -= magnitude
        elif tx_type == "还款":
            totals.repayment += magnitude
            totals.repayment_by_account[account or "未填账户"] += magnitude
        elif tx_type == "转账":
            totals.transfer_legs += magnitude
            pid = pair_id(row)
            if pid:
                pair_legs[pid].append(row)
            else:
                totals.internal_transfer += magnitude
        elif tx_type == "投资":
            pid = pair_id(row)
            if pid:
                invest_legs[pid].append(row)
            else:
                _note_investment_leg(totals, row, count_flow=True)

    for legs in pair_legs.values():
        outgoing = [abs(money(leg.get("金额"))) for leg in legs if money(leg.get("金额")) < 0]
        if outgoing:
            totals.internal_transfer += outgoing[0]
        elif legs:
            totals.internal_transfer += max(abs(money(leg.get("金额"))) for leg in legs)
    for legs in invest_legs.values():
        if not legs:
            continue
        _note_investment_leg(totals, legs[0], count_flow=True)
        for leg in legs[1:]:
            _note_investment_leg(totals, leg, count_flow=False)
    _collect_pending(totals, rows)
    return totals


def category_net(totals: FlowTotals) -> dict[str, Decimal]:
    names = set(totals.by_category_gross) | set(totals.by_category_refund) | set(totals.by_category_reimburse)
    return {
        name: totals.by_category_gross[name] - totals.by_category_refund[name] - totals.by_category_reimburse[name]
        for name in names
    }
