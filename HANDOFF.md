# Agent Handoff

Use this folder as a self-contained accounting skill.

## Start

1. Read `SKILL.md`.
2. Read `schema.md` before editing ledger data.
3. Read `categories.md` before classifying records.
4. Read `storage.md` before locating or writing real ledger files.
5. Import third-party bills when needed:

```bash
python scripts/import_ledger.py <bill.csv-or-xlsx> --split-by-month --year-dirs --output data/ledger
```

6. Run validation before statistics:

```bash
python scripts/validate_ledger.py <ledger.csv-or-json>
python scripts/summarize_ledger.py <ledger.csv-or-json>
```

7. Query assets, debt, net assets, installments, and reminders when needed:

```bash
python scripts/summarize_assets.py <ledger-or-assets.json>
```

8. Analyze planned purchases when needed:

```bash
python scripts/analyze_wishlist.py <wishlist.json> --ledger <month-ledger.json> --assets <assets.json>
```

9. Export standard JSON when needed:

```bash
python scripts/export_ledger.py <ledger.json> --output exports/ledger.csv
```

Direct asset edits should report the ledger-derived difference and ask before creating adjustment records.

## Data Safety

Do not print full real ledgers unless the user asks.

Private data should stay in ignored folders:

- `data/`
- `raw/`
- `exports/`
- `private/`
- `real/`

Preferred ledger shards:

- `data/ledger/YYYY/YYYY-MM.json`
- `data/assets/YYYY/YYYY-MM.assets.json`
- `data/wishlist/YYYY/wishlist.json`

## Package

Create a handoff bundle:

```bash
python scripts/package_skill.py
```

Share files from `dist/`.
