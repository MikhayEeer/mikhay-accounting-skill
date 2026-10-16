from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

import pytest

from ledgerlib import shard_key
from project_assets import project
from validate_ledger import validate_records


ROOT = Path(__file__).resolve().parents[1]


def run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record(**kwargs):
    base = {
        "时间": "2026-06-01 10:00",
        "收支类型": "支出",
        "金额": -10,
        "类别": "食品餐饮",
        "子类": "午餐",
        "账户": "微信钱包",
        "备注": "午饭",
        "tags": "",
        "note": "",
    }
    base.update(kwargs)
    return base


def test_basename_shard_key_does_not_capture_ledger_prefix() -> None:
    path = "data/ledger/2026/2026-06.json"
    buggy = path[path.index("ledger") + 5 : path.index("ledger") + 10]
    assert buggy == "r/202"
    assert shard_key(path, "month") == "2026-06"
    assert shard_key(Path(path), "day") == ""
    day_path = "data/ledger/2026/2026-06/2026-06-01.json"
    assert shard_key(day_path, "day") == "2026-06-01"
    assert shard_key(day_path, "month") == "2026-06"
    source = (ROOT / "scripts" / "ledgerlib.py").read_text(encoding="utf-8")
    assert "os.path.basename" in source


def test_existing_samples_still_validate() -> None:
    for name in ("examples/ledger.sample.csv", "examples/book.sample.json", "examples/assets.sample.json"):
        result = run("validate_ledger.py", name)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.startswith("OK:")


def test_new_subcategories_and_refund_and_currency(tmp_path: Path) -> None:
    rows = [
        record(子类="早餐", 金额=-8, 备注="早餐"),
        record(时间="2026-06-02 10:00", 类别="出行交通", 子类="维修", 金额=-30, 备注="保养", 账户="支付宝"),
        record(时间="2026-06-03 10:00", 类别="居家生活", 子类="电费", 金额=-40, 备注="电费", 账户="建设银行"),
        record(时间="2026-06-04 10:00", 类别="休闲娱乐", 子类="KTV", 金额=-50, 备注="唱歌", 账户="美团"),
        record(
            id="usd-1",
            时间="2026-06-05 10:00",
            金额=-70,
            类别="购物消费",
            子类="数码",
            账户="招商银行",
            备注="美元",
            currency="USD",
            original_amount=-10,
            fx_rate=7,
            cny_amount=-70,
        ),
    ]
    errors, _warnings = validate_records(rows, max_date=date(2026, 12, 31))
    assert errors == []


def test_validator_rejects_bad_tags_dates_duplicates_and_pairs() -> None:
    ok_pair = [
        record(id="a", 时间="2026-06-01 09:00", 收支类型="转账", 金额=-20, 类别="转账", 子类="个人转账", 账户="建设银行", 备注="转出", pairid="p1", tags="trip:hz"),
        record(id="b", 时间="2026-06-01 09:01", 收支类型="转账", 金额=20, 类别="转账", 子类="个人转账", 账户="支付宝", 备注="转入", pairid="p1", tags="trip:hz"),
    ]
    errors, warnings = validate_records(ok_pair, max_date=date(2026, 12, 31))
    assert errors == []
    assert warnings == []

    bad_tag, _ = validate_records([record(tags="foo:bar")], max_date=date(2026, 12, 31))
    assert any("trip:" in error for error in bad_tag)
    legacy_errors, legacy_warnings = validate_records([record(tags="旅行")], max_date=date(2026, 12, 31))
    assert legacy_errors == []
    assert any("legacy tag" in warning for warning in legacy_warnings)

    future, _ = validate_records([record(时间="2999-01-01 00:00")], max_date=date(2026, 12, 31))
    assert any("upper bound" in error for error in future)

    dup, _ = validate_records([record(备注="同一笔"), record(备注="同一笔")], max_date=date(2026, 12, 31))
    assert any("duplicate" in error for error in dup)

    unequal, _ = validate_records(
        [
            record(收支类型="转账", 金额=-20, 类别="转账", 子类="个人转账", 账户="建设银行", 备注="转出", pairid="p2"),
            record(时间="2026-06-01 11:00", 收支类型="转账", 金额=21, 类别="转账", 子类="个人转账", 账户="支付宝", 备注="转入", pairid="p2"),
        ],
        max_date=date(2026, 12, 31),
    )
    assert any("not equal" in error for error in unequal)

    same_way, _ = validate_records(
        [
            record(收支类型="转账", 金额=20, 类别="转账", 子类="个人转账", 账户="建设银行", 备注="甲", pairid="p3"),
            record(时间="2026-06-01 12:00", 收支类型="转账", 金额=20, 类别="转账", 子类="个人转账", 账户="支付宝", 备注="乙", pairid="p3"),
        ],
        max_date=date(2026, 12, 31),
    )
    assert any("opposite" in error for error in same_way)

    incomplete, _ = validate_records(
        [record(收支类型="转账", 金额=-20, 类别="转账", 子类="个人转账", 账户="建设银行", 备注="单边", pairid="p4")],
        max_date=date(2026, 12, 31),
    )
    assert any("expected 2 legs" in error for error in incomplete)

    bad_amount, _ = validate_records([record(金额="12.3.4")], max_date=date(2026, 12, 31))
    assert any("decimal" in error for error in bad_amount)

    fx, _ = validate_records(
        [record(金额=-10, currency="USD", original_amount=-10, fx_rate=7, cny_amount=-10, 类别="购物消费", 子类="数码", 备注="汇率不符")],
        max_date=date(2026, 12, 31),
    )
    assert any("fx_rate" in error for error in fx)


def test_csv_duplicate_header_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("时间,时间,金额\n2026-06-01,2026-06-01,1\n", encoding="utf-8")
    result = run("validate_ledger.py", str(path))
    assert result.returncode == 1
    assert "duplicate column" in result.stdout


def test_dual_basis_gross_net_and_buckets(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger" / "2026" / "2026-06.json"
    write_json(
        ledger,
        {
            "schema_version": "0.2.0",
            "month": "2026-06",
            "records": [
                record(id="e1", 金额=-40, 备注="吃饭", tags="trip:city"),
                record(id="e2", 时间="2026-06-02 10:00", 金额=-60, 类别="出行交通", 子类="打车", 账户="支付宝", 备注="打车", tags="trip:city"),
                record(id="r1", 时间="2026-06-03 10:00", 收支类型="退款", 金额=10, 备注="退一笔", refund_of="e1", tags="trip:city"),
                record(id="in", 时间="2026-06-04 10:00", 收支类型="收入", 金额=100, 类别="收入", 子类="工资", 账户="建设银行", 备注="工资"),
                record(id="o", 时间="2026-06-05 10:00", 收支类型="转账", 金额=-15, 类别="转账", 子类="个人转账", 账户="建设银行", 备注="转出", pairid="pair"),
                record(id="i", 时间="2026-06-05 10:01", 收支类型="转账", 金额=15, 类别="转账", 子类="个人转账", 账户="支付宝", 备注="转入", pairid="pair"),
            ],
        },
    )
    buckets = tmp_path / "buckets.json"
    buckets.write_text(json.dumps({"饮食": ["食品餐饮"], "其他": ["*"]}, ensure_ascii=False), encoding="utf-8")
    result = run("summarize_ledger.py", str(ledger.parent.parent), "--buckets", str(buckets))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "花销毛额: 100.00" in result.stdout
    assert "退款: 10.00" in result.stdout
    assert "花销净额: 90.00" in result.stdout
    assert "收入: 100.00" in result.stdout
    assert "内部转账: 15.00" in result.stdout
    assert "转账: 30.00" in result.stdout
    assert "花销口径:" in result.stdout
    assert "内部转账口径: 15.00" in result.stdout
    assert "2026-06" in result.stdout
    assert "r/202" not in result.stdout
    assert "饮食:" in result.stdout
    assert "食品餐饮: 30.00" in result.stdout


def test_summarize_tags_scans_every_shard_and_prints_percentage(tmp_path: Path) -> None:
    root = tmp_path / "data" / "ledger" / "2026"
    write_json(
        root / "2026-05.json",
        {"records": [record(时间="2026-05-02 10:00", 金额=-30, 备注="五月", tags=["trip:city"])]},
    )
    write_json(
        root / "2026-06.json",
        {
            "records": [
                record(id="food", 时间="2026-06-01 10:00", 金额=-40, 备注="饭", tags="trip:city"),
                record(时间="2026-06-02 10:00", 金额=-70, 类别="出行交通", 子类="打车", 账户="支付宝", 备注="车", tags="trip:city;event:dinner"),
                record(时间="2026-06-03 10:00", 收支类型="退款", 金额=10, 类别="食品餐饮", 子类="午餐", 备注="退款", refund_of="food"),
            ]
        },
    )
    result = run("summarize_tags.py", str(tmp_path / "data" / "ledger"))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "扫描文件: 2" in result.stdout
    assert "全部分片已扫描" in result.stdout
    assert "2026-05" in result.stdout and "2026-06" in result.stdout
    assert "r/202" not in result.stdout
    assert "毛额: 140.00" in result.stdout
    assert "净额: 130.00" in result.stdout
    food = next(line for line in result.stdout.splitlines() if line.startswith("- 食品餐饮:"))
    traffic = next(line for line in result.stdout.splitlines() if line.startswith("- 出行交通:"))
    assert "毛额 70.00, 净额 60.00, 占比 46.15%" in food
    assert "毛额 70.00, 净额 70.00, 占比 53.85%" in traffic


def test_tag_percentage_is_share_of_tag_net(tmp_path: Path) -> None:
    path = tmp_path / "2026-06.json"
    write_json(
        path,
        {
            "records": [
                record(id="f", 金额=-30, 备注="饭", tags="nature:need"),
                record(时间="2026-06-02 10:00", 金额=-70, 类别="出行交通", 子类="打车", 账户="支付宝", 备注="车", tags="nature:need"),
                record(时间="2026-06-03 10:00", 收支类型="退款", 金额=10, 备注="退", refund_of="f"),
            ]
        },
    )
    result = run("summarize_tags.py", str(path))
    assert result.returncode == 0, result.stdout + result.stderr
    food = next(line for line in result.stdout.splitlines() if "食品餐饮:" in line and "占比" in line)
    traffic = next(line for line in result.stdout.splitlines() if "出行交通:" in line and "占比" in line)
    assert "毛额 30.00, 净额 20.00, 占比 22.22%" in food
    assert "毛额 70.00, 净额 70.00, 占比 77.78%" in traffic


def test_included_and_excluded_net_worth_and_card_methods(tmp_path: Path) -> None:
    path = tmp_path / "assets.json"
    write_json(
        path,
        {
            "schema_version": "0.2.0",
            "asset_snapshots": [
                {"时间": "2026-06-01", "账户": "建设银行", "账户类型": "资产", "金额": 5000},
                {"时间": "2026-06-01", "账户": "公积金", "账户类型": "资产", "金额": 20000},
                {"时间": "2026-06-01", "账户": "花呗", "账户类型": "负债", "金额": -100},
                {"时间": "2026-06-01", "账户": "Apple Card", "账户类型": "负债", "金额": -50},
            ],
            "records": [
                {"时间": "2026-05-01 10:00", "收支类型": "支出", "金额": -30, "账户": "花呗", "类别": "食品餐饮", "子类": "午餐", "备注": "五月"},
                {"时间": "2026-06-02 10:00", "收支类型": "支出", "金额": -40, "账户": "花呗", "类别": "食品餐饮", "子类": "午餐", "备注": "六月"},
            ],
            "credit_accounts": [{"账户": "花呗", "欠款": 100, "额度": 5000, "账单日": 1, "还款日": 10, "状态": "active"}],
        },
    )
    method_a = run("summarize_assets.py", str(path), "--as-of", "2026-06-30", "--cc-method", "A")
    assert method_a.returncode == 0, method_a.stdout + method_a.stderr
    assert "信用卡余额算法: A（最近快照+快照后新增）" in method_a.stdout
    included, rest = method_a.stdout.split("## 备查账户", 1)
    assert "花呗: -140.00" in included
    assert "公积金" not in included.split("## 计入净资产", 1)[1]
    assert "公积金: 20000.00" in rest
    assert "Apple Card: -50.00" in rest
    summary = rest.split("## 汇总", 1)[1].split("##", 1)[0]
    assert "净资产: 4860.00" in summary
    assert "备查净值: 19950.00" in summary

    method_b = run("summarize_assets.py", str(path), "--as-of", "2026-06-30", "--cc-method", "B")
    assert method_b.returncode == 0, method_b.stdout + method_b.stderr
    assert "信用卡余额算法: B（账本从零重放）" in method_b.stdout
    assert "花呗: -70.00" in method_b.stdout


def test_forecast_uses_last_working_day(tmp_path: Path) -> None:
    path = tmp_path / "assets.json"
    write_json(
        path,
        {
            "asset_snapshots": [
                {"时间": "2026-05-01", "账户": "建设银行", "账户类型": "资产", "金额": 3000},
                {"时间": "2026-05-01", "账户": "花呗", "账户类型": "负债", "金额": 0},
            ],
            "credit_accounts": [{"账户": "花呗", "欠款": 0, "额度": 5000, "账单日": 1, "还款日": 10, "状态": "active"}],
            "records": [
                record(时间="2026-05-20 12:00", 金额=-80, 账户="花呗", 备注="上期"),
                record(时间="2026-06-05 12:00", 金额=-200, 账户="花呗", 备注="本期"),
                record(时间="2026-06-10 09:00", 收支类型="收入", 金额=2000, 类别="收入", 子类="工资", 账户="建设银行", 备注="工资"),
            ],
        },
    )
    result = run("summarize_assets.py", str(path), "--as-of", "2026-06-15", "--forecast")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "发薪日: 2026-06-30" in result.stdout
    card = next(line for line in result.stdout.splitlines() if line.startswith("- 花呗: 预计账单"))
    assert "预计账单 200.00" in card
    assert "预计还款 80.00" in card
    assert "还款日 2026-06-10" in card
    assert "还款在发薪日前" in card
    assert "发薪日现金流: 收入 2000.00 - 现金花销净额 0.00 - 预计还款 80.00 = 1920.00" in result.stdout

    from ledgerlib import last_working_day

    assert last_working_day(2026, 10) == date(2026, 10, 30)
    assert last_working_day(2026, 5) == date(2026, 5, 29)


def test_import_shard_basename_and_schema_version(tmp_path: Path) -> None:
    source = tmp_path / "bill.csv"
    source.write_text(
        "时间,收支类型,金额,类别,子类,账户,备注\n"
        "2026-06-01 08:00,支出,15,食品餐饮,早餐,微信钱包,早饭\n"
        "2026-06-02 08:00,支出,16,食品餐饮,早餐,微信钱包,早饭2\n"
        "2026-06-03 08:00,支出,20,出行交通,维修,支付宝,保养\n",
        encoding="utf-8",
    )
    out = tmp_path / "data" / "ledger"
    result = run("import_ledger.py", str(source), "--shard", "day", "--year-dirs", "--output", str(out))
    assert result.returncode == 0, result.stdout + result.stderr
    day_file = out / "2026" / "2026-06" / "2026-06-01.json"
    assert day_file.exists()
    full = day_file.as_posix()
    assert full[full.index("ledger") + 5 : full.index("ledger") + 10] == "r/202"
    assert shard_key(day_file, "day") == "2026-06-01"
    payload = json.loads(day_file.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "0.2.0"
    month = run("import_ledger.py", str(source), "--shard", "month", "--year-dirs", "--output", str(tmp_path / "month"))
    assert month.returncode == 0, month.stdout + month.stderr
    month_file = tmp_path / "month" / "2026" / "2026-06.json"
    assert shard_key(month_file, "month") == "2026-06"
    exported = tmp_path / "out.csv"
    exported_run = run("export_ledger.py", str(month_file), "--output", str(exported))
    assert exported_run.returncode == 0, exported_run.stdout + exported_run.stderr
    header = exported.read_text(encoding="utf-8-sig").splitlines()[0]
    assert "currency" in header and "pairid" in header and "refund_of" in header


def test_project_assets_starts_from_observed_snapshot() -> None:
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
    from datetime import datetime

    inferred = project(assets, records, datetime.fromisoformat("2026-07-05 23:59"))
    balances = {row["账户"]: row["余额"] for row in inferred["账户余额"]}
    assert balances == {"建设银行": 1150, "花呗": -150}
    assert inferred["净资产"] == 1000
    assert inferred["未建立基线账户"] == ["微信钱包"]


def test_pair_tag_on_either_leg_counts_once() -> None:
    from decimal import Decimal

    from summarize_tags import rollup

    stats = rollup(
        [
            record(
                时间="2026-06-05 10:00",
                收支类型="转账",
                金额=-15,
                类别="转账",
                子类="个人转账",
                账户="建设银行",
                备注="转出",
                pairid="pair",
                tags="event:move",
            ),
            record(
                时间="2026-06-05 10:01",
                收支类型="转账",
                金额=15,
                类别="转账",
                子类="个人转账",
                账户="支付宝",
                备注="转入",
                pairid="pair",
                tags="person:li",
            ),
        ]
    )
    assert stats["event:move"].transfer == Decimal("15")
    assert stats["person:li"].transfer == Decimal("15")
    assert stats["event:move"].gross == Decimal("0")


def test_extended_example_and_docs() -> None:
    result = run("validate_ledger.py", "examples/ledger.extended.sample.json")
    assert result.returncode == 0, result.stdout + result.stderr
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    categories = (ROOT / "categories.md").read_text(encoding="utf-8")
    assert "never hand math" in skill
    assert "summarize_tags.py" in skill
    assert "花销" in skill and "内部转账" in skill
    assert "花销" in readme and "内部转账" in readme
    assert "维修" in categories and "电费" in categories and "KTV" in categories
    assert (ROOT / "CHANGELOG.md").exists()
    assert not (ROOT / "VERSION").exists()
    frontmatter = skill.split("---", 2)[1]
    assert "version: 0.2.1" in frontmatter
    assert "slug: mikhay-accounting-skill" in frontmatter
    body = skill.split("---", 2)[2]
    assert len(body.splitlines()) <= 160
    for name in ("faq.md", "troubleshooting.md", "triggers.md", "design-rationale.md"):
        assert (ROOT / "references" / name).exists()
    assert (ROOT / ".github" / "workflows" / "ci.yml").exists()


def test_package_omits_version_file_tests_and_github(tmp_path: Path) -> None:
    result = run("package_skill.py", "--output", str(tmp_path))
    assert result.returncode == 0, result.stdout + result.stderr
    archive = zipfile.ZipFile(tmp_path / "mikhay-accounting-skill.zip")
    names = [name.replace("\\", "/") for name in archive.namelist()]
    assert not any(name.endswith("/VERSION") or name.rsplit("/", 1)[-1] == "VERSION" for name in names)
    assert not any("/tests/" in f"/{name}" or "/.github/" in f"/{name}" for name in names)
    assert any(name.endswith("references/faq.md") for name in names)
    assert any(name.endswith("examples/workflow-credit-repay.md") for name in names)
    manifest = json.loads(archive.read("mikhay-accounting-skill/MANIFEST.json"))
    assert manifest["version"] == "0.2.1"


def test_wishlist_still_runs() -> None:
    result = run(
        "analyze_wishlist.py",
        "examples/wishlist.sample.json",
        "--ledger",
        "examples/book.sample.json",
        "--assets",
        "examples/assets.sample.json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "机械键盘" in result.stdout
