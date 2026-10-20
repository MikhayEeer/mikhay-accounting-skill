"""v0.3 flows: reimbursement, investment, credit mode, and 0.2.0 compatibility.

Fixtures use fictional round amounts only.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ledgerlib import SCHEMA_VERSION
from test_ledger import ROOT, record, run, write_json
from validate_ledger import validate_book


def test_schema_version_constant_is_0_3() -> None:
    assert SCHEMA_VERSION == "0.3.0"


def test_legacy_sample_totals_and_validation_stay_put() -> None:
    summary = run("summarize_ledger.py", "examples/book.sample.json", "--as-of", "2026-10-19")
    assert summary.returncode == 0, summary.stdout + summary.stderr
    for line in (
        "- 记录数: 20",
        "- 收入: 2300.00",
        "- 支出: 1227.00",
        "- 花销毛额: 1227.00",
        "- 退款: 0.00",
        "- 已报销: 0.00",
        "- 待报销: 0.00",
        "- 花销净额: 1227.00",
        "- 还款: 500.00",
        "- 转账: 0.00",
        "- 内部转账: 0.00",
        "- 投资净投入: 0.00",
        "- 结余(不含还款): 1073.00",
        "- 现金流结余: 573.00",
        "- 花销口径: 毛额 1227.00, 退款 0.00, 净额 1227.00",
        "- 出行交通: 376.00 (30.64%)",
        "- 购物消费/数码: 300.00",
    ):
        assert line in summary.stdout
    assert "预计实际花销" not in summary.stdout
    pending = summary.stdout.split("## 待报销", 1)[1]
    assert "- 无" in pending

    checked = run("validate_ledger.py", "examples/book.sample.json")
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "收入/报销 is a legacy shape" in checked.stdout
    assert "unrecognized schema_version" not in checked.stdout
    assert "schema_version missing" not in checked.stdout

    assets = run("summarize_assets.py", "examples/assets.sample.json", "--as-of", "2026-06-30")
    assert assets.returncode == 0, assets.stdout + assets.stderr
    assert "- 净资产: 6600.00" in assets.stdout
    assert "- 总资产: 6800.00" in assets.stdout
    assert "- 备查净值: 0.00" in assets.stdout
    credit = assets.stdout.split("## 信贷账户", 1)[1].split("##", 1)[0]
    assert "欠款 100.00" in credit
    assert "额度" not in credit
    assert "可用" not in credit
    exposure = assets.stdout.split("## 信用敞口", 1)[1].split("##", 1)[0]
    assert "还款日 10" in exposure
    assert "- 总欠款: 100.00" in exposure
    assert "使用率" not in exposure


def test_accepted_schema_versions_do_not_warn() -> None:
    base = {"records": [record()], "asset_snapshots": [], "credit_accounts": []}
    for version in ("", "0.2.0", "0.3.0"):
        book = dict(base, schema_version=version)
        errors, warnings = validate_book(book, max_date=date(2026, 12, 31))
        assert errors == []
        assert not any("schema_version" in warning for warning in warnings)
    errors, warnings = validate_book(dict(base, schema_version="9.9.9"), max_date=date(2026, 12, 31))
    assert errors == []
    assert any("unrecognized schema_version" in warning for warning in warnings)


def test_reimbursement_reduces_spending_only_after_cash_arrives(tmp_path: Path) -> None:
    ledger = tmp_path / "2026-06.json"
    write_json(
        ledger,
        {
            "schema_version": "0.3.0",
            "month": "2026-06",
            "records": [
                record(id="meal", 时间="2026-05-01 12:00", 金额=-100, 备注="餐费", 报销状态="待报销", 预计报销=100),
                record(id="ride", 时间="2026-06-02 12:00", 金额=-40, 类别="出行交通", 子类="打车", 账户="支付宝", 备注="打车"),
                record(
                    id="back",
                    时间="2026-06-20 09:00",
                    收支类型="报销",
                    金额=30,
                    类别="报销",
                    子类="差旅",
                    账户="微信钱包",
                    备注="餐费报销一部分",
                    reimburse_of="meal",
                ),
                record(
                    id="old",
                    时间="2026-06-03 09:00",
                    收支类型="收入",
                    金额=50,
                    类别="收入",
                    子类="报销",
                    账户="建设银行",
                    备注="旧写法报销",
                ),
            ],
        },
    )
    checked = run("validate_ledger.py", str(ledger))
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "收入/报销 is a legacy shape" in checked.stdout
    summary = run("summarize_ledger.py", str(ledger), "--as-of", "2026-06-21")
    assert summary.returncode == 0, summary.stdout + summary.stderr
    assert "- 收入: 50.00" in summary.stdout
    assert "- 花销毛额: 140.00" in summary.stdout
    assert "- 已报销: 30.00" in summary.stdout
    assert "- 待报销: 70.00" in summary.stdout
    assert "- 花销净额: 110.00" in summary.stdout
    assert "预计实际花销" not in summary.stdout
    assert "- 食品餐饮: 70.00" in summary.stdout
    pending = summary.stdout.split("## 待报销", 1)[1]
    assert "餐费: 70.00" in pending
    assert "已等待 51 天" in pending
    assert "打车" not in pending


def test_reimburse_of_must_point_at_an_expense(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    write_json(
        bad,
        {
            "schema_version": "0.3.0",
            "records": [
                record(id="pay", 收支类型="收入", 金额=20, 类别="收入", 子类="工资", 账户="建设银行", 备注="工资"),
                record(
                    时间="2026-06-02 10:00",
                    收支类型="报销",
                    金额=20,
                    类别="报销",
                    子类="其他",
                    备注="指错了",
                    reimburse_of="pay",
                ),
            ],
        },
    )
    result = run("validate_ledger.py", str(bad))
    assert result.returncode == 1
    assert "reimburse_of target must be 支出" in result.stdout

    left = tmp_path / "a.json"
    right = tmp_path / "b.json"
    write_json(left, {"schema_version": "0.3.0", "records": [record(id="meal", 金额=-15, 备注="午饭", 报销状态="已报销")]})
    write_json(
        right,
        {
            "schema_version": "0.3.0",
            "records": [
                record(
                    时间="2026-06-08 10:00",
                    收支类型="报销",
                    金额=15,
                    类别="报销",
                    子类="其他",
                    备注="午饭报销",
                    reimburse_of="missing",
                )
            ],
        },
    )
    strict = run("validate_ledger.py", str(left), str(right))
    assert strict.returncode == 1
    assert "does not match a record id" in strict.stdout


def test_investment_is_net_worth_not_spending(tmp_path: Path) -> None:
    path = tmp_path / "assets.json"
    write_json(
        path,
        {
            "schema_version": "0.3.0",
            "account_policy": [{"账户": "基金", "账户类型": "资产", "纳入": "included"}],
            "asset_snapshots": [
                {"时间": "2026-06-01", "账户": "建设银行", "账户类型": "资产", "金额": 1000},
                {"时间": "2026-06-30", "账户": "基金", "账户类型": "资产", "金额": 120},
            ],
            "records": [
                record(
                    id="out",
                    时间="2026-06-10 09:00",
                    收支类型="投资",
                    金额=-100,
                    类别="投资",
                    子类="定投",
                    账户="建设银行",
                    备注="定投转出",
                    pairid="inv",
                ),
                record(
                    id="in",
                    时间="2026-06-10 09:01",
                    收支类型="投资",
                    金额=100,
                    类别="投资",
                    子类="定投",
                    账户="基金",
                    备注="定投转入",
                    pairid="inv",
                ),
                record(
                    id="back",
                    时间="2026-06-20 09:00",
                    收支类型="投资",
                    金额=40,
                    类别="投资",
                    子类="赎回",
                    账户="建设银行",
                    备注="赎回",
                    target_account="基金",
                ),
                record(时间="2026-06-11 09:00", 收支类型="收入", 金额=500, 类别="收入", 子类="工资", 账户="建设银行", 备注="工资"),
            ],
        },
    )
    checked = run("validate_ledger.py", str(path))
    assert checked.returncode == 0, checked.stdout + checked.stderr
    summary = run("summarize_ledger.py", str(path))
    assert summary.returncode == 0, summary.stdout + summary.stderr
    assert "- 收入: 500.00" in summary.stdout
    assert "- 花销净额: 0.00" in summary.stdout
    assert "- 投资净投入: 60.00" in summary.stdout
    assert "- 现金流结余: 440.00" in summary.stdout

    assets = run("summarize_assets.py", str(path), "--as-of", "2026-06-30")
    assert assets.returncode == 0, assets.stdout + assets.stderr
    included = assets.stdout.split("## 计入净资产", 1)[1].split("##", 1)[0]
    assert "基金" in included
    assert "净资产: 1560.00" in assets.stdout.split("## 汇总", 1)[1].split("##", 1)[0]
    assert "备查账户" in assets.stdout
    assert "基金" not in assets.stdout.split("## 备查账户", 1)[1].split("##", 1)[0]
    invest = assets.stdout.split("## 投资", 1)[1].split("##", 1)[0]
    assert "投资净投入: 60.00" in invest
    assert "基金: 快照市值 120.00, 累计净投入 60.00, 浮动盈亏 60.00" in invest
    assert "不查行情" in invest
    assert "建设银行:" not in invest


def test_investment_without_snapshot_skips_market_pnl(tmp_path: Path) -> None:
    path = tmp_path / "cash.json"
    write_json(
        path,
        {
            "schema_version": "0.3.0",
            "account_policy": [{"账户": "证券", "账户类型": "资产"}],
            "asset_snapshots": [{"时间": "2026-06-01", "账户": "招商银行", "账户类型": "资产", "金额": 800}],
            "records": [
                record(
                    时间="2026-06-02 09:00",
                    收支类型="投资",
                    金额=-200,
                    类别="投资",
                    子类="证券入金",
                    账户="招商银行",
                    备注="入金",
                    target_account="证券",
                )
            ],
        },
    )
    assets = run("summarize_assets.py", str(path), "--as-of", "2026-06-30", "--forecast")
    assert assets.returncode == 0, assets.stdout + assets.stderr
    assert "无市值快照，不估算浮动盈亏" in assets.stdout
    assert "浮动盈亏" not in assets.stdout.split("无市值快照", 1)[0].split("## 投资", 1)[-1]
    assert "本月现金流: 收入 0.00 - 现金花销净额 0.00 - 预计还款 0.00 - 投资净投入 200.00 = -200.00" in assets.stdout
    included = assets.stdout.split("## 计入净资产", 1)[1].split("##", 1)[0]
    assert "证券" not in included


def test_credit_modes_and_assumed_cycle_days(tmp_path: Path) -> None:
    path = tmp_path / "cards.json"
    write_json(
        path,
        {
            "schema_version": "0.3.0",
            "credit_policy": {"mode": "debt_only"},
            "asset_snapshots": [
                {"时间": "2026-06-01", "账户": "建设银行", "账户类型": "资产", "金额": 100},
                {"时间": "2026-06-01", "账户": "花呗", "账户类型": "负债", "金额": 0},
                {"时间": "2026-06-01", "账户": "白条", "账户类型": "负债", "金额": 0},
            ],
            "credit_accounts": [
                {"账户": "花呗", "欠款": 80, "额度": 5000, "可用额度": 4900},
                {"账户": "白条", "欠款": 50, "mode": "with_limit", "额度": 200, "可用额度": 100},
            ],
        },
    )
    checked = run("validate_ledger.py", str(path))
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "differs from 额度-欠款" in checked.stdout
    shown = run("summarize_assets.py", str(path), "--as-of", "2026-06-15", "--forecast")
    assert shown.returncode == 0, shown.stdout + shown.stderr
    credit = shown.stdout.split("## 信贷账户", 1)[1].split("##", 1)[0]
    huabei = next(line for line in credit.splitlines() if "花呗" in line)
    assert huabei == "- 花呗: 欠款 80.00, 计入"
    assert "白条: 欠款 50.00, 额度 200, 可用 100, 计入" in credit
    exposure = shown.stdout.split("## 信用敞口", 1)[1].split("##", 1)[0]
    assert "花呗: 欠款 80.00, 还款日 未填" in exposure
    assert "- 总欠款: 130.00" in exposure
    assert "相差超过 1 元" in exposure
    assert "假定账单日" in shown.stdout
    assert "假定还款日" in shown.stdout
    assert "未填账单日，假定为 1 日" in shown.stdout

    missing_limit = tmp_path / "limit.json"
    write_json(
        missing_limit,
        {
            "schema_version": "0.3.0",
            "credit_policy": {"mode": "with_limit"},
            "credit_accounts": [{"账户": "花呗", "欠款": 10}],
        },
    )
    warned = run("validate_ledger.py", str(missing_limit))
    assert warned.returncode == 0, warned.stdout + warned.stderr
    assert "with_limit mode is missing 额度" in warned.stdout


def test_migrate_preview_lists_rows_and_apply_is_refused(tmp_path: Path) -> None:
    ledger = tmp_path / "2026-06.json"
    write_json(
        ledger,
        {
            "schema_version": "0.2.0",
            "records": [
                record(
                    时间="2026-06-01 09:00",
                    收支类型="收入",
                    金额=80,
                    类别="收入",
                    子类="报销",
                    账户="微信钱包",
                    备注="旧报销",
                ),
                record(时间="2026-06-02 09:00", 金额=-100, 账户="招商银行", 备注="基金定投"),
            ],
        },
    )
    before = ledger.read_text(encoding="utf-8")
    preview = run("migrate_0_3.py", str(ledger))
    assert preview.returncode == 0, preview.stdout + preview.stderr
    assert "收入/报销" in preview.stdout
    assert "旧报销" in preview.stdout
    assert "投资候选[定投]" in preview.stdout or "投资候选[基金]" in preview.stdout
    assert "未改写任何文件" in preview.stdout
    refused = run("migrate_0_3.py", str(ledger), "--apply")
    assert refused.returncode == 2
    assert "拒绝自动迁移" in refused.stderr
    assert ledger.read_text(encoding="utf-8") == before
    assert not list(tmp_path.glob("data.bak-*"))


def test_examples_with_explicit_0_2_0_still_validate() -> None:
    sample = ROOT / "examples" / "ledger.extended.sample.json"
    payload = json.loads(sample.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "0.2.0"
    result = run("validate_ledger.py", str(sample))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "unrecognized schema_version" not in result.stdout
