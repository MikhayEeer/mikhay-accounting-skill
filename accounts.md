# Accounts And Assets

Use this file for account balances, liabilities, installment plans, and repayment reminders.

## Account Types

Asset accounts:

- `建设银行`
- `工商银行`
- `招商银行`
- `微信钱包`
- `支付宝`
- `美团`

Liability accounts:

- `白条`
- `花呗`
- `美团月付`
- `抖音月付`

## Asset Module Shape

Use these top-level arrays in JSON:

- `asset_snapshots`: account balance snapshots.
- `credit_accounts`: current credit account debt and limits.
- `installment_plans`: installment plan details.
- `repayment_reminders`: repayment reminders.

## Sync Rule

Ledger records affect asset balances:

- `支出`: decrease `账户` balance. For a liability account, this means the negative balance becomes larger.
- `收入`: increase `账户` balance.
- `还款`: decrease cash asset account and decrease liability account when the target liability is known.
- `转账`: move money between accounts only when source and destination are known.
- `退款`: increase the account the refund lands in. This is not income.
- `报销`: increase the account the reimbursement lands in. This is not income. Add the `报销` row and set the original expense to `已报销` only when the money arrives. Until then the pending amount stays in actual spending.
- `投资`: move money between a cash account and an investment account. Declare the investment account with `account_policy` as `资产` and `纳入=included` so it is part of net worth. Do not schedule market-price lookups. A market value exists only after the user asks to record an `asset_snapshots` row. Users who want a periodic update set their own scheduled task outside this skill.

Write target accounts in `note` or `备注`, for example `target_account=花呗`. A transfer can instead use two `pairid` legs with opposite signs.

## Included And Excluded

Each account is `included` or `excluded` (备查). Headline net worth uses included accounts only. The report prints excluded accounts in `备查账户`.

Default excluded accounts:

- `Apple Card` (负债)
- `公积金` (资产)
- `助学贷款` (负债)
- `加密货币` (资产)

Other accounts in the built-in list are included. Add or override accounts with `account_policy`, or set `纳入` on a snapshot.

## Credit-Card Snapshot Method

`scripts/summarize_assets.py --cc-method A|B` states which method it used.

- A, default: `最近快照+快照后新增`. Start at the latest snapshot dated on or before `--as-of`, then apply later ledger rows. This is the same rule as `scripts/project_assets.py`.
- B: `账本从零重放`. Credit cards ignore their snapshot and replay every ledger row from zero. Other accounts still use method A.

## Credit Mode

```json
{"credit_policy": {"mode": "debt_only"}}
```

`debt_only` is the default. The report prints debt, the repayment day, and total debt. It does not print blank `额度` or `可用额度`. `with_limit` also prints available credit and utilization, and warns when the limit is missing or the available credit disagrees with `额度 - 欠款` by more than 1.

A single `credit_accounts` entry may set `mode` and override the file.

## Investment Accounts

Add accounts such as `基金` or `证券` with `account_policy`. They are assets and included in net worth. The ledger stores net contributions. Floating profit is `snapshot market value - cumulative net contribution`, and it is printed only when a snapshot exists. There is no price feed and no built-in schedule.

## Forecast

```bash
python scripts/summarize_assets.py data/assets.json --forecast --as-of 2026-06-15
```

For each credit card the script prints the open-cycle statement and the previous-cycle repayment. Payday is the last Monday–Friday of that month. The cash-flow line is recorded income, minus cash spending on non-card accounts, minus card repayments due that month, minus net investment contributions when that amount is not zero. Card charges are not treated as cash leaving the bank until they are repaid. A missing bill day or repayment day is labeled `假定` (day 1 or day 10) instead of being applied quietly.

## Inferred Snapshot

Observed snapshots stay in `asset_snapshots`. Rebuild the inferred view from the latest observed balance plus later records:

```bash
python scripts/project_assets.py data/assets/assets.json data/ledger/2026/2026-06.json --write
```

Accounts with no observed baseline are listed and left out of the inferred total. Do not create an adjustment record unless the user asks.

Use positive balances for assets and negative balances for liabilities in `asset_snapshots`.

If a user directly edits asset module data and the new balance differs from ledger-derived balance:

1. Do not silently create a ledger item.
2. Report the difference.
3. Ask whether to create an adjustment record.

Default policy: ask every time before creating adjustment records.

## One-Command Query

```bash
python scripts/summarize_assets.py data/assets.json
```

Useful output:

- 总资产
- 总负债
- 净资产
- 各账户余额
- 信贷账户欠款
- 分期计划摘要
- 还款提醒
- 账本推演与资产快照差额
