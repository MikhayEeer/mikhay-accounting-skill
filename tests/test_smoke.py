from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from project_assets import project  # noqa: E402
from package_skill import collect_files  # noqa: E402
from validate_ledger import validate_records  # noqa: E402
from validate_wishlist import validate  # noqa: E402


class AccountingSmokeTests(unittest.TestCase):
    def test_compact_ledger_record_is_valid(self) -> None:
        errors, _ = validate_records(
            [{"时间": "2026-07-26 12:30", "收支类型": "支出", "金额": -25, "账户": "微信钱包", "事件": "午饭"}]
        )
        self.assertEqual(errors, [])

    def test_ledger_event_is_required(self) -> None:
        errors, _ = validate_records(
            [{"时间": "2026-07-26 12:30", "收支类型": "支出", "金额": -25, "账户": "微信钱包"}]
        )
        self.assertTrue(any("事件" in error for error in errors))

    def test_wishlist_does_not_require_price(self) -> None:
        self.assertEqual(validate([{"名称": "机械键盘", "状态": "想买"}]), [])
        self.assertTrue(validate([{"名称": "机械键盘", "预计金额": "未知"}]))

    def test_assets_start_from_observed_snapshots(self) -> None:
        assets = {
            "asset_snapshots": [
                {"时间": "2026-07-01 00:00", "账户": "建设银行", "账户类型": "资产", "余额": 1000},
                {"时间": "2026-07-01 00:00", "账户": "花呗", "账户类型": "负债", "余额": -200},
            ]
        }
        records = [
            {"时间": "2026-07-02 10:00", "收支类型": "支出", "金额": -100, "账户": "建设银行", "事件": "餐饮"},
            {"时间": "2026-07-03 10:00", "收支类型": "收入", "金额": 300, "账户": "建设银行", "事件": "报销"},
            {"时间": "2026-07-04 10:00", "收支类型": "还款", "金额": 50, "账户": "建设银行", "target_account": "花呗", "事件": "还款"},
            {"时间": "2026-07-05 10:00", "收支类型": "支出", "金额": -20, "账户": "微信钱包", "事件": "饮料"},
        ]
        inferred = project(assets, records, datetime.fromisoformat("2026-07-05 23:59"))
        balances = {row["账户"]: row["余额"] for row in inferred["账户余额"]}
        self.assertEqual(balances, {"建设银行": 1150, "花呗": -150})
        self.assertEqual(inferred["净资产"], 1000)
        self.assertEqual(inferred["未建立基线账户"], ["微信钱包"])

    def test_default_reply_template(self) -> None:
        config = json.loads((ROOT / "assets" / "preferences.template.json").read_text(encoding="utf-8"))
        self.assertEqual(config["ledger_reply_template"], "{账户} {收支类型} {金额} {时间} {事件}{备注块}")

    def test_core_skill_stays_concise(self) -> None:
        lines = [line for line in (ROOT / "SKILL.md").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertLessEqual(len(lines), 30)

    def test_package_scope_and_version(self) -> None:
        names = {path.as_posix() for path in collect_files(ROOT)}
        self.assertTrue({"VERSION", "SKILL.md", "credit.md", "assets/preferences.template.json"} <= names)
        self.assertFalse({"tests/test_smoke.py", "examples/book.sample.json", "data/private.json", "packages/output.zip"} & names)
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "0.1.0")


if __name__ == "__main__":
    unittest.main()
