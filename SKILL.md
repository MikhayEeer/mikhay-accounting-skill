---
name: mikhay-accounting-skill
description: Chinese personal accounting workflow for CSV/JSON/XLSX ledger files. Use when the user asks to import, export, record, classify, validate, summarize, or analyze records with fields like 时间, 收支类型, 金额, 类别, 子类, 账户, 备注, tags, note; supports 支出, 收入, 还款, 转账, third-party bill conversion, account statistics, repayment reminders, and monthly bookkeeping reports.
---

# Mikhay Accounting Skill

Use this skill to work with a Chinese personal ledger directory. Keep answers concise.

## Files To Read

Read these files only as needed:

- `schema.md`: Chinese CSV/JSON fields and validation rules.
- `categories.md`: category, subcategory, and legacy alias rules.
- `import_rules.md`: third-party CSV/XLSX import mapping rules.
- `scripts/import_ledger.py`: convert CSV/XLSX/JSON bills to standard JSON.
- `scripts/export_ledger.py`: export standard JSON to CSV or normalized JSON.
- `scripts/validate_ledger.py`: deterministic format checks.
- `scripts/summarize_ledger.py`: 基础收入、支出、还款、转账、分类统计。

## Workflow

1. Identify ledger files: `.csv`, `.xlsx`, or `.json`.
2. Read `schema.md` before changing or validating data.
3. Read `categories.md` before classifying transactions.
4. Read `import_rules.md` before importing third-party bills.
5. Never print full real ledgers unless the user asks.
6. Import third-party files with `scripts/import_ledger.py <file> --output data/imported.json`.
7. Use `scripts/validate_ledger.py <file>` before trusting data.
8. Use `scripts/summarize_ledger.py <file>` for quick statistics.
9. Export with `scripts/export_ledger.py <json> --output exports/ledger.csv`.
10. Mark uncertain classifications as `待确认`.

## Data Rules

- Main fields are `时间 / 收支类型 / 金额 / 类别 / 子类 / 账户 / 备注 / tags / note`.
- `收支类型` must be one of: `支出`, `收入`, `还款`, `转账`.
- Use signed `金额`: `支出` is negative; `收入`, `还款`, `转账` are positive.
- `转账` 不计入收入或支出。
- `还款` is separate from normal spending; display it as a positive total.
- Keep real data in ignored folders such as `data/`, `raw/`, or `exports/`.

## Output Style

Return short results:

- Totals first.
- Then category highlights.
- Then warnings or uncertain items.
- Avoid long transaction dumps.
