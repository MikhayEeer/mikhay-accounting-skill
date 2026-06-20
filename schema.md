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

For total asset records, use a separate JSON file if needed:

```json
{
  "asset_snapshots": [
    {"时间": "2026-06-30", "账户": "建设银行", "金额": 1000, "note": ""}
  ]
}
```

## Optional Repayment Reminder

For reminders, use a separate JSON file if needed:

```json
{
  "repayment_reminders": [
    {"时间": "2026-07-10", "账户": "白条", "金额": 500, "状态": "待还", "note": ""}
  ]
}
```
