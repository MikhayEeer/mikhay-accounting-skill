---
name: mikhay-accounting-skill
description: Chinese personal accounting workflow for CSV/JSON/XLSX ledger and asset files. Use when the user asks to import, export, record, classify, validate, summarize, store, or analyze records with fields like 时间, 收支类型, 金额, 类别, 子类, 账户, 备注, tags, note; supports 支出, 收入, 还款, 转账, year/month shard layout, third-party bill conversion, account balances, credit debt, installment plans, repayment reminders, net asset statistics, and monthly reports.
---

# Mikhay Accounting Skill

Use this skill to work with a Chinese personal ledger directory. Keep answers concise.

## Files To Read

Read these files only as needed:

- `schema.md`: Chinese CSV/JSON fields and validation rules.
- `categories.md`: category, subcategory, and legacy alias rules.
- `accounts.md`: account balance, liability, installment, repayment, and sync rules.
- `storage.md`: year/month shard layout for large ledgers.
- `import_rules.md`: third-party CSV/XLSX import mapping rules.
- `scripts/import_ledger.py`: convert CSV/XLSX/JSON bills to standard JSON.
- `scripts/export_ledger.py`: export standard JSON to CSV or normalized JSON.
- `scripts/validate_ledger.py`: deterministic format checks.
- `scripts/summarize_ledger.py`: 基础收入、支出、还款、转账、分类统计。
- `scripts/summarize_assets.py`: 资产、负债、净资产、分期、还款提醒。

## Workflow

1. Identify ledger files: `.csv`, `.xlsx`, or `.json`.
2. Read `schema.md` before changing or validating data.
3. Read `categories.md` before classifying transactions.
4. Read `storage.md` before locating or writing real ledger files.
5. Read `import_rules.md` before importing third-party bills.
6. Never print full real ledgers unless the user asks.
7. Import third-party files with `scripts/import_ledger.py <file> --split-by-month --year-dirs --output data/ledger`.
8. Use `scripts/validate_ledger.py <file>` before trusting data.
9. Use `scripts/summarize_ledger.py <file>` for quick statistics.
10. Use `scripts/summarize_assets.py <json>` for total assets, debt, net assets, installments, and reminders.
11. Export with `scripts/export_ledger.py <json> --output exports/ledger.csv`.
12. Mark uncertain classifications as `待确认`.

## Data Rules

- Main fields are `时间 / 收支类型 / 金额 / 类别 / 子类 / 账户 / 备注 / tags / note`.
- `收支类型` must be one of: `支出`, `收入`, `还款`, `转账`.
- Use signed `金额`: `支出` is negative; `收入`, `还款`, `转账` are positive.
- `转账` 不计入收入或支出。
- `还款` is separate from normal spending; display it as a positive total.
- Ledger records should update asset statistics: spending lowers assets or raises debt; income raises assets; repayment lowers cash and debt; transfer moves money.
- If direct asset edits differ from ledger-derived balances, report the difference and ask before creating an adjustment item.
- Prefer year/month shards like `data/ledger/2026/2026-06.json`; do not load all shards unless required.
- Keep real data in ignored folders such as `data/`, `raw/`, or `exports/`.

## Output Style

Return short results:

- Totals first.
- Then category highlights.
- Then warnings or uncertain items.
- Avoid long transaction dumps.
