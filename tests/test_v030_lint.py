"""Read-only lint. Fixtures use fictional round amounts only."""

from __future__ import annotations

from pathlib import Path

from test_ledger import record, run, write_json


def test_lint_warns_near_duplicates_aliases_and_overdue_reimbursement(tmp_path: Path) -> None:
    ledger = tmp_path / "2026-06.json"
    write_json(
        ledger,
        {
            "schema_version": "0.3.0",
            "records": [
                record(时间="2026-06-01 10:00", 金额=-35, 备注="午饭套餐"),
                record(时间="2026-06-03 11:00", 金额=-35, 备注="午饭套餐加餐"),
                record(时间="2026-06-01 10:00", 金额=-35, 备注="午饭套餐"),
                record(时间="2026-06-08 10:00", 金额=-35, 账户="支付宝", 备注="午饭套餐"),
                record(时间="2026-07-02 10:00", 金额=-18, 账户="美团", 备注="美团外卖"),
                record(时间="2026-06-04 10:00", 金额=-12, 账户="现金罐", 备注="路边摊"),
                record(时间="2026-06-05 10:00", 金额=12, 备注="正数支出"),
                record(
                    时间="2026-06-06 10:00",
                    收支类型="还款",
                    金额=20,
                    类别="还款",
                    子类="月付还款",
                    账户="支付宝",
                    备注="还白条",
                ),
                record(
                    时间="2026-06-07 10:00",
                    收支类型="报销",
                    金额=10,
                    类别="报销",
                    子类="其他",
                    备注="报销未关联",
                ),
                record(时间="2026-05-01 10:00", 金额=-22, 备注="旧发票", 报销状态="待报销"),
            ],
        },
    )
    aliases = tmp_path / "aliases.json"
    aliases.write_text(
        '[{"名称":"美团","含义":"美团钱包","起":"2026-01-01","止":"2026-06-30"}]\n',
        encoding="utf-8",
    )
    before = ledger.read_text(encoding="utf-8")
    result = run("lint_ledger.py", str(ledger), "--aliases", str(aliases), "--as-of", "2026-06-20")
    assert result.returncode == 0, result.stdout + result.stderr
    assert ledger.read_text(encoding="utf-8") == before
    assert "近似重复 record[1] 与 record[2]" in result.stdout
    assert "近似重复 record[1] 与 record[3]" not in result.stdout
    assert not any("近似重复" in line and "record[4]" in line for line in result.stdout.splitlines())
    assert "别名 美团" in result.stdout
    assert "2026-07-02" in result.stdout
    assert "新账户 现金罐" in result.stdout
    merchant_lines = [line for line in result.stdout.splitlines() if line.endswith("新商户 午饭套餐")]
    assert merchant_lines == ["- record[1]: 新商户 午饭套餐"]
    assert "usually uses a negative" in result.stdout
    assert "还款没有 target_account" in result.stdout
    assert "报销没有 reimburse_of" in result.stdout
    assert "待报销超过30天" in result.stdout
    assert "## 月度覆盖" in result.stdout


def test_lint_flags_missing_recurring_and_subscription(tmp_path: Path) -> None:
    ledger = tmp_path / "2026-06.json"
    write_json(
        ledger,
        {
            "schema_version": "0.3.0",
            "records": [
                record(
                    时间="2026-06-01 09:00",
                    金额=-2100,
                    类别="居家生活",
                    子类="住宿",
                    账户="招商银行",
                    备注="房租",
                ),
                record(时间="2026-06-02 12:00", 金额=-30, 备注="午饭"),
                record(时间="2026-07-05 12:00", 金额=-30, 备注="午饭 待确认"),
            ],
        },
    )
    recurring = tmp_path / "recurring.json"
    recurring.write_text(
        '{"items":[{"名称":"房租","金额下限":2000,"金额上限":2200,"日":5,"账户":"招商银行","周期":"月"}]}\n',
        encoding="utf-8",
    )
    items = tmp_path / "items.json"
    items.write_text(
        """
        {"schema_version":"0.3.0","subscriptions":[
          {"id":"sub-001","名称":"某AI会员","金额":140,"周期":"月","续费日":"2026-06-03","扣款账户":"招商银行","状态":"active"},
          {"id":"sub-002","名称":"已停会员","金额":20,"周期":"月","续费日":"2026-06-03","扣款账户":"招商银行","状态":"已取消"}
        ],"holdings":[]}
        """,
        encoding="utf-8",
    )
    result = run(
        "lint_ledger.py",
        str(ledger),
        "--recurring",
        str(recurring),
        "--items",
        str(items),
        "--as-of",
        "2026-07-31",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "固定支出缺月 房租 2026-06" not in result.stdout
    assert "固定支出缺月 房租 2026-07" in result.stdout
    assert "预计每月 5 日" in result.stdout
    assert "固定支出缺月 某AI会员 2026-06" in result.stdout
    assert "已停会员" not in result.stdout
    assert "2026-06: 记录 2, 有记录天数 2, 最长连续空白 28 天, 时间为空 0, 待确认 0, 固定支出 1/2" in result.stdout
    assert "2026-07: 记录 1, 有记录天数 1, 最长连续空白 26 天, 时间为空 0, 待确认 1, 固定支出 0/2" in result.stdout


def test_lint_counts_blank_time_and_rejects_bad_json(tmp_path: Path) -> None:
    ledger = tmp_path / "book.json"
    write_json(
        ledger,
        {
            "schema_version": "0.2.0",
            "records": [record(时间="", 金额=-10, 备注="缺时间")],
        },
    )
    result = run("lint_ledger.py", str(ledger), "--as-of", "2026-06-30")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "无时间: 记录 1" in result.stdout
    assert "时间为空 1" in result.stdout
    broken = tmp_path / "broken.json"
    broken.write_text("{", encoding="utf-8")
    invalid = run("lint_ledger.py", str(broken))
    assert invalid.returncode == 1
    assert "invalid JSON" in invalid.stdout
