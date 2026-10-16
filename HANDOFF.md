# Agent Handoff

Use this folder as a self-contained accounting skill. Skill version `0.2.2` lives in `SKILL.md` frontmatter. Ledger `schema_version` stays `0.2.0`. Homepage: https://github.com/MikhayEeer/mikhay-accounting-skill. The ledger stays on the local machine and is not uploaded. This skill is for Chinese personal ledgers.

## Start

1. Read `SKILL.md`. When a record looks wrong, read `references/faq.md`. When a command fails, read `references/troubleshooting.md`.
2. Read `schema.md` before editing ledger data.
3. Read `categories.md` before classifying records.
4. Read `storage.md` before locating or writing real ledger files.
5. Import third-party bills when needed:

```bash
python scripts/import_ledger.py <bill.csv-or-xlsx> --shard month --year-dirs --output data/ledger
```

If any target shard already exists, the script aborts the whole batch and writes nothing. Back up `data/` before re-running with `--overwrite`. That flag replaces each target file and can drop records missing from the new bill.

6. Run validation before statistics. Totals must come from these scripts, never hand math:

```bash
python scripts/validate_ledger.py <ledger.csv-or-json-or-directory>
python scripts/summarize_ledger.py <ledger-or-directory>
python scripts/summarize_tags.py <ledger-directory>
```

7. Query assets, debt, net assets, installments, and reminders when needed:

```bash
python scripts/summarize_assets.py <ledger-or-assets.json> --cc-method A
python scripts/summarize_assets.py <ledger-or-assets.json> --forecast
python scripts/project_assets.py <assets.json> <ledger.json>
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
- `data/ledger/YYYY/YYYY-MM/YYYY-MM-DD.json`
- `data/assets/YYYY/YYYY-MM.assets.json`
- `data/wishlist/YYYY/wishlist.json`

## Package

Maintainer-only. `tools/package_skill.py` is not part of the end-user skill. ClawHub publish ignores `tools/` (`.clawhubignore`), and the archive omits `tools/` and `package_skill.py`.

```bash
python tools/package_skill.py
```

Share files from `dist/`.
