# Ledger Schema

Primary format: Chinese CSV or JSON.

## Main Record Fields

Use these 9 fields. Extra fields documented below are optional, so older ledgers stay valid:

- `时间`: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`.
- `收支类型`: `支出`, `收入`, `还款`, `转账`, `退款`.
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
  "schema_version": "0.2.0",
  "month": "2026-06",
  "records": []
}
```

Files written by the scripts include `schema_version`. A missing `schema_version` is a legacy file and still validates.

A JSON list is also accepted and treated as records.

Preferred storage path: `data/ledger/YYYY/YYYY-MM.json`.

## Type Rules

- `支出`: 真实消费。
- `收入`: 真实收入。退款不是收入。
- `还款`: 还负债；不混入普通支出统计。
- `转账`: 账户间移动；不计入收入或支出。
- `退款`: 冲回一笔支出。可以只写 `收支类型=退款`，也可以再写 `refund_of` 指向原支出的 `id`。报表同时给出毛额和净额，退款不计入收入。

## Amount Sign Rules

- `支出`: 负数。
- `收入`: 正数。
- `还款`: 正数。
- `转账`: 旧的单边记录用正数。`pairid` 的两条腿一正一负。
- `退款`: 正数，表示钱退回来。
- 统计展示时，`支出`、`还款`、`转账` 使用正数合计。花销净额 = 支出毛额 - 退款。

## Account Enums

Liability, included:

- `白条`
- `花呗`
- `美团月付`
- `抖音月付`

Liability, excluded (备查) unless `account_policy` says otherwise:

- `Apple Card`
- `助学贷款`

Asset, included:

- `建设银行`
- `工商银行`
- `招商银行`
- `微信钱包`
- `支付宝`
- `美团`

Asset, excluded (备查) unless `account_policy` says otherwise:

- `公积金`
- `加密货币`

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
- `退款`: 原账户余额回升；信用卡欠款下降。退款不记成收入。

## Tags

Prefer namespaced tags. A record may carry more than one tag; each tag receives the full amount.

- `trip:` a trip, such as `trip:shanghai`
- `event:` an event, such as `event:wedding`
- `person:` a person, such as `person:li`
- `nature:` why the money moved, such as `nature:need`

Older bare tags such as `旅行` still load, with a warning. Any other `prefix:` is invalid.

`scripts/summarize_tags.py` is the only way to total tags. It reads every shard it is given.

## Refunds And Transfer Pairs

Optional record fields:

- `id`: stable id inside the validated file set.
- `refund_of`: id of the original `支出`.
- `pairid`: shared id of the two transfer legs.
- `target_account`: other account. `note` may still say `target_account=花呗`.

A `pairid` group must contain exactly two `转账` rows, with equal absolute amounts, opposite signs, and different accounts. Validate a directory when the legs live in different shards.

## Currency

Default currency is `CNY`. Optional columns:

- `currency`: 3-letter code, default `CNY`.
- `original_amount`: signed amount in `currency`.
- `fx_rate`: multiplier into CNY. `CNY` uses `1`.
- `cny_amount`: signed CNY amount. It must match `金额`.

`金额` stays the signed CNY amount used by every total. For a non-CNY row, `金额` must equal `original_amount * fx_rate` within 0.01.

## Account Inclusion

Accounts are `included` or `excluded` (备查). Excluded balances stay visible and stay out of headline net worth.

Built-in excluded accounts: `Apple Card`, `公积金`, `助学贷款`, `加密货币`. Override them with `account_policy` or a snapshot field `纳入`.

```json
{
  "account_policy": [
    {"账户": "公积金", "账户类型": "资产", "纳入": "excluded"}
  ]
}
```

`纳入` accepts `included` or `excluded`. `备查: true` also means excluded.
