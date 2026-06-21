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

Write target accounts in `note` or `备注`, for example `target_account=花呗`.

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
