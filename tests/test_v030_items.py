"""Subscriptions and holdings stay outside net worth. Amounts are fictional."""

from __future__ import annotations

from pathlib import Path

from test_ledger import record, run, write_json


def test_items_summary_and_asset_residual_are_separate(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    write_json(
        ledger,
        {
            "schema_version": "0.3.0",
            "records": [
                record(
                    id="fee",
                    时间="2026-10-03 09:00",
                    金额=-140,
                    账户="招商银行",
                    备注="某AI会员",
                    item_id="sub-001",
                    报销状态="待报销",
                )
            ],
        },
    )
    summary = run(
        "summarize_items.py",
        "examples/items.sample.json",
        "--ledger",
        str(ledger),
        "--as-of",
        "2026-10-19",
    )
    assert summary.returncode == 0, summary.stdout + summary.stderr
    assert "- 按月折算: 240.00" in summary.stdout
    assert "某AI会员 2026-11-03 140.00" in summary.stdout
    assert "年刊" not in summary.stdout.split("30天内续费", 1)[1].split("##", 1)[0]
    assert "已停周刊" not in summary.stdout.split("## 订阅", 1)[1].split("##", 1)[0]
    assert "某AI会员: 没有对应报销" in summary.stdout
    assert "- 购入合计: 5000.00" in summary.stdout
    assert "- 残值合计: 3200.00" in summary.stdout
    assert "- 使用成本/天: 8.41" in summary.stdout
    assert "旧耳机" not in summary.stdout.split("## 物品", 1)[1].split("已卖出或已送出", 1)[0]
    assert "已卖出或已送出: 1" in summary.stdout
    assert "不计入总资产、净资产、备查净值" in summary.stdout

    paid = tmp_path / "paid.json"
    write_json(
        paid,
        {
            "schema_version": "0.3.0",
            "records": [
                record(
                    id="fee",
                    时间="2026-10-03 09:00",
                    金额=-140,
                    账户="招商银行",
                    备注="某AI会员",
                    item_id="sub-001",
                    报销状态="已报销",
                ),
                record(
                    时间="2026-10-18 09:00",
                    收支类型="报销",
                    金额=140,
                    类别="报销",
                    子类="AI订阅",
                    账户="招商银行",
                    备注="会员报销",
                    reimburse_of="fee",
                    item_id="sub-001",
                ),
            ],
        },
    )
    cleared = run("summarize_items.py", "examples/items.sample.json", "--ledger", str(paid), "--as-of", "2026-10-19")
    assert cleared.returncode == 0, cleared.stdout + cleared.stderr
    assert "没有对应报销" not in cleared.stdout

    assets = run(
        "summarize_assets.py",
        "examples/assets.sample.json",
        "--as-of",
        "2026-06-30",
        "--items",
        "examples/items.sample.json",
    )
    assert assets.returncode == 0, assets.stdout + assets.stderr
    summary_block = assets.stdout.split("## 汇总", 1)[1].split("##", 1)[0]
    assert "净资产: 6600.00" in summary_block
    assert "总资产: 6800.00" in summary_block
    assert "备查净值: 0.00" in summary_block
    assert "3200" not in summary_block
    assert "## 备查物品" in assets.stdout
    assert "- 残值合计: 3200.00（不计入总资产、净资产、备查净值）" in assets.stdout

    bare = run("summarize_assets.py", "examples/assets.sample.json", "--as-of", "2026-06-30")
    assert "## 备查物品" not in bare.stdout


def test_item_id_is_not_a_tag_and_satisfies_subscription_lint(tmp_path: Path) -> None:
    ledger = tmp_path / "2026-06.json"
    write_json(
        ledger,
        {
            "schema_version": "0.3.0",
            "records": [
                record(
                    时间="2026-06-03 09:00",
                    金额=-140,
                    账户="招商银行",
                    备注="扣款",
                    tags="nature:need",
                    item_id="sub-001",
                )
            ],
        },
    )
    checked = run("validate_ledger.py", str(ledger))
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "trip:" not in checked.stdout
    items = tmp_path / "items.json"
    items.write_text(
        '{"subscriptions":[{"id":"sub-001","名称":"某AI会员","金额":140,"周期":"月","续费日":"2026-06-03","扣款账户":"招商银行","状态":"active"}],"holdings":[]}\n',
        encoding="utf-8",
    )
    linted = run("lint_ledger.py", str(ledger), "--items", str(items), "--as-of", "2026-06-30")
    assert linted.returncode == 0, linted.stdout + linted.stderr
    assert "固定支出缺月 某AI会员" not in linted.stdout
