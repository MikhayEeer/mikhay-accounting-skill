# Assets

Store observed history and the current inference in `data/assets/assets.json`:

```json
{
  "asset_snapshots": [
    {"时间": "2026-07-25 20:00", "账户": "建设银行", "账户类型": "资产", "余额": 5000}
  ],
  "inferred_snapshot": {
    "时间": "2026-07-26 12:30",
    "类型": "推理",
    "账户余额": [],
    "总资产": 5000,
    "总负债": 0,
    "净资产": 5000,
    "未建立基线账户": []
  }
}
```

- Append observed snapshots; never overwrite history.
- Use positive asset balances and negative liability balances. Accept legacy field `金额` as `余额`.
- Infer each account from its latest observed snapshot plus later ledger items.
- Exclude accounts without an observed baseline from totals and list them in `未建立基线账户`.
- Replace `inferred_snapshot` after each ledger or observed-balance update.
- Do not create adjustment records unless requested.

```bash
python scripts/project_assets.py data/assets/assets.json <ledger.json> [<ledger.json> ...] --write
```
