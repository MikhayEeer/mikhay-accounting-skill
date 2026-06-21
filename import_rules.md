# Import Rules

Use `scripts/import_ledger.py` to convert third-party CSV/XLSX bills into the standard JSON ledger.

## Supported Inputs

- Standard Mikhay CSV: `时间, 收支类型, 金额, 类别, 子类, 账户, 备注, tags, note`
- Common CSV/XLSX exports from payment or bank tools, when columns can be mapped by name.

## Common Column Aliases

- 时间: `时间`, `交易时间`, `交易创建时间`, `付款时间`, `日期`, `交易日期`
- 收支类型: `收支类型`, `收/支`, `收支`, `类型`, `交易类型`
- 金额: `金额`, `金额(元)`, `金额（元）`, `交易金额`, `收入金额`, `支出金额`
- 类别: `类别`, `分类`, `一级分类`
- 子类: `子类`, `二级分类`
- 账户: `账户`, `支付方式`, `付款方式`, `收/付款方式`
- 备注: `备注`, `商品`, `商品说明`, `交易对方`, `商户`, `摘要`, `说明`

## Import Policy

- Preserve existing valid `类别/子类`.
- Normalize known aliases from `categories.md`.
- If no confident category is found, use `购物消费/日用百货` and append `待确认分类` to `note`.
- Use signed amount rules from `schema.md`: `支出` is negative; `收入`, `还款`, `转账` are positive.
- Do not overwrite existing ledger files unless the user asks.

## Commands

Single JSON:

```bash
python scripts/import_ledger.py raw/bill.csv --output data/imported.json
```

Split by month:

```bash
python scripts/import_ledger.py raw/bill.csv --split-by-month --output data/
```
