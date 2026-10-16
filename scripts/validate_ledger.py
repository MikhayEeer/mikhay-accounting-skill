#!/usr/bin/env python3
"""Validate Chinese personal ledger CSV/JSON files."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from ledgerlib import (
    ACCOUNT_KINDS,
    CATEGORY_ALIASES,
    CATEGORY_MAP,
    CURRENCY_RE,
    LEGACY_PAIR_ALIASES,
    SCHEMA_VERSION,
    SUBCATEGORY_ALIASES,
    TYPES,
    check_tag,
    currency_of,
    decimal_value,
    default_max_date,
    is_refund,
    iter_ledger_files,
    known_accounts,
    load_file,
    merge_account_policy,
    normalize_include,
    normalize_pair,
    pair_id,
    parse_tags,
    parse_time,
    record_id,
    target_account,
)


REQUIRED_RECORD = ["时间", "收支类型", "金额", "类别", "子类", "账户", "备注"]
ACCOUNTS = known_accounts()
LIABILITY_ACCOUNTS = {name for name, meta in merge_account_policy([])[0].items() if meta["kind"] == "负债"}
ASSET_ACCOUNTS = ACCOUNTS - LIABILITY_ACCOUNTS


def is_datetime(value: Any) -> bool:
    return parse_time(value) is not None


def _blank(value: Any) -> bool:
    return str(value if value is not None else "").strip() == ""


def _check_upper(prefix: str, value: Any, max_date: date, errors: list[str], field: str = "时间") -> None:
    parsed = parse_time(value)
    if parsed is None:
        errors.append(f"{prefix}: invalid {field}")
        return
    if parsed.date() > max_date:
        errors.append(f"{prefix}: {field} {parsed.date().isoformat()} is after upper bound {max_date.isoformat()}")


def _check_currency(prefix: str, row: dict[str, Any], amount: Decimal | None, errors: list[str]) -> None:
    raw_currency = row.get("currency", "")
    if not _blank(raw_currency) and not CURRENCY_RE.fullmatch(str(raw_currency).strip().upper()):
        errors.append(f"{prefix}: currency must be a 3-letter code")
        return
    currency = currency_of(row)
    original = row.get("original_amount", "")
    fx = row.get("fx_rate", "")
    cny = row.get("cny_amount", "")
    original_amount = decimal_value(original) if not _blank(original) else None
    fx_rate = decimal_value(fx) if not _blank(fx) else None
    cny_amount = decimal_value(cny) if not _blank(cny) else None
    if not _blank(original) and original_amount is None:
        errors.append(f"{prefix}: original_amount must be numeric")
    if not _blank(fx) and (fx_rate is None or fx_rate <= 0):
        errors.append(f"{prefix}: fx_rate must be a positive number")
    if not _blank(cny) and cny_amount is None:
        errors.append(f"{prefix}: cny_amount must be numeric")
    if amount is None:
        return
    if currency == "CNY":
        if fx_rate is not None and fx_rate != 1:
            errors.append(f"{prefix}: CNY fx_rate must be 1")
        if original_amount is not None and original_amount != amount:
            errors.append(f"{prefix}: CNY original_amount must equal 金额")
        if cny_amount is not None and cny_amount != amount:
            errors.append(f"{prefix}: cny_amount must equal 金额")
        return
    if original_amount is None or fx_rate is None:
        errors.append(f"{prefix}: non-CNY records require original_amount and fx_rate")
        return
    expected = (original_amount * fx_rate).quantize(Decimal("0.01"))
    actual = amount.quantize(Decimal("0.01"))
    if abs(expected - actual) > Decimal("0.01"):
        errors.append(f"{prefix}: 金额 {actual} != original_amount * fx_rate {expected}")
    if cny_amount is not None and abs(cny_amount.quantize(Decimal("0.01")) - actual) > Decimal("0.01"):
        errors.append(f"{prefix}: cny_amount must equal 金额")


def validate_records(
    rows: list[dict[str, Any]],
    *,
    max_date: date | None = None,
    strict_refs: bool = False,
    catalog: dict[str, dict[str, str]] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    max_date = max_date or default_max_date()
    catalog = catalog or merge_account_policy([])[0]
    seen_ids: dict[str, int] = {}
    seen_rows: dict[tuple[Any, ...], int] = {}
    id_index: dict[str, dict[str, Any]] = {}
    pairs: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)

    if not isinstance(rows, list):
        return ["records must be a list"], warnings

    for i, row in enumerate(rows, 1):
        prefix = f"record[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: record must be an object")
            continue
        for field in REQUIRED_RECORD:
            if _blank(row.get(field)):
                errors.append(f"{prefix}: missing {field}")
        tx_type = str(row.get("收支类型", "")).strip()
        amount = decimal_value(row.get("金额"))
        account = str(row.get("账户", "")).strip()
        category = str(row.get("类别", "")).strip()
        subcategory = str(row.get("子类", "")).strip()
        norm_category, norm_subcategory, pair_warnings = normalize_pair(category, subcategory)
        warnings.extend(f"{prefix}: {w}" for w in pair_warnings)
        _check_upper(prefix, row.get("时间"), max_date, errors)
        if tx_type not in TYPES:
            errors.append(f"{prefix}: invalid 收支类型 {tx_type!r}")
        if amount is None:
            errors.append(f"{prefix}: 金额 must be a decimal number")
        elif amount == 0:
            errors.append(f"{prefix}: 金额 cannot be zero")
        else:
            if amount != amount.quantize(Decimal("0.01")):
                warnings.append(f"{prefix}: 金额 has more than 2 decimal places")
            if tx_type == "支出" and amount > 0:
                warnings.append(f"{prefix}: 支出 usually uses a negative 金额")
            elif tx_type in {"收入", "还款"} and amount < 0:
                warnings.append(f"{prefix}: {tx_type} usually uses a positive 金额")
            elif tx_type == "退款" and amount < 0:
                warnings.append(f"{prefix}: 退款 usually uses a positive 金额")
            elif tx_type == "转账" and amount < 0 and not pair_id(row):
                warnings.append(f"{prefix}: legacy 转账 usually uses a positive 金额; pair legs may be signed")
        if account not in catalog:
            errors.append(f"{prefix}: invalid 账户 {account!r}")
        if norm_category not in CATEGORY_MAP:
            errors.append(f"{prefix}: invalid 类别 {category!r}")
        elif norm_subcategory not in CATEGORY_MAP[norm_category]:
            errors.append(f"{prefix}: invalid 子类 {subcategory!r} for 类别 {category!r}")
        else:
            if tx_type == "退款" or (is_refund(row) and tx_type != "支出"):
                if norm_category in {"收入", "还款", "转账"}:
                    errors.append(f"{prefix}: 退款 cannot use 类别 {norm_category}")
            else:
                expected_category = {"收入": "收入", "还款": "还款", "转账": "转账"}.get(tx_type)
                if expected_category and norm_category != expected_category:
                    errors.append(f"{prefix}: 收支类型 {tx_type} should use 类别 {expected_category}")
                if tx_type == "支出" and norm_category in {"收入", "还款", "转账", "退款"}:
                    errors.append(f"{prefix}: 支出 cannot use 类别 {norm_category}")
        for tag in parse_tags(row.get("tags")):
            status, message = check_tag(tag)
            if status == "error":
                errors.append(f"{prefix}: {message}")
            elif status == "legacy":
                warnings.append(f"{prefix}: {message}")
        _check_currency(prefix, row, amount, errors)
        noted_target = target_account(row)
        if noted_target and noted_target not in catalog:
            errors.append(f"{prefix}: unknown target_account {noted_target!r}")
        if tx_type == "转账" and not pair_id(row) and not noted_target:
            warnings.append(f"{prefix}: 转账 has neither pairid nor target_account")
        rid = record_id(row)
        if rid:
            if rid in seen_ids:
                errors.append(f"{prefix}: duplicate id {rid!r} also at record[{seen_ids[rid]}]")
            else:
                seen_ids[rid] = i
                id_index[rid] = row
        if amount is not None and is_datetime(row.get("时间")):
            dup_key = (str(row.get("时间", "")).strip(), tx_type, amount, account, str(row.get("备注", "")).strip())
            if dup_key in seen_rows:
                errors.append(f"{prefix}: duplicate of record[{seen_rows[dup_key]}]")
            else:
                seen_rows[dup_key] = i
        if pair_id(row):
            pairs[pair_id(row)].append((i, row))
        refund_ref = str(row.get("refund_of", "")).strip()
        if refund_ref:
            if tx_type not in {"退款", "支出"}:
                errors.append(f"{prefix}: refund_of is only valid on 退款 records")

    for pid, legs in pairs.items():
        label = f"pairid {pid}"
        if len(legs) != 2:
            errors.append(f"{label}: expected 2 legs, found {len(legs)}")
            continue
        (left_i, left), (right_i, right) = legs
        left_amount = decimal_value(left.get("金额"))
        right_amount = decimal_value(right.get("金额"))
        if str(left.get("收支类型", "")).strip() != "转账" or str(right.get("收支类型", "")).strip() != "转账":
            errors.append(f"{label}: both legs must be 转账")
        if left_amount is None or right_amount is None:
            continue
        if abs(left_amount) != abs(right_amount):
            errors.append(f"{label}: amounts are not equal ({left_amount} vs {right_amount})")
        if left_amount * right_amount >= 0:
            errors.append(f"{label}: legs must have opposite directions")
        if str(left.get("账户", "")).strip() == str(right.get("账户", "")).strip():
            errors.append(f"{label}: legs must use different accounts")

    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            continue
        refund_ref = str(row.get("refund_of", "")).strip()
        if not refund_ref:
            continue
        target = id_index.get(refund_ref)
        prefix = f"record[{i}]"
        if target is None:
            message = f"{prefix}: refund_of {refund_ref!r} does not match a record id"
            if strict_refs:
                errors.append(message)
            else:
                warnings.append(message + " in this file")
        elif str(target.get("收支类型", "")).strip() != "支出":
            errors.append(f"{prefix}: refund_of target must be 支出")
    return errors, warnings


def validate_assets(rows: list[dict[str, Any]], catalog: dict[str, dict[str, str]], max_date: date) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for i, row in enumerate(rows, 1):
        prefix = f"asset_snapshot[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: snapshot must be an object")
            continue
        for field in ["时间", "账户"]:
            if _blank(row.get(field)):
                errors.append(f"{prefix}: missing {field}")
        if _blank(row.get("余额", row.get("金额", ""))):
            errors.append(f"{prefix}: missing 金额")
        _check_upper(prefix, row.get("时间"), max_date, errors)
        account = str(row.get("账户", "")).strip()
        if account not in catalog:
            errors.append(f"{prefix}: invalid 账户 {account!r}")
        kind = str(row.get("账户类型", "")).strip()
        if kind and kind not in ACCOUNT_KINDS:
            errors.append(f"{prefix}: 账户类型 must be 资产 or 负债")
        include = str(row.get("纳入", "")).strip()
        if include and not normalize_include(include):
            errors.append(f"{prefix}: 纳入 must be included or excluded")
        amount = decimal_value(row.get("余额", row.get("金额")))
        if amount is None:
            errors.append(f"{prefix}: 金额 must be a decimal number")
        elif kind == "资产" and amount < 0:
            warnings.append(f"{prefix}: asset account usually uses non-negative 金额")
        elif kind == "负债" and amount > 0:
            warnings.append(f"{prefix}: liability snapshot usually uses negative 金额")
        currency = str(row.get("currency", "") or "").strip()
        if currency and not CURRENCY_RE.fullmatch(currency.upper()):
            errors.append(f"{prefix}: currency must be a 3-letter code")
    return errors, warnings


def validate_day(value: Any) -> bool:
    try:
        day = int(value)
    except (TypeError, ValueError):
        return False
    return 1 <= day <= 31


def validate_credit_accounts(rows: list[dict[str, Any]], catalog: dict[str, dict[str, str]]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for i, row in enumerate(rows, 1):
        prefix = f"credit_account[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: credit account must be an object")
            continue
        for field in ["账户", "欠款"]:
            if _blank(row.get(field)):
                errors.append(f"{prefix}: missing {field}")
        account = str(row.get("账户", "")).strip()
        kind = catalog.get(account, {}).get("kind")
        if account not in catalog or kind != "负债":
            errors.append(f"{prefix}: 账户 must be a liability account")
        debt = decimal_value(row.get("欠款"))
        if debt is None or debt < 0:
            errors.append(f"{prefix}: 欠款 must be a non-negative decimal")
        for field in ["额度", "可用额度"]:
            value = row.get(field, "")
            if not _blank(value) and decimal_value(value) is None:
                errors.append(f"{prefix}: {field} must be numeric")
        for field in ["账单日", "还款日"]:
            value = row.get(field, "")
            if not _blank(value) and not validate_day(value):
                errors.append(f"{prefix}: {field} must be 1-31")
    return errors, warnings


def validate_installments(rows: list[dict[str, Any]], catalog: dict[str, dict[str, str]], max_date: date) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required = ["id", "账户", "本金", "总期数", "已还期数", "每期金额", "下一还款日", "状态"]
    seen_ids: set[str] = set()
    for i, row in enumerate(rows, 1):
        prefix = f"installment_plan[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: installment must be an object")
            continue
        for field in required:
            if _blank(row.get(field)):
                errors.append(f"{prefix}: missing {field}")
        plan_id = str(row.get("id", "")).strip()
        if plan_id:
            if plan_id in seen_ids:
                errors.append(f"{prefix}: duplicate installment id {plan_id!r}")
            seen_ids.add(plan_id)
        account = str(row.get("账户", "")).strip()
        if catalog.get(account, {}).get("kind") != "负债":
            errors.append(f"{prefix}: 账户 must be a liability account")
        for field in ["本金", "每期金额"]:
            value = decimal_value(row.get(field))
            if value is None or value <= 0:
                errors.append(f"{prefix}: {field} must be a positive decimal")
        try:
            total = int(row.get("总期数", ""))
            paid = int(row.get("已还期数", ""))
        except (TypeError, ValueError):
            errors.append(f"{prefix}: 总期数 and 已还期数 must be integers")
        else:
            if total <= 0:
                errors.append(f"{prefix}: 总期数 must be positive")
            if paid < 0:
                errors.append(f"{prefix}: 已还期数 cannot be negative")
            if total > 0 and paid > total:
                errors.append(f"{prefix}: 已还期数 cannot exceed 总期数")
        _check_upper(prefix, row.get("下一还款日"), max_date, errors, "下一还款日")
    return errors, warnings


def validate_reminders(rows: list[dict[str, Any]], catalog: dict[str, dict[str, str]], max_date: date) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for i, row in enumerate(rows, 1):
        prefix = f"repayment_reminder[{i}]"
        if not isinstance(row, dict):
            errors.append(f"{prefix}: reminder must be an object")
            continue
        for field in ["时间", "账户", "金额", "状态"]:
            if _blank(row.get(field)):
                errors.append(f"{prefix}: missing {field}")
        _check_upper(prefix, row.get("时间"), max_date, errors)
        account = str(row.get("账户", "")).strip()
        if catalog.get(account, {}).get("kind") != "负债":
            errors.append(f"{prefix}: 账户 must be a liability account")
        amount = decimal_value(row.get("金额"))
        if amount is None or amount <= 0:
            errors.append(f"{prefix}: 金额 must be a positive decimal")
    return errors, warnings


def validate_book(
    book: dict[str, Any],
    *,
    max_date: date | None = None,
    strict_refs: bool = False,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    max_date = max_date or default_max_date()
    version = str(book.get("schema_version", "") or "")
    if not version:
        warnings.append("schema_version missing; treated as a legacy ledger")
    elif version != SCHEMA_VERSION:
        warnings.append(f"unrecognized schema_version {version!r}; this tool writes {SCHEMA_VERSION}")
    catalog, policy_errors = merge_account_policy(book.get("account_policy") or [])
    errors.extend(policy_errors)
    record_errors, record_warnings = validate_records(
        book.get("records") or [],
        max_date=max_date,
        strict_refs=strict_refs,
        catalog=catalog,
    )
    asset_errors, asset_warnings = validate_assets(book.get("asset_snapshots") or [], catalog, max_date)
    credit_errors, credit_warnings = validate_credit_accounts(book.get("credit_accounts") or [], catalog)
    installment_errors, installment_warnings = validate_installments(book.get("installment_plans") or [], catalog, max_date)
    reminder_errors, reminder_warnings = validate_reminders(book.get("repayment_reminders") or [], catalog, max_date)
    errors.extend(record_errors)
    errors.extend(asset_errors)
    errors.extend(credit_errors)
    errors.extend(installment_errors)
    errors.extend(reminder_errors)
    warnings.extend(record_warnings)
    warnings.extend(asset_warnings)
    warnings.extend(credit_warnings)
    warnings.extend(installment_warnings)
    warnings.extend(reminder_warnings)
    return errors, warnings


def collect_paths(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(iter_ledger_files(path))
        else:
            files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Chinese personal ledger CSV/JSON files.")
    parser.add_argument("paths", nargs="+", type=Path, help="Ledger files or directories. Directories are scanned fully.")
    parser.add_argument("--max-date", help="Upper bound for dates, YYYY-MM-DD. Default: today + 366 days.")
    args = parser.parse_args()
    if args.max_date:
        parsed = parse_time(args.max_date)
        if parsed is None:
            raise SystemExit("--max-date must be YYYY-MM-DD")
        max_date = parsed.date()
    else:
        max_date = default_max_date()

    files = collect_paths(args.paths)
    if not files:
        raise SystemExit("no ledger files found")
    combined_records: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    books: list[tuple[Path, dict[str, Any]]] = []
    for path in files:
        book, load_errors = load_file(path)
        if not book.get("is_ledger", True):
            warnings.append(f"{path}: skipped non-ledger file")
            continue
        if load_errors:
            errors.extend(f"{path}: {item}" for item in load_errors)
        books.append((path, book))
        combined_records.extend(row for row in book["records"] if isinstance(row, dict))

    strict_refs = len(books) > 1
    if len(books) == 1:
        book_errors, book_warnings = validate_book(books[0][1], max_date=max_date, strict_refs=False)
        errors.extend(book_errors)
        warnings.extend(book_warnings)
    else:
        for path, book in books:
            partial = dict(book)
            partial["records"] = []
            book_errors, book_warnings = validate_book(partial, max_date=max_date, strict_refs=False)
            errors.extend(f"{path}: {item}" for item in book_errors)
            warnings.extend(f"{path}: {item}" for item in book_warnings)
        catalog: dict[str, dict[str, str]] = {}
        for _, book in books:
            merged, policy_errors = merge_account_policy(book.get("account_policy") or [])
            catalog.update(merged)
            errors.extend(policy_errors)
        if not catalog:
            catalog = merge_account_policy([])[0]
        record_errors, record_warnings = validate_records(
            combined_records,
            max_date=max_date,
            strict_refs=strict_refs,
            catalog=catalog,
        )
        errors.extend(record_errors)
        warnings.extend(record_warnings)

    label = files[0] if len(files) == 1 else f"{len(files)} files"
    if errors:
        print(f"INVALID: {label}")
        for error in errors:
            print(f"- {error}")
        if warnings:
            print("WARNINGS:")
            for warning in warnings[:50]:
                print(f"- {warning}")
            if len(warnings) > 50:
                print(f"- ... {len(warnings) - 50} more warnings")
        return 1

    print(f"OK: {label}")
    print(f"records: {len(combined_records)}")
    if len(books) == 1:
        book = books[0][1]
        print(f"asset_snapshots: {len(book['asset_snapshots'])}")
        print(f"credit_accounts: {len(book['credit_accounts'])}")
        print(f"installment_plans: {len(book['installment_plans'])}")
        print(f"repayment_reminders: {len(book['repayment_reminders'])}")
    if warnings:
        print(f"warnings: {len(warnings)}")
        for warning in warnings[:20]:
            print(f"- {warning}")
        if len(warnings) > 20:
            print(f"- ... {len(warnings) - 20} more warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
