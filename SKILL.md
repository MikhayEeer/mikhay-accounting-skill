---
name: mikhay-accounting-skill
description: Chinese personal accounting workflow for CSV/JSON/XLSX ledger, asset, and wishlist files. Use when the user asks to import, export, record, classify, validate, summarize, store, analyze records, or evaluate planned purchases with fields like 时间, 收支类型, 金额, 类别, 子类, 账户, 备注, tags, note; supports 支出, 收入, 还款, 转账, 退款, trip/event/person/nature tags, day or month shards, refunds, transfer pairs, multi-currency CNY totals, included and excluded accounts, credit-card snapshot methods, payday forecast, third-party bill conversion, and monthly reports.
---

# Mikhay Accounting Skill

Use this skill to work with a Chinese personal ledger directory. Keep answers concise.

## Hard Rule: Totals

Totals must come from scripts scanning everything, never hand math.

That includes tag totals, category percentages, gross and net spending, refunds, transfers, and net worth. Run the script on the directory (or on every shard in scope). Do not add a sample of rows yourself, and do not skip a shard because it looks small.

- `scripts/summarize_ledger.py` for 花销 and 内部转账.
- `scripts/summarize_tags.py` for every tag total. It always scans the whole tree it is given.
- `scripts/summarize_assets.py` for included net worth, 备查 balances, card method, and `--forecast`.
- `scripts/validate_ledger.py` before trusting a file.

If a script was not run, do not invent a number.

## Files To Read

Read these files only as needed:

- `schema.md`: Chinese CSV/JSON fields and validation rules.
- `categories.md`: category, subcategory, and legacy alias rules.
- `accounts.md`: inclusion flag, balances, credit-card methods, forecast, installments.
- `storage.md`: day/month shard layout. Shard keys use the file basename.
- `wishlist.md`: pre-purchase wishlist schema and rules.
- `import_rules.md`: third-party CSV/XLSX import mapping rules.
- `scripts/import_ledger.py`: convert CSV/XLSX/JSON bills to standard JSON.
- `scripts/export_ledger.py`: export standard JSON to CSV or normalized JSON.
- `scripts/validate_ledger.py`: deterministic format checks.
- `scripts/summarize_ledger.py`: 花销毛额/净额、内部转账、分类占比。
- `scripts/summarize_tags.py`: scan every shard; per-tag gross, net, day, and category share.
- `scripts/summarize_assets.py`: included and excluded net worth, card method, forecast.
- `scripts/project_assets.py`: inferred balances from the latest observed snapshot plus later records.
- `scripts/analyze_wishlist.py`: 预购清单经济压力、购买建议、优先级。

## Workflow

1. Identify ledger files: `.csv`, `.xlsx`, or `.json`.
2. Read `schema.md` before changing or validating data.
3. Read `categories.md` before classifying transactions.
4. Read `storage.md` before locating or writing real ledger files.
5. Read `import_rules.md` before importing third-party bills.
6. Never print full real ledgers unless the user asks.
7. Import third-party files with `scripts/import_ledger.py <file> --shard month --year-dirs --output data/ledger`.
8. Use `scripts/validate_ledger.py <file-or-directory>` before trusting data.
9. Use `scripts/summarize_ledger.py <file-or-directory>` for statistics. Pass `--buckets buckets.json` only when a bucket file exists.
10. Use `scripts/summarize_tags.py <ledger-directory>` for tag totals. Do not total tags by hand.
11. Use `scripts/summarize_assets.py <json> --cc-method A` for net worth. Add `--forecast` when the user asks about card bills or payday.
12. Use `scripts/analyze_wishlist.py <wishlist.json> --ledger <month.json> --assets <assets.json>` for planned purchases.
13. Export with `scripts/export_ledger.py <json> --output exports/ledger.csv`.
14. Mark uncertain classifications as `待确认`.

## Data Rules

- Main fields are `时间 / 收支类型 / 金额 / 类别 / 子类 / 账户 / 备注 / tags / note`.
- `收支类型` must be one of: `支出`, `收入`, `还款`, `转账`, `退款`.
- Use signed `金额` in CNY: `支出` is negative; `收入`, `还款`, `退款` are positive. Legacy `转账` is positive. `pairid` legs are opposite signs.
- Optional currency columns are `currency`, `original_amount`, `fx_rate`, `cny_amount`. Missing currency means `CNY`. Totals use `金额`.
- Tags should use `trip:`, `event:`, `person:`, or `nature:`. Bare legacy tags are allowed with a warning.
- `退款` reduces 花销. It is not income. `refund_of` points at the original `支出` id when that id is known.
- `转账` is 内部转账, not 花销. Prefer two `pairid` legs. A note `target_account=` remains valid for a single-sided transfer.
- 花销口径 is gross spending minus refunds. 内部转账口径 counts each pair once. Reports show both.
- `还款` is separate from normal spending; display it as a positive total.
- Accounts are `included` or `excluded` (备查). Excluded examples include Apple Card, 公积金, 助学贷款, and 加密货币. Net worth prints the two groups separately.
- Credit cards default to snapshot method A (last snapshot plus post-snapshot records). Method B replays the card from zero. The script output names the method.
- New JSON files carry `schema_version`. Older files without it remain valid.
- Ledger records should update asset statistics: spending lowers assets or raises debt; income raises assets; repayment lowers cash and debt; refunds reverse the original effect; transfer moves money.
- If direct asset edits differ from ledger-derived balances, report the difference and ask before creating an adjustment item.
- Wishlist items are planned purchases, not ledger records; create a `支出` record only after purchase.
- Prefer shards like `data/ledger/2026/2026-06.json` or `data/ledger/2026/2026-06/2026-06-01.json`.
- For a total, the script must scan every shard in scope. For a question about one month, pass that month only and say so.
- Keep real data in ignored folders such as `data/`, `raw/`, or `exports/`.

## Output Style

Return short results:

- Totals first, copied from the script.
- Then category highlights, including the script's percentage.
- Then which card method or forecast payday was used, when assets were queried.
- Then warnings or uncertain items.
- Avoid long transaction dumps.
