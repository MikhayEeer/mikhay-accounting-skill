# Storage Layout

Use year/month shards for real ledgers. Agents should open only the shard needed for the user request.

## Recommended Tree

```text
data/
  ledger/
    2026/
      2026-06.json
      2026-07.json
  assets/
    2026/
      2026-06.assets.json
raw/
  2026/
    2026-06/
exports/
  2026/
reports/
  2026/
```

## Rules

- Store transaction records by month: `data/ledger/YYYY/YYYY-MM.json`.
- Store asset snapshots separately when they are not part of the monthly ledger: `data/assets/YYYY/YYYY-MM.assets.json`.
- Keep raw third-party bills under `raw/YYYY/YYYY-MM/`.
- Keep generated CSV/JSON exports under `exports/YYYY/`.
- Keep generated reports under `reports/YYYY/`.
- Do not load all shards for normal tasks. Pick months first, then run scripts on those files.
- For cross-year statistics, summarize each month first and merge totals instead of asking the model to read all records.

## Import Command

```bash
python scripts/import_ledger.py raw/bill.csv --split-by-month --year-dirs --output data/ledger
```
