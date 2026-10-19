# Ledger Schema

Primary format: Chinese CSV or JSON.

## Main Record Fields

Use these 9 fields. Extra fields documented below are optional, so older ledgers stay valid:

- `时间`: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM`.
- `收支类型`: `支出`, `收入`, `还款`, `转账`, `退款`, `报销`, `投资`.
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
  "schema_version": "0.3.0",
  "month": "2026-06",
  "records": []
}
```

Files written by the scripts include `schema_version` `0.3.0`. A missing `schema_version`, `0.2.0`, and `0.3.0` all validate with no version warning. Any other value warns and still loads. New fields below are optional, so an unedited 0.2.0 book stays valid and its totals stay the same.

A JSON list is also accepted and treated as records.

Preferred storage path: `data/ledger/YYYY/YYYY-MM.json`.

## Type Rules

- `支出`: 真实消费。
- `收入`: 真实收入。退款不是收入。
- `还款`: 还负债；不混入普通支出统计。
- `转账`: 账户间移动；不计入收入或支出。
- `退款`: 冲回一笔支出。可以只写 `收支类型=退款`，也可以再写 `refund_of` 指向原支出的 `id`。报表同时给出毛额和净额，退款不计入收入。
- `报销`: 报销到账。金额为正，不计入收入。可选 `reimburse_of` 指向原 `支出` 的 `id`，校验方式和 `refund_of` 相同。指到原支出时，金额冲回那个类别。
- `投资`: 现金和投资账户之间的移动。不进花销，不进收入。成对记录和转账一样，同一个 `pairid`，一正一负；只记得一边时写 `target_account=`。赎回方向相反。报表单列「投资净投入 = 投入 − 赎回」。

## Amount Sign Rules

- `支出`: 负数。
- `收入`: 正数。
- `还款`: 正数。
- `转账`: 旧的单边记录用正数。`pairid` 的两条腿一正一负。
- `退款`: 正数，表示钱退回来。
- `报销`: 正数，表示报销款回到原账户。
- `投资`: 成对记录一正一负。单边投入在现金账户用负数，单边赎回在现金账户用正数。
- 统计展示时，`支出`、`还款`、`转账` 使用正数合计。实际花销 = 支出毛额 − 退款 − 已报销。待报销的钱仍算在实际花销里，到账并写成 `报销` 之后才扣减。不另报「预计实际花销」。旧的 `收入/报销` 不改写，仍然算收入，校验只给警告。

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

`credit_policy.mode` is `debt_only` (default) or `with_limit`. A `credit_accounts` row may set `mode` to override the file. `debt_only` reports debt and the repayment day, and does not print empty limits. `with_limit` warns when `额度` is missing, and when `可用额度` differs from `额度 − 欠款` by more than 1.

Forecast does not invent a silent bill day or repayment day. A missing `账单日` is reported as assumed day 1, and a missing `还款日` as assumed day 10.

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
- `报销`: 原账户余额回升；不记成收入。到账时新增一条 `报销`，`reimburse_of` 指向原支出，并把原支出的 `报销状态` 改为 `已报销`。在那之前，`待报销` 仍算实际花销。
- `投资`: 和成对转账一样移动余额。投资账户用 `account_policy` 声明为资产且 `纳入=included`，计入净资产。市值只来自用户主动写入的 `asset_snapshots`，不查行情，也不做定时更新。有快照时才打印「浮动盈亏 = 快照市值 − 累计净投入」。

## Tags

Prefer namespaced tags. A record may carry more than one tag; each tag receives the full amount.

- `trip:` a trip, such as `trip:demo`
- `event:` an event, such as `event:demo`
- `person:` a person, such as `person:demo`
- `nature:` why the money moved, such as `nature:need`

Older bare tags such as `旅行` still load, with a warning. Any other `prefix:` is invalid.

`scripts/summarize_tags.py` is the only way to total tags. It reads every shard it is given.

## Refunds And Transfer Pairs

Optional record fields:

- `id`: stable id inside the validated file set.
- `refund_of`: id of the original `支出`.
- `reimburse_of`: id of the original `支出`. Only on `报销`.
- `报销状态`: on an `支出`, one of `待报销`, `已报销`, `不报销`. Missing means `不报销`.
- `预计报销`: amount still expected back. Missing means the whole expense. Used only to list 待报销, not to reduce 实际花销.
- `pairid`: shared id of the two transfer or investment legs.
- `target_account`: other account. `note` may still say `target_account=花呗`.

`scripts/migrate_0_3.py` only prints a preview of legacy `收入/报销` rows and investment keyword candidates. It does not accept `--apply`. Do not rewrite historical rows unless the user asks.

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
