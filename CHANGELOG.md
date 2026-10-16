# Changelog

## 0.2.2 - 2026-10-16

Import no longer replaces an existing ledger shard unless `--overwrite` is set. Ledger `schema_version` stays `0.2.0`.

### Fixed

- `scripts/import_ledger.py` checks `Path.exists()` before writing. If any target path already exists and `--overwrite` is absent, the whole batch aborts and nothing is written. `write_json` uses the same rule.

### Changed

- Skill version is `0.2.2`. `displayName` is `Mikhay 记账 - 资产管理/信用卡/预购清单/年月统计`.
- `metadata.openclaw.homepage` is `https://github.com/MikhayEeer/mikhay-accounting-skill`.
- `SKILL.md` and `references/faq.md` warn that re-import can drop records, tell you to back up `data/`, and state that the script enforces `--overwrite`.
- `package_skill.py` moved to `tools/`. It is maintainer-only, listed in `.clawhubignore`, and omitted from the handoff archive.
- `README.md` is English. `README.zh-CN.md` is the Chinese copy of the same sections. `SKILL.md` stays Chinese.

### Added

- Privacy note: local Chinese personal ledger only; scripts do not upload it. License in the repo stays MIT.

## 0.2.1 - 2026-10-16

Documentation only. Ledger scripts and `schema_version` stay at `0.2.0`.

### Added

- `references/faq.md` lists common mistakes and the correct recording rules.
- `references/troubleshooting.md` classifies missing fields, bad formats, validation failures, missing files, corrupt JSON, and retries.
- `references/triggers.md` gives ten user phrases with the module and the reply shape.
- `references/design-rationale.md` explains snapshots versus inferred balances, and why refunds are not income.
- End-to-end workflows in `examples/workflow-import-monthly.md`, `examples/workflow-credit-repay.md`, and `examples/workflow-fix-records.md`.

### Changed

- Skill version is `0.2.1` in `SKILL.md` frontmatter (`slug`, `displayName`, `version`, `summary`). The `VERSION` file is removed so the package version has one source.
- `SKILL.md` now states what this skill does not do, and points at the reference files instead of only listing trigger keywords.
- MIT `LICENSE`, copyright MikhayEeer. README includes the license and `npx skills add MikhayEeer/mikhay-accounting-skill`.
- Sample ledgers use round fictional amounts and say `虚构示例`. The placeholder tag is `person:demo`.

## 0.2.0 - 2026-10-16

Ledger scripts now scan shards for totals, and existing books that only use the original fields stay valid.

### Added

- Tag namespaces `trip:`, `event:`, `person:`, and `nature:`. `scripts/summarize_tags.py` scans every shard and prints per-tag gross, net, day, and category totals. Category rows include the percentage on the same line.
- Refunds (`收支类型=退款` and/or `refund_of`). Reports show gross and net. Refunds are not income.
- Transfer pairs via `pairid`. The validator requires two legs, equal absolute amounts, and opposite directions. `target_account=` in `note` still works.
- Multi-currency fields: `currency` (default `CNY`), `original_amount`, `fx_rate`, and `cny_amount`. Statistics use the CNY `金额`.
- Account flag `included` / `excluded` (备查). Net worth is split into 计入净资产 and 备查账户. Built-in 备查 examples: Apple Card, 公积金, 助学贷款, 加密货币.
- Credit-card snapshot method A (default, last snapshot plus later records) and method B (replay card ledgers from zero). The report names the method.
- `--forecast` on `scripts/summarize_assets.py`: projected statement and repayment per card against payday cash flow. Payday is the last Monday–Friday of the month.
- `--shard=day|month` on import. Shard keys use `os.path.basename`, so a path such as `data/ledger/2026/2026-06.json` is `2026-06` and not `r/202`.
- Optional `--buckets` map for `scripts/summarize_ledger.py`.
- `schema_version` (`0.2.0`) on newly written JSON. Missing versions warn and still load.
- `scripts/project_assets.py` rebuilds an inferred snapshot from the latest observed balance plus later records.
- Subcategories `维修`, `电费`, and `KTV`.
- pytest suite and GitHub Actions CI.
- 花销 vs 内部转账 dual-basis totals in `scripts/summarize_ledger.py`.

### Compatibility

- Old ledgers do not need `schema_version`, namespaced tags, `pairid`, currency columns, or account policy.
- Untagged legacy tags warn instead of failing.
- A single-sided `转账` with `target_account` remains valid.
- `scripts/validate_ledger.py` still checks categories, accounts, decimals, credit accounts, installments, and reminders.

The 0.1.0 minimal-core reply template and the deletions of README, storage, and wishlist analysis are not part of this release.
