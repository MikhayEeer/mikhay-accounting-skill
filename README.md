# Mikhay Accounting Skill

Chinese personal accounting workflow for CSV/JSON ledger files.

## 导入导出

导入 CSV/XLSX 到标准 JSON：

```bash
python scripts/import_ledger.py raw/bill.csv --output data/imported.json
```

按月拆分导入：

```bash
python scripts/import_ledger.py raw/bill.csv --split-by-month --year-dirs --output data/ledger
```

导出标准 JSON 到 CSV：

```bash
python scripts/export_ledger.py data/ledger/2026/2026-06.json --output exports/2026/2026-06.csv
```

推荐真实账本按年月分片：`data/ledger/YYYY/YYYY-MM.json`。按日分片：`data/ledger/YYYY/YYYY-MM/YYYY-MM-DD.json`。

```bash
python scripts/import_ledger.py raw/bill.csv --shard day --year-dirs --output data/ledger
python scripts/import_ledger.py raw/bill.csv --shard month --year-dirs --output data/ledger
```

分片键只用文件名（`os.path.basename`）。`data/ledger/2026/2026-06.json` 的月份键是 `2026-06`。不要截取整段路径，否则会得到错误键 `r/202`。

校验：

```bash
python scripts/validate_ledger.py data/ledger/2026/2026-06.json
python scripts/validate_ledger.py data/ledger
```

## 花销与内部转账

统计一律跑脚本，不要手算。脚本会扫描传入的全部分片。

```bash
python scripts/summarize_ledger.py data/ledger
python scripts/summarize_ledger.py data/ledger --buckets examples/buckets.sample.json
python scripts/summarize_tags.py data/ledger
```

两套口径：

- **花销**：支出毛额减去退款。退款（`收支类型=退款` 或 `refund_of`）不是收入，也不算一笔新的消费。报表同时给出毛额和净额。
- **内部转账**：账户之间的 `转账`。`pairid` 成对的两条腿只计一次。转账不进入花销。

标签使用 `trip:`、`event:`、`person:`、`nature:`。`summarize_tags.py` 对每个标签给出毛额、净额、按日合计，以及类别行上的占比。

可选字段还包括 `currency`（默认 CNY）、`original_amount`、`fx_rate`、`cny_amount`。合计使用人民币 `金额`。新写出的 JSON 带 `schema_version`。旧账本没有这些字段也能用。

## 净资产、信用卡与发薪日

```bash
python scripts/summarize_assets.py data/assets/2026/2026-06.assets.json --cc-method A
python scripts/summarize_assets.py data/assets/2026/2026-06.assets.json --forecast --as-of 2026-06-15
python scripts/project_assets.py data/assets/assets.json data/ledger/2026/2026-06.json
```

账户有 `included` 和 `excluded`（备查）两种。净资产分成「计入净资产」和「备查账户」两段。备查示例：Apple Card、公积金、助学贷款、加密货币。

信用卡余额默认用方法 A：最近快照 + 快照之后的流水。方法 B 从零重放该卡流水、不用快照。输出会写明用的是哪一种。

`--forecast` 给出每张卡的预计账单和预计还款，并对照发薪日现金流。发薪日是当月最后一个工作日（周一至周五）。

## 资产模块

查询总资产、总负债、净资产、分期和还款提醒：

```bash
python scripts/summarize_assets.py data/assets/2026/2026-06.assets.json
```

记账会影响资产统计；直接改资产快照时，默认先询问是否创建差额记账项。

## 预购清单

分析想买物品的经济压力、购买建议和优先级：

```bash
python scripts/analyze_wishlist.py data/wishlist/2026/wishlist.json --ledger data/ledger/2026/2026-06.json --assets data/assets/2026/2026-06.assets.json
```

预购清单不是账本记录，真正购买后再生成 `支出` item。

## 一键封装

生成给其他 Agent 使用的离线包：

```bash
python scripts/package_skill.py
```

输出位置：

```text
dist/mikhay-accounting-skill.tar.gz
dist/mikhay-accounting-skill.zip
```

包内只包含 skill、导入规则、脚本和脱敏示例，不包含 `data/`、`raw/`、`exports/`、`.claude/`、`.codex/` 等真实数据或本地配置。

## 记账场景：使用 skill 与不使用 skill 的对比

以处理 197 条真实记录（2026-05 与 2026-06 两个月）做一次本地(ClaudeCode GLM-5.2)校验、月度统计、分类 Top 为例。

| 维度 | 不使用 skill（纯 LLM 推理） | 使用 skill（脚本 + 短指令） |
|---|---|---|
| 输入 token | 需将 schema、类别表、规则口头说明给模型，或模型靠记忆推理，约 2-4k token 规则加上全量记录约 15k token | 只读 SKILL.md（约 400 token），按需读 schema 与 categories（约 1k） |
| 推理 token | 197 条逐条分类、求和、别名归一化，输出长且易错，约 8-15k 输出 token | 几乎不推理，只发 2 条 Bash 命令 |
| 输出 token | 完整报表手写，约 1-2k | 脚本结果，约 300-500 token |
| 延迟 | 单轮 30s 到 1min 以上，多轮纠错更久 | 2 次 Bash 调用，约 3-8s |
| 准确性 | 求和与别名归一化经常出错，197 笔难一次算对 | 确定性正确，与对账文件完全一致 |
| 总 token | 约 25-35k | 约 3-5k |

## 结论

- Token：使用 skill 大约节省 5-8 倍，主要省在不必把规则塞进上下文、不必由模型逐条算账。
- 速度：使用 skill 快约 5-10 倍，从可能需要纠错 2-3 轮变为一次跑通。
- 质量：差距最大。纯 LLM 处理 197 笔金额求和与别名归一化，容易出现几百元误差；脚本是确定性的，零误差。

如需长期记账（录入新交易、按月出报表、查异常），建议把本 skill 放到对应工具支持的 skill/配置目录下，按「读 schema、跑 validate、跑 summarize、只回报脚本给出的总数与异常」执行。标签、分类占比和净资产都由脚本扫描全部分片后给出，不要手算。

测试：

```bash
python -m pytest -q
```
