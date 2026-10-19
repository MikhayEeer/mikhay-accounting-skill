"""Wishlist cooling-off period and budget buckets. Amounts are fictional."""

from __future__ import annotations

import json
from pathlib import Path

from test_ledger import record, run, write_json


def wishlist(tmp_path: Path, items: list[dict], buckets: list[dict] | None = None) -> Path:
    path = tmp_path / "wishlist.json"
    path.write_text(
        json.dumps({"items": items, "budget_buckets": buckets or []}, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def base_item(**kwargs) -> dict:
    item = {
        "名称": "键盘",
        "预计金额": 200,
        "类型": "数码",
        "优先级": "P2",
        "目标日期": "2026-12-01",
        "可延期": True,
        "状态": "想买",
        "加入日期": "2026-09-01",
    }
    item.update(kwargs)
    return item


def test_sample_wishlist_still_runs() -> None:
    result = run(
        "analyze_wishlist.py",
        "examples/wishlist.sample.json",
        "--ledger",
        "examples/book.sample.json",
        "--assets",
        "examples/assets.sample.json",
        "--as-of",
        "2026-10-19",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "机械键盘" in result.stdout
    assert "冷静期" not in result.stdout


def test_cooling_period_blocks_and_due_lists_only_expired(tmp_path: Path) -> None:
    path = wishlist(
        tmp_path,
        [
            base_item(名称="还在冷静", 加入日期="2026-10-18", 冷静天数=7, 额度桶="双十一", 预计金额=4000),
            base_item(名称="已经到期", 加入日期="2026-10-01", 冷静天数=7, 优先级="P1"),
            base_item(名称="立刻要", 优先级="P0", 加入日期="2026-10-19", 预计金额=20, 类型="维修", 可延期=False),
        ],
        [{"名称": "双十一", "额度": 3000, "起": "2026-10-01", "止": "2026-11-12"}],
    )
    result = run("analyze_wishlist.py", str(path), "--as-of", "2026-10-19")
    assert result.returncode == 0, result.stdout + result.stderr
    cooling = next(line for line in result.stdout.splitlines() if line.startswith("- 还在冷静"))
    assert "观望（冷静期剩 6 天）" in cooling
    assert "不建议" not in cooling
    ready = next(line for line in result.stdout.splitlines() if line.startswith("- 已经到期"))
    assert "冷静期" not in ready
    urgent = next(line for line in result.stdout.splitlines() if line.startswith("- 立刻要"))
    assert "冷静期" not in urgent

    due = run("analyze_wishlist.py", str(path), "--due", "--as-of", "2026-10-19")
    assert due.returncode == 0, due.stdout + due.stderr
    assert "已经到期: 冷静期至 2026-10-08，已到期" in due.stdout
    assert "还在冷静" not in due.stdout
    assert "立刻要" not in due.stdout


def test_bucket_and_target_price(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.json"
    write_json(
        ledger,
        {
            "schema_version": "0.3.0",
            "records": [record(id="bought-1", 时间="2026-10-21 10:00", 金额=-2500, 备注="已买的杯子")],
        },
    )
    path = wishlist(
        tmp_path,
        [
            base_item(名称="杯子", 状态="已购买", 预计金额=2500, record_id="bought-1", 额度桶="双十一", 加入日期="2026-10-01"),
            base_item(名称="显示器", 预计金额=800, 目标价=500, 额度桶="双十一", 加入日期="2026-10-01"),
            base_item(名称="耳机", 预计金额=300, 目标价=100, 加入日期="2026-10-01"),
        ],
        [{"名称": "双十一", "额度": 3000, "起": "2026-10-20", "止": "2026-11-12"}],
    )
    result = run("analyze_wishlist.py", str(path), "--ledger", str(ledger), "--as-of", "2026-10-21")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "双十一: 额度 3000.00, 已用 2500.00, 剩余 500.00" in result.stdout
    screen = next(line for line in result.stdout.splitlines() if line.startswith("- 显示器"))
    assert "不建议" in screen
    assert "超出额度桶剩余额度" in screen
    headphones = next(line for line in result.stdout.splitlines() if line.startswith("- 耳机"))
    assert "等降价" in headphones
    assert "不建议" not in headphones or "等降价" in headphones


def test_missing_reason_and_record_id_warn(tmp_path: Path) -> None:
    path = wishlist(
        tmp_path,
        [
            base_item(名称="放弃的", 状态="放弃", 加入日期="2026-10-01"),
            base_item(名称="买过的", 状态="已购买", 加入日期="2026-10-01"),
        ],
    )
    result = run("analyze_wishlist.py", str(path), "--validate-only", "--as-of", "2026-10-19")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "放弃需要填写放弃原因" in result.stdout
    assert "已购买缺少 record_id" in result.stdout
    filled = wishlist(
        tmp_path,
        [base_item(名称="放弃的", 状态="放弃", 放弃原因="等生态", 加入日期="2026-10-01", record_id="x")],
    )
    ok = run("analyze_wishlist.py", str(filled), "--validate-only", "--as-of", "2026-10-19")
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "放弃需要填写放弃原因" not in ok.stdout
