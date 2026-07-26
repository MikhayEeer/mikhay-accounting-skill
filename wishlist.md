# Wishlist

Store it independently at `data/wishlist/wishlist.json`:

```json
{
  "items": [
    {"名称": "机械键盘", "状态": "想买", "备注": ""}
  ]
}
```

Only `名称` is required; `状态` defaults to `想买`.

- Store `预计金额` only when provided.
- Optional: `备注`, `目标日期`, `链接`, `规格`, `数量`.
- Do not infer prices, consult financial data, or give unsolicited advice.
- Do not create ledger or asset entries before purchase.
