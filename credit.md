# Credit

Store credit schedules at `data/credit/credit.json`:

```json
{
  "accounts": [
    {"账户": "花呗", "额度": 5000, "账单日": 1, "还款日": 10, "状态": "active"}
  ],
  "bills": [
    {"账户": "花呗", "账单月": "2026-07", "应还金额": 500, "到期日": "2026-08-10", "状态": "待还"}
  ],
  "installments": []
}
```

- Store bills, due dates, limits, and installments here.
- Store completed repayments in the ledger.
- Append reported debt balances to asset snapshots.
- Credit schedules alone do not change assets.
