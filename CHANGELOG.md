# Changelog

## 0.3.0 - 2026-10-19

Ledger `schema_version` is `0.3.0`. Skill version is `0.3.0`. `slug` stays `mikhay-accounting-skill`. `displayName` is unchanged. There is still no `VERSION` file.

Unedited `0.2.0` books still validate, and their totals stay the same. Empty `schema_version`, `0.2.0`, and `0.3.0` are accepted. Other versions still warn.

### Added

- `收支类型=报销`, with `reimburse_of`, `报销状态`, and `预计报销`. Actual spending is gross expense minus refunds minus reimbursements that have arrived. Pending reimbursement stays in actual spending and is listed with its age. There is no projected-spending line. A reimbursement is not income.
- `收支类型=投资`. Net investment is separate from spending and income. Investment accounts added with `account_policy` count toward net worth. Floating profit is printed only from a snapshot the user asked to record. The skill does not fetch prices and does not schedule market updates.
- `credit_policy.mode`: `debt_only` (default) or `with_limit`. Reports include a credit-exposure section. Forecast labels an assumed bill day or repayment day instead of using one quietly.
- `scripts/lint_ledger.py` (read-only): near-duplicates, alias windows, missing fixed expenses, and a monthly coverage report. `data/aliases.json` and `data/recurring.json` are optional inputs.
- `data/items/items.json` and `scripts/summarize_items.py` for subscriptions and belongings. Residual value is printed at the end of the asset report and is not added to assets, net worth, or the excluded-account total.
- Wishlist fields `加入日期`, `冷静天数`, `目标价`, `放弃原因`, `额度桶`, and `record_id`, plus top-level `budget_buckets` and `analyze_wishlist.py --due`.
- `scripts/migrate_0_3.py` prints legacy `收入/报销` rows and investment keyword candidates. `--apply` is refused. Historical rows are not rewritten.

### Compatibility

- A legacy `收入/报销` row still counts as income and produces a warning. Whether to edit it is the user's decision.
- New types and files are optional. An agent that sees the old reimbursement shape should say so and wait for the user.

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
