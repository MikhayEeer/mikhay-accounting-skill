"""v0.4.0: configurable categories, configurable accounts with aliases, and zero-amount netting.

Fixtures use fictional round amounts only.
"""

from __future__ import annotations

import json
from pathlib import Path

from test_ledger import run, record, write_json


def write_json_file(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_zero_amount_is_valid_and_netting_stays_one_item(tmp_path: Path) -> None:
    ledger = tmp_path / "2026-06.json"
    write_json(
        ledger,
        {
            "schema_version": "0.3.0",
            "records": [
                record(id="flight", 金额=0, 类别="出行交通", 子类="飞机", 账户="支付宝", 备注="机票全额报销后净额"),
                record(id="meal", 时间="2026-06-02 10:00", 金额=-50, 备注="午饭"),
                record(
                    id="bonus",
                    时间="2026-06-03 10:00",
                    收支类型="收入",
                    金额=20,
                    类别="收入",
                    子类="补贴",
                    账户="招商银行",
                    备注="报销多出 20",
                ),
            ],
        },
    )
    checked = run("validate_ledger.py", str(ledger))
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "cannot be zero" not in checked.stdout

    summary = run("summarize_ledger.py", str(ledger))
    assert summary.returncode == 0, summary.stdout + summary.stderr
    assert "- 收入: 20.00" in summary.stdout
    assert "- 支出: 50.00" in summary.stdout
    assert "- 花销净额: 50.00" in summary.stdout
    assert "- 记录数: 3" in summary.stdout


def test_custom_categories_are_only_a_recommendation(tmp_path: Path) -> None:
    categories = write_json_file(
        tmp_path / "custom-categories.json",
        {"categories": {"宠物": ["猫粮", "疫苗"]}, "subcategory_aliases": {"猫食": "猫粮"}},
    )
    ledger = tmp_path / "2026-06.json"
    write_json(ledger, {"schema_version": "0.3.0", "records": [record(类别="宠物", 子类="猫食", 金额=-30)]})

    without = run("validate_ledger.py", str(ledger))
    assert without.returncode == 0, without.stdout + without.stderr
    assert "不在类别表" in without.stdout

    configured = run("validate_ledger.py", str(ledger), "--categories", str(categories))
    assert configured.returncode == 0, configured.stdout + configured.stderr
    assert "不在类别表" not in configured.stdout

    strict = run("validate_ledger.py", str(ledger), "--strict")
    assert strict.returncode == 1
    assert "不在类别表" in strict.stdout


def test_custom_accounts_and_aliases(tmp_path: Path) -> None:
    accounts = write_json_file(
        tmp_path / "custom-accounts.json",
        {
            "accounts": [
                {"账户": "测试钱包", "别名": ["测试", "test-wallet"], "账户类型": "资产"},
                {"账户": "我的花呗", "别名": ["花呗"], "账户类型": "负债", "信用卡": True},
            ]
        },
    )
    ledger = tmp_path / "2026-06.json"
    write_json(
        ledger,
        {
            "schema_version": "0.3.0",
            "records": [
                record(账户="测试", 金额=-30, 备注="猫粮"),
                record(时间="2026-06-02 10:00", 账户="花呗", 金额=-20, 备注="还款前消费"),
            ],
        },
    )

    without = run("validate_ledger.py", str(ledger))
    assert without.returncode == 0, without.stdout + without.stderr
    assert "不在账户表" in without.stdout

    configured = run("validate_ledger.py", str(ledger), "--accounts", str(accounts))
    assert configured.returncode == 0, configured.stdout + configured.stderr
    assert "不在账户表" not in configured.stdout
    assert "账户别名" in configured.stdout
    assert "测试钱包" in configured.stdout

    strict = run("validate_ledger.py", str(ledger), "--strict")
    assert strict.returncode == 1


def test_custom_liability_account_is_not_blocked_in_credit_section(tmp_path: Path) -> None:
    accounts = write_json_file(
        tmp_path / "custom-accounts.json",
        {"accounts": [{"账户": "我的花呗", "账户类型": "负债", "信用卡": True}]},
    )
    assets = tmp_path / "assets.json"
    write_json(
        assets,
        {
            "schema_version": "0.3.0",
            "credit_accounts": [{"账户": "我的花呗", "欠款": 100, "账单日": 1, "还款日": 10}],
            "repayment_reminders": [{"时间": "2026-07-10", "账户": "我的花呗", "金额": 100, "状态": "待还"}],
        },
    )
    ok = run("validate_ledger.py", str(assets), "--accounts", str(accounts))
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "应为负债账户" not in ok.stdout

    plain = run("validate_ledger.py", str(assets))
    assert plain.returncode == 0, plain.stdout + plain.stderr
    assert "不在账户表" in plain.stdout


def test_import_uses_account_aliases_and_custom_categories(tmp_path: Path) -> None:
    accounts = write_json_file(
        tmp_path / "custom-accounts.json",
        {"accounts": [{"账户": "招行储蓄", "别名": ["招行"], "账户类型": "资产"}]},
    )
    categories = write_json_file(tmp_path / "categories.json", {"categories": {"宠物": ["猫粮"]}})
    bill = tmp_path / "bill.csv"
    bill.write_text(
        "时间,收支类型,金额,类别,子类,账户,备注\n"
        "2026-06-05 10:00,支出,20,宠物,猫粮,招行,猫粮\n",
        encoding="utf-8",
    )
    out = tmp_path / "imported.json"
    result = run(
        "import_ledger.py",
        str(bill),
        "--output",
        str(out),
        "--accounts",
        str(accounts),
        "--categories",
        str(categories),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = read_json(out)
    assert payload["records"][0]["账户"] == "招行储蓄"
    assert payload["records"][0]["类别"] == "宠物"


def test_bom_prefixed_config_still_loads(tmp_path: Path) -> None:
    accounts = tmp_path / "custom-accounts.json"
    accounts.write_text(
        '\ufeff{"accounts": [{"账户": "现金", "账户类型": "资产"}]}',
        encoding="utf-8",
    )
    ledger = tmp_path / "2026-06.json"
    write_json(ledger, {"schema_version": "0.3.0", "records": [record(账户="现金", 金额=-10)]})
    result = run("validate_ledger.py", str(ledger), "--accounts", str(accounts))
    assert result.returncode == 0, result.stdout + result.stderr

def test_multi_currency_and_base_currency(tmp_path: Path) -> None:
    settings = tmp_path / "custom-settings.json"
    settings.write_text(json.dumps({"base_currency": "CNY"}), encoding="utf-8")
    ledger = tmp_path / "2026-06.json"
    write_json(
        ledger,
        {
            "schema_version": "0.3.0",
            "records": [
                record(金额=-70, currency="USD", original_amount=-10, fx_rate=7, cny_amount=-70),
                record(时间="2026-06-02 10:00", 金额=-20, 备注="人民币"),
            ],
        },
    )
    checked = run("validate_ledger.py", str(ledger), "--settings", str(settings))
    assert checked.returncode == 0, checked.stdout + checked.stderr
    summary = run("summarize_ledger.py", str(ledger), "--settings", str(settings))
    assert summary.returncode == 0, summary.stdout + summary.stderr
    assert "按币种（原币，不折算）" in summary.stdout
    usd_line = next(line for line in summary.stdout.splitlines() if line.startswith("- USD:"))
    assert "支出毛额 10.00" in usd_line

    jpy_settings = tmp_path / "custom-jpy.json"
    jpy_settings.write_text(json.dumps({"base_currency": "JPY"}), encoding="utf-8")
    jpy_ledger = tmp_path / "jpy.json"
    write_json(
        jpy_ledger,
        {
            "schema_version": "0.3.0",
            "records": [
                record(金额=-2000, currency="CNY", original_amount=-100, fx_rate=20, cny_amount=-2000),
            ],
        },
    )
    jpy_checked = run("validate_ledger.py", str(jpy_ledger), "--settings", str(jpy_settings))
    assert jpy_checked.returncode == 0, jpy_checked.stdout + jpy_checked.stderr
    assert "非-CNY" not in jpy_checked.stdout


def test_import_rules_are_configurable(tmp_path: Path) -> None:
    accounts = write_json_file(
        tmp_path / "custom-accounts.json",
        {"replace_defaults": True, "accounts": [{"账户": "测试现金", "账户类型": "资产"}]},
    )
    categories = write_json_file(
        tmp_path / "custom-categories.json",
        {"replace_defaults": True, "categories": {"宠物": ["猫粮"]}},
    )
    import_rules = write_json_file(
        tmp_path / "custom-import-rules.json",
        {
            "category_keywords": [{"类别": "宠物", "子类": "猫粮", "关键词": ["猫粮", "猫砂"]}],
            "fallback": {"类别": "宠物", "子类": "猫粮"},
        },
    )
    bill = tmp_path / "bill.csv"
    bill.write_text(
        "时间,收支类型,金额,类别,子类,账户,备注\n"
        "2026-06-05 10:00,支出,20,,,测试现金,猫粮\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    result = run(
        "import_ledger.py",
        str(bill),
        "--output",
        str(out),
        "--accounts",
        str(accounts),
        "--categories",
        str(categories),
        "--import-rules",
        str(import_rules),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = read_json(out)
    assert payload["records"][0]["类别"] == "宠物"
    assert payload["records"][0]["子类"] == "猫粮"


def test_investment_account_flag_drives_direction(tmp_path: Path) -> None:
    accounts = write_json_file(
        tmp_path / "custom-accounts.json",
        {
            "accounts": [
                {"账户": "建设银行", "账户类型": "资产"},
                {"账户": "基金", "账户类型": "资产", "投资账户": True},
            ]
        },
    )
    ledger = tmp_path / "invest.json"
    write_json(
        ledger,
        {
            "schema_version": "0.3.0",
            "records": [
                record(
                    id="buy-out",
                    时间="2026-06-01 09:00",
                    收支类型="投资",
                    金额=-100,
                    类别="投资",
                    子类="定投",
                    账户="建设银行",
                    备注="买入",
                    pairid="inv",
                ),
                record(
                    id="buy-in",
                    时间="2026-06-01 09:01",
                    收支类型="投资",
                    金额=100,
                    类别="投资",
                    子类="定投",
                    账户="基金",
                    备注="买入",
                    pairid="inv",
                ),
                record(
                    id="sell",
                    时间="2026-06-10 09:00",
                    收支类型="投资",
                    金额=40,
                    类别="投资",
                    子类="卖出",
                    账户="建设银行",
                    备注="赎回",
                    target_account="基金",
                ),
            ],
        },
    )
    checked = run("validate_ledger.py", str(ledger), "--accounts", str(accounts))
    assert checked.returncode == 0, checked.stdout + checked.stderr
    summary = run("summarize_ledger.py", str(ledger), "--accounts", str(accounts))
    assert summary.returncode == 0, summary.stdout + summary.stderr
    assert "- 投资净投入: 60.00" in summary.stdout


def test_zero_amount_pending_reimbursement_is_flagged(tmp_path: Path) -> None:
    ledger = tmp_path / "pending.json"
    write_json(
        ledger,
        {
            "schema_version": "0.3.0",
            "records": [
                record(
                    金额=0,
                    类别="出行交通",
                    子类="飞机",
                    备注="全额报销",
                    报销状态="待报销",
                    预计报销=500,
                )
            ],
        },
    )
    checked = run("validate_ledger.py", str(ledger))
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "金额为 0 的支出仍标为" in checked.stdout
    summary = run("summarize_ledger.py", str(ledger))
    assert "- 待报销: 0.00" in summary.stdout
