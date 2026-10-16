[English](README.md) · [中文](README.zh-CN.md)

# Mikhay Accounting Skill

Skill version `0.2.2` (see `SKILL.md` frontmatter). Ledger `schema_version` stays `0.2.0`.

Install: `npx skills add MikhayEeer/mikhay-accounting-skill`

Homepage: https://github.com/MikhayEeer/mikhay-accounting-skill

License: MIT, copyright MikhayEeer. Full text in [LICENSE](LICENSE).

Chinese personal ledger workflow for CSV, JSON, and XLSX files. Agent instructions stay in Chinese in `SKILL.md`. Common mistakes: `references/faq.md`. Recovery: `references/troubleshooting.md`.

Display name: `Mikhay 记账 - 资产管理/信用卡/预购清单/年月统计`.

## Privacy

This skill is for Chinese personal ledgers. Records, asset snapshots, and wishlists stay in local files under `data/`, `raw/`, and `exports/`. The scripts do not upload the ledger.

## Import and export

**Re-import can delete data.** `scripts/import_ledger.py` refuses to overwrite an existing ledger file unless you pass `--overwrite`. If any target path already exists, the whole batch aborts and nothing is written. The script checks `Path.exists()` before it writes. `--overwrite` replaces each target file; records that are not in the new bill are dropped from that file. Back up `data/` before you use the flag. The gate is enforced by the script, not only by asking first.

Import CSV or XLSX into standard JSON:

```bash
python scripts/import_ledger.py raw/bill.csv --output data/imported.json
```

Split by month:

```bash
python scripts/import_ledger.py raw/bill.csv --split-by-month --year-dirs --output data/ledger
```

Replace existing shards only after a backup:

```bash
python scripts/import_ledger.py raw/bill.csv --shard month --year-dirs --output data/ledger --overwrite
```

Export standard JSON to CSV:

```bash
python scripts/export_ledger.py data/ledger/2026/2026-06.json --output exports/2026/2026-06.csv
```

Preferred real ledger shards: `data/ledger/YYYY/YYYY-MM.json`. Day shards: `data/ledger/YYYY/YYYY-MM/YYYY-MM-DD.json`.

```bash
python scripts/import_ledger.py raw/bill.csv --shard day --year-dirs --output data/ledger
python scripts/import_ledger.py raw/bill.csv --shard month --year-dirs --output data/ledger
```

Shard keys use the file name (`os.path.basename`). The month key of `data/ledger/2026/2026-06.json` is `2026-06`. Do not slice the full path; that produces the wrong key `r/202`.

Validate:

```bash
python scripts/validate_ledger.py data/ledger/2026/2026-06.json
python scripts/validate_ledger.py data/ledger
```

## Spending and internal transfers

Totals come from scripts. Do not add them by hand. The scripts scan every shard you pass in.

```bash
python scripts/summarize_ledger.py data/ledger
python scripts/summarize_ledger.py data/ledger --buckets examples/buckets.sample.json
python scripts/summarize_tags.py data/ledger
```

Two bases:

- **花销 (spending):** gross expense minus refunds. A refund (`收支类型=退款` or `refund_of`) is not income and is not a new purchase. Reports show both gross and net.
- **内部转账 (internal transfers):** `转账` between accounts. A `pairid` pair is counted once. Transfers are not spending.

Tags use `trip:`, `event:`, `person:`, and `nature:`. `summarize_tags.py` prints gross, net, per-day totals, and the category share on the same line.

Optional fields: `currency` (default CNY), `original_amount`, `fx_rate`, `cny_amount`. Totals use the CNY `金额`. New JSON files include `schema_version`. Older books that omit these fields still load.

## Net worth, credit cards, and payday

```bash
python scripts/summarize_assets.py data/assets/2026/2026-06.assets.json --cc-method A
python scripts/summarize_assets.py data/assets/2026/2026-06.assets.json --forecast --as-of 2026-06-15
python scripts/project_assets.py data/assets/assets.json data/ledger/2026/2026-06.json
```

Accounts are `included` or `excluded` (备查). Net worth is printed as 计入净资产 and 备查账户. Built-in 备查 examples: Apple Card, 公积金, 助学贷款, 加密货币.

Credit-card balances default to method A: latest snapshot plus records after that snapshot. Method B replays the card ledger from zero and ignores the snapshot. The report names the method.

`--forecast` prints each card's projected statement and repayment against payday cash flow. Payday is the last Monday–Friday of the month.

## Assets

Query total assets, liabilities, net worth, installments, and repayment reminders:

```bash
python scripts/summarize_assets.py data/assets/2026/2026-06.assets.json
```

New ledger records affect asset totals. Editing an asset snapshot directly should report the difference and ask before writing an adjustment. `project_assets.py --write` writes the inferred view only when you pass that flag.

## Wishlist

Pressure, suggestions, and priority for planned purchases:

```bash
python scripts/analyze_wishlist.py data/wishlist/2026/wishlist.json --ledger data/ledger/2026/2026-06.json --assets data/assets/2026/2026-06.assets.json
```

A wishlist item is not a ledger record. Write an `支出` only after the purchase happens.

## Maintainer packaging

`tools/package_skill.py` is maintainer-only. It is not an end-user ledger command. ClawHub publish ignores `tools/` via `.clawhubignore`, and the archive itself omits `tools/` and `package_skill.py`.

```bash
python tools/package_skill.py
```

Output:

```text
dist/mikhay-accounting-skill.tar.gz
dist/mikhay-accounting-skill.zip
```

The archive includes the skill, reference docs, import rules, `scripts/`, fictional examples, both READMEs, and `LICENSE`. It does not include `VERSION`, `tests/`, `.github/`, `tools/`, `data/`, `raw/`, `exports/`, `.claude/`, or `.codex/`. `MANIFEST.json` uses the same version as `SKILL.md`.

## Using the skill compared with not using it

This comparison used a local sample that is not in the repository: one local check, a monthly total, and a category top list (Claude Code, GLM-5.2). The times and token counts below are that session's order of magnitude, not the example files in this repo.

| | Without the skill (LLM only) | With the skill (scripts + short instructions) |
|---|---|---|
| Input tokens | Schema, categories, and rules pasted or recalled, about 2–4k tokens of rules plus about 15k of records | Read `SKILL.md`, then open schema, categories, or references only when needed |
| Reasoning tokens | Classify, sum, and alias each row; long output, easy to get wrong, about 8–15k output tokens | Almost no arithmetic; two Bash commands |
| Output tokens | Hand-written report, about 1–2k | Script result, about 300–500 tokens |
| Latency | One turn of 30s to over 1min, longer with correction rounds | Two Bash calls, about 3–8s |
| Accuracy | Sums and alias normalization often drift; a few hundred rows rarely match on the first try | Deterministic; matches the reconciliation file |
| Total tokens | About 25–35k | About 3–5k |

## Conclusion

- Tokens: the skill used about 5–8× fewer, mostly because the rules and the row-by-row arithmetic stay out of the prompt.
- Speed: about 5–10× faster, from two or three correction rounds down to one pass.
- Quality: the largest gap. Hand sums and alias normalization can miss by hundreds of yuan. The scripts are deterministic.

For ongoing bookkeeping (new records, monthly reports, exceptions), install the skill and follow: read the schema, run validate, run summarize, and report only the totals and warnings the scripts print. Tag totals, category shares, and net worth come from a full shard scan. Do not add them by hand.

Tests:

```bash
python -m pytest -q
```
