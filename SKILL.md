---
slug: mikhay-accounting-skill
displayName: "Mikhay 记账"
version: 0.2.1
summary: "中文个人记账。流水、资产快照、信用卡和愿望清单分开存放；合计只抄脚本；退款不是收入。"
license: MIT
name: mikhay-accounting-skill
description: Chinese personal accounting workflow for CSV/JSON/XLSX ledger, asset, and wishlist files. Use when the user asks to import, export, record, classify, validate, summarize, store, analyze records, or evaluate planned purchases with fields like 时间, 收支类型, 金额, 类别, 子类, 账户, 备注, tags, note; supports 支出, 收入, 还款, 转账, 退款, trip/event/person/nature tags, day or month shards, refunds, transfer pairs, multi-currency CNY totals, included and excluded accounts, credit-card snapshot methods, payday forecast, third-party bill conversion, and monthly reports.
---

# Mikhay 记账

技能版本 `0.2.1`。账本字段 `schema_version` 仍是 `0.2.0`，那是数据格式号。合计必须来自脚本，never hand math。没跑脚本就不要报数字。

## 不做什么

- 不把退款记成收入，不把转账或还款记成花销。
- 购买前不把愿望清单写成 `支出`，也不替用户估价格。
- 不主动做预算、投资或消费建议。
- 不静默改分类、不覆盖已有分片、不在用户没要求时写差额调整。
- 不手算合计，不跳过范围内的分片。

取舍见 `references/design-rationale.md`。

## 30 秒上手

1. 没有 `data/` 时按 `storage.md` 建空目录，不要编造余额。
2. 改数据前读 `schema.md`；分类前读 `categories.md`。
3. `scripts/validate_ledger.py` 通过后再汇总。
4. 回复先给脚本总数，再给警告和下一步。

## 触发示例

原话决定模块。对话全文在 `references/triggers.md`。

1. 「午饭 35，微信」→ 记账 → `支出`，金额 `-35`，`食品餐饮/午餐`，账户 `微信钱包`。
2. 「昨天午饭退了 10」→ 记账 → `退款` `+10`，`refund_of` 指向原支出；不记收入。
3. 「支付宝还花呗 500」→ 记账 → `还款` `+500`，`note` 写 `target_account=花呗`。
4. 「建行转支付宝 200」→ 记账 → 两条 `转账`，同一 `pairid`，金额一负一正。
5. 「这个月花了多少」→ 汇总 → 只跑该月分片，报花销毛额、退款、净额。
6. 「导入这份支付宝账单」→ 导入 → `import_ledger.py` 后校验；已有分片先问再覆盖。
7. 「建行余额现在是 8000」→ 资产 → 追加快照；和推算不一致就先报差额。
8. 「想买机械键盘，399」→ 愿望清单 → 只写 wishlist，不写账本。
9. 「发薪日前花呗要还多少」→ 预测 → `summarize_assets.py --forecast`，写明算法和发薪日。
10. 「这次旅行花了多少」→ 标签 → `summarize_tags.py` 扫完全部分片，报毛额和净额。

## 常见陷阱

细节在 `references/faq.md`，恢复步骤在 `references/troubleshooting.md`。

- 退款写成了 `收入`。改成 `退款` 正数，不要进收入合计。
- `pairid` 只有一条。补上另一条，金额相反、账户不同；或改成单边并写 `target_account=`。
- 外币对不上。`金额` 用人民币，且等于 `original_amount * fx_rate`（误差 0.01 以内）。
- 类别不在枚举里。不要新造类别；备注写 `待确认`。导入才落到 `购物消费/日用百货`。
- 没有 `data/`、JSON 损坏，或同一账单导入了两次。先停写，说清原因，再问下一步。

## 错误处理

出错时不要只回「已记录」或「有问题」。说明类别、原因、卡住的字段或路径，以及下一步。完整分类见 `references/troubleshooting.md`。

- 缺字段：列出缺项并提问，不要用空字符串凑记录。
- 格式错误：指出哪个值和 `schema.md` 不符，并给出改后的样子。
- 校验失败：贴出 `INVALID` 的第一条原因，改完再跑 `validate_ledger.py`。
- 找不到文件：说明路径不存在。按 `storage.md` 建空目录，不要编余额。
- 文件损坏：引用 JSON 解析错误。保留坏文件，不覆盖；从 `raw/` 重导或请用户确认后再替换。
- 重试：校验和汇总可以重跑。导入和 `--write` 会写文件，输入没改或用户没同意覆盖时不要重跑。同一条 `INVALID` 重复出现就停。

## 按需阅读

- 字段和符号：`schema.md`。定位或写入分片：`storage.md`。
- 分类：`categories.md`。余额、信用卡、发薪日：`accounts.md`。
- 第三方账单：`import_rules.md`。愿望清单：`wishlist.md`。
- 常见错误：`references/faq.md`。报错和恢复：`references/troubleshooting.md`。
- 设计取舍：`references/design-rationale.md`。示例对话：`references/triggers.md`。
- 端到端：`examples/workflow-import-monthly.md`、`examples/workflow-credit-repay.md`、`examples/workflow-fix-records.md`。

## 脚本

- `scripts/summarize_ledger.py`：花销和内部转账。
- `scripts/summarize_tags.py`：标签合计，扫完整棵给定目录。
- `scripts/summarize_assets.py`：计入净资产、备查、`--cc-method`、`--forecast`。
- `scripts/project_assets.py`：最近快照加上之后的流水，得到推算余额。
- `scripts/validate_ledger.py`：相信文件之前先跑。
- `scripts/import_ledger.py <file> --shard month --year-dirs --output data/ledger`：转到标准 JSON。目标分片已存在时先问用户。
- `scripts/export_ledger.py`：导出 CSV。`scripts/analyze_wishlist.py`：购买压力。

## 数据规则

- `收支类型` 只接受 `支出`、`收入`、`还款`、`转账`、`退款`。
- `支出` 为负；`收入`、`还款`、`退款` 为正。成对转账一正一负。
- 花销净额 = 支出毛额减退款。内部转账每对只计一次。两套口径都要报。
- 缺币种即 `CNY`。合计只用人民币 `金额`。
- 标签用 `trip:`、`event:`、`person:`、`nature:`。裸标签只警告。
- 账户分 `included` 与 `excluded`（备查）。净资产分开打印。
- 信用卡默认方法 A（最近快照 + 快照后流水）。输出要写明算法。
- 新 JSON 写 `schema_version` `0.2.0`。旧文件没有该字段也有效。
- 直接改快照时，若和推算不一致，先报差额，再问要不要调整。

## 回复

- 先抄脚本总数，再写类别要点和占比。
- 查过资产就写明信用卡算法或发薪日。
- 警告和 `待确认` 单独列出。
- 失败时写原因和下一步，不要只做简短确认。
- 用户没要时不要倾倒全部流水。
