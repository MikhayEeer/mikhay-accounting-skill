# Ledger Schema

Primary format: Chinese CSV or JSON.

## Main Record Fields

Use these 9 fields:

- `时间`: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`.
- `收支类型`: `支出`, `收入`, `还款`, `转账`.
- `金额`: signed number.
- `类别`: top category.
- `子类`: second-level category.
- `账户`: one account enum.
- `备注`: short description.
- `tags`: optional tag text or list.
- `note`: optional extra note.

Existing records may miss `tags` or `note`; treat them as empty.

## JSON Shape

Preferred monthly file:

```json
{
  "month": "2026-06",
  "records": []
}
```

A JSON list is also accepted and treated as records.

Preferred storage path: `data/ledger/YYYY/YYYY-MM.json`.

## Type Rules

- `支出`: 真实消费。
- `收入`: 真实收入。
- `还款`: 还负债；不混入普通支出统计。
- `转账`: 账户间移动；不计入收入或支出。

## Amount Sign Rules

- `支出`: 负数。
- `收入`: 正数。
- `还款`: 正数。
- `转账`: 正数。
- 统计展示时，`支出`、`还款`、`转账` 使用正数合计。

## Account Enums

Liability:

- `白条`
- `花呗`
- `美团月付`
- `抖音月付`

Asset:

- `建设银行`
- `工商银行`
- `招商银行`
- `微信钱包`
- `支付宝`
- `美团`

## Optional Asset Snapshot

For account balance snapshots:

```json
{
  "asset_snapshots": [
    {"时间": "2026-06-30", "账户": "建设银行", "账户类型": "资产", "金额": 1000, "currency": "CNY", "note": ""},
    {"时间": "2026-06-30", "账户": "花呗", "账户类型": "负债", "金额": -500, "currency": "CNY", "note": ""}
  ]
}
```

Rules:

- `资产`账户余额通常为正数。
- `负债`账户余额通常为负数，统计时按绝对值计入总负债。
- 直接修改资产快照时，默认先询问是否创建差额记账项，不自动补 item。

## Optional Credit Accounts

For credit account debt and limits:

```json
{
  "credit_accounts": [
    {"账户": "花呗", "欠款": 500, "额度": 5000, "可用额度": 4500, "账单日": 1, "还款日": 10, "状态": "active", "note": ""}
  ]
}
```

`账户` must be a liability account.

## Optional Installment Plans

For installment strategy:

```json
{
  "installment_plans": [
    {"id": "inst-001", "账户": "花呗", "本金": 1200, "总期数": 12, "已还期数": 3, "每期金额": 100, "下一还款日": "2026-07-10", "状态": "active", "note": ""}
  ]
}
```

## Optional Repayment Reminder

For reminders, use a separate JSON file if needed:

```json
{
  "repayment_reminders": [
    {"时间": "2026-07-10", "账户": "白条", "金额": 500, "状态": "待还", "installment_id": "", "note": ""}
  ]
}
```

## Asset Sync Rule

- `支出`: 资产账户减少；信贷账户负债增加。
- `收入`: 资产账户增加。
- `还款`: 付款账户减少；目标负债账户减少。目标账户写在 `note` 或 `备注`，如 `target_account=花呗`。
- `转账`: 来源账户减少；目标账户增加。目标账户同样用 `target_account=...`。
