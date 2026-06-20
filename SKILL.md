---
name: mikhay-accounting-skill
description: Chinese personal accounting workflow for CSV/JSON ledger files. Use when the user asks to record, classify, validate, summarize, or analyze records with fields like 时间, 收支类型, 金额, 类别, 子类, 账户, 备注, tags, note; supports 支出, 收入, 还款, 转账, account statistics, repayment reminders, and monthly bookkeeping reports.
---

# Mikhay Accounting Skill

Use this skill to work with a Chinese personal ledger directory. Keep answers concise.

## Files To Read

Read these files only as needed:

- `schema.md`: Chinese CSV/JSON fields and validation rules.
- `categories.md`: category, subcategory, and legacy alias rules.
- `scripts/validate_ledger.py`: deterministic format checks.
- `scripts/summarize_ledger.py`: 基础收入、支出、还款、转账、分类统计。

## Workflow

1. Identify ledger files: `.csv` or `.json`.
2. Read `schema.md` before changing or validating data.
3. Read `categories.md` before classifying transactions.
4. Never print full real ledgers unless the user asks.
5. Use `scripts/validate_ledger.py <file>` before trusting data.
6. Use `scripts/summarize_ledger.py <file>` for quick statistics.
7. Mark uncertain classifications as `待确认`.

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
