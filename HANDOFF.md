# Agent Handoff

Use this folder as a self-contained accounting skill.

## Start

1. Read `SKILL.md`.
2. Read `schema.md` before editing ledger data.
3. Read `categories.md` before classifying records.
4. Run validation before statistics:

```bash
python scripts/validate_ledger.py <ledger.csv-or-json>
python scripts/summarize_ledger.py <ledger.csv-or-json>
```

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

Share files from `dist/`.
