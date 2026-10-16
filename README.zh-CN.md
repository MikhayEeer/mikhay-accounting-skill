[English](README.md) · [中文](README.zh-CN.md)

# Mikhay 记账技能

技能版本 `0.2.2`（见 `SKILL.md` frontmatter）。账本 `schema_version` 仍是 `0.2.0`。

安装：`npx skills add MikhayEeer/mikhay-accounting-skill`

主页：https://github.com/MikhayEeer/mikhay-accounting-skill

协议：MIT，版权人 MikhayEeer。全文见 [LICENSE](LICENSE)。

面向中文个人账本，处理 CSV、JSON、XLSX。给代理看的操作说明在 `SKILL.md`（中文）。常见错误见 `references/faq.md`，报错恢复见 `references/troubleshooting.md`。

显示名：`Mikhay 记账 - 资产管理/信用卡/预购清单/年月统计`。

## 隐私

本技能面向中文个人账本。流水、资产快照和愿望清单只留在本地的 `data/`、`raw/`、`exports/`。脚本不会上传账本。

## 导入导出

**重新导入可能丢数据。** `scripts/import_ledger.py` 默认拒绝覆盖已有账本文件，除非显式加上 `--overwrite`。任一目标路径已存在时，整批中止，一个文件都不写。脚本在写入前用 `Path.exists()` 检查。`--overwrite` 会整文件替换每个目标分片；新账单里没有的旧流水会从该文件消失。使用该标志前先备份 `data/`。这道门由脚本执行，不是只靠先问一句。

把 CSV 或 XLSX 导入为标准 JSON：

```bash
python scripts/import_ledger.py raw/bill.csv --output data/imported.json
```

按月拆分导入：

```bash
python scripts/import_ledger.py raw/bill.csv --split-by-month --year-dirs --output data/ledger
```

备份之后，才用 `--overwrite` 替换已有分片：

```bash
python scripts/import_ledger.py raw/bill.csv --shard month --year-dirs --output data/ledger --overwrite
```

把标准 JSON 导出为 CSV：

```bash
python scripts/export_ledger.py data/ledger/2026/2026-06.json --output exports/2026/2026-06.csv
```

真实账本推荐按年月分片：`data/ledger/YYYY/YYYY-MM.json`。按日分片：`data/ledger/YYYY/YYYY-MM/YYYY-MM-DD.json`。

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

## 资产

查询总资产、总负债、净资产、分期和还款提醒：

```bash
python scripts/summarize_assets.py data/assets/2026/2026-06.assets.json
```

记账会影响资产统计。直接改资产快照时，先报差额，再问要不要写调整分录。`project_assets.py --write` 只有带上该标志才会把推算视图写进资产文件。

## 预购清单

分析想买物品的经济压力、购买建议和优先级：

```bash
python scripts/analyze_wishlist.py data/wishlist/2026/wishlist.json --ledger data/ledger/2026/2026-06.json --assets data/assets/2026/2026-06.assets.json
```

预购清单不是账本记录。真正购买之后再写 `支出`。

## 维护者封装

`tools/package_skill.py` 只给维护者用，不是终端用户的记账命令。ClawHub 发布通过 `.clawhubignore` 忽略 `tools/`。打出来的压缩包本身也不含 `tools/` 和 `package_skill.py`。

```bash
python tools/package_skill.py
```

输出位置：

```text
dist/mikhay-accounting-skill.tar.gz
dist/mikhay-accounting-skill.zip
```

包内包含技能、参考文档、导入规则、`scripts/`、虚构示例、两份 README 和 `LICENSE`，不包含 `VERSION`、`tests/`、`.github/`、`tools/`、`data/`、`raw/`、`exports/`、`.claude/`、`.codex/`。`MANIFEST.json` 里的版本与 `SKILL.md` 的 `version` 相同。

## 使用 skill 与不使用 skill 的对比

以一份没有放进本仓库的本地样本，做一次本地（Claude Code，GLM-5.2）校验、月度统计、分类 Top 为例。下面的耗时和 token 是当时的量级，不是仓库里的示例文件。

| | 不使用 skill（纯 LLM 推理） | 使用 skill（脚本 + 短指令） |
|---|---|---|
| 输入 token | 需将 schema、类别表、规则口头说明给模型，或模型靠记忆推理，约 2–4k token 规则加上全量记录约 15k token | 先读 SKILL.md，再按需打开 schema、categories 或 references |
| 推理 token | 样本逐条分类、求和、别名归一化，输出长且易错，约 8–15k 输出 token | 几乎不推理，只发 2 条 Bash 命令 |
| 输出 token | 完整报表手写，约 1–2k | 脚本结果，约 300–500 token |
| 延迟 | 单轮 30s 到 1min 以上，多轮纠错更久 | 2 次 Bash 调用，约 3–8s |
| 准确性 | 求和与别名归一化经常出错，上百笔难一次算对 | 确定性正确，与对账文件完全一致 |
| 总 token | 约 25–35k | 约 3–5k |

## 结论

- Token：使用 skill 大约节省 5–8 倍，主要省在不必把规则塞进上下文、不必由模型逐条算账。
- 速度：使用 skill 快约 5–10 倍，从可能需要纠错 2–3 轮变为一次跑通。
- 质量：差距最大。纯 LLM 做金额求和与别名归一化，容易出现几百元误差；脚本是确定性的，零误差。

如需长期记账（录入新交易、按月出报表、查异常），建议把本 skill 放到对应工具支持的 skill 目录下，按「读 schema、跑 validate、跑 summarize、只回报脚本给出的总数与异常」执行。标签、分类占比和净资产都由脚本扫描全部分片后给出，不要手算。

测试：

```bash
python -m pytest -q
```
