# Agent Handoff

Use this folder as a self-contained accounting skill.

## Start

1. Read `SKILL.md`.
2. Read `schema.md` before editing ledger data.
3. Read `categories.md` before classifying records.
4. Import third-party bills when needed:

```bash
python scripts/import_ledger.py <bill.csv-or-xlsx> --output data/imported.json
```

5. Run validation before statistics:

```bash
python scripts/validate_ledger.py <ledger.csv-or-json>
python scripts/summarize_ledger.py <ledger.csv-or-json>
```

6. Query assets, debt, net assets, installments, and reminders when needed:

```bash
python scripts/summarize_assets.py <ledger-or-assets.json>
```

7. Export standard JSON when needed:

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

## Package

Create a handoff bundle:

```bash
python scripts/package_skill.py
```

Share files from `dist`.
