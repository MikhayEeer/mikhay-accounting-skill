# Ledger

Store monthly records at `data/ledger/YYYY/YYYY-MM.json`.

```json
{
  "month": "2026-07",
  "records": [
    {
      "时间": "2026-07-26 12:30",
      "收支类型": "支出",
      "金额": -25,
      "账户": "微信钱包",
      "事件": "午饭",
      "备注": "和同事"
    }
  ]
}
```

Required: `时间`, `收支类型`, `金额`, `账户`, `事件`.

- `收支类型`: `支出`, `收入`, `还款`, or `转账`.
- Use negative amounts for expenses and positive amounts otherwise.
- Add `target_account` to repayments and transfers for asset inference.
- Optional legacy/import fields: `类别`, `子类`, `tags`, `note`, `id`.
- Accept legacy records that use `备注` as `事件`.

Balance effects:

- Expense: decrease the source asset or increase its liability.
- Income: increase the account.
- Repayment: decrease the source asset and liability.
- Transfer: decrease the source and increase `target_account`.
