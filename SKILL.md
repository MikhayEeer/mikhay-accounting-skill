---
name: mikhay-accounting-skill
description: "Record Chinese expenses, income, repayments, and transfers; maintain observed and inferred asset snapshots and credit schedules; or update an independent wishlist. Use for transaction, balance, debt, credit bill, due-date, installment, wanted-item, and purchased-item messages. Return terse confirmations."
---

# Mikhay Accounting

Classify each message:

- **记账**: expense, income, completed repayment, or completed transfer.
- **资产**: observed balance or debt, credit bill, due date, installment, or asset query.
- **Wishlist**: wanted, purchased, or abandoned item.

Handle explicitly mixed messages module by module.

## 记账

- Append the record per `schema.md`.
- Use the current time when omitted. Ask one short question if another required value is unavailable.
- Rebuild `inferred_snapshot` as defined in `accounts.md`.
- Reply only with `{账户} {收支类型} {金额} {时间} {事件}{备注块}`.
- Let `data/preferences.json` override `assets/preferences.template.json`.

## 资产

- Apply reported balances per `accounts.md` and credit schedules per `credit.md`.

## Wishlist

- Update only the file defined in `wishlist.md`.
- On purchase, update the item and record an expense when transaction details are available.
- Reply only with the item and status.

Read `categories.md` only for categorization and `import_rules.md` only for third-party bill imports.
