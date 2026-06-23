# Wishlist

Use this module for things the user wants to buy but has not bought yet.

## Storage

Preferred path:

```text
data/wishlist/YYYY/wishlist.json
```

## Shape

```json
{
  "items": [
    {
      "名称": "机械键盘",
      "预计金额": 399,
      "类型": "数码",
      "优先级": "P2",
      "目标日期": "2026-07-15",
      "可延期": true,
      "使用频率": "每日",
      "替代方案": "继续使用现有键盘",
      "状态": "想买",
      "note": ""
    }
  ]
}
```

## Rules

- Wishlist items are plans, not ledger records.
- Do not create a `records` item before the purchase actually happens.
- Analyze pressure with recent ledger surplus, net assets, debt, and repayment reminders.
- After purchase, create a normal `支出` record and set wishlist `状态` to `已购买`.
- For uncertain value judgments, output `观望` instead of forcing a buy/no-buy answer.

## Command

```bash
python scripts/analyze_wishlist.py data/wishlist/2026/wishlist.json --ledger data/ledger/2026/2026-06.json --assets data/assets/2026/2026-06.assets.json
```

Useful output:

- 是否建议购买
- 经济压力
- 建议优先级
- 建议购买时间
- 主要原因
