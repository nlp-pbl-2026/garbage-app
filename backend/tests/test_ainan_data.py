"""Synthetic Ainan data tests: no network, official files, OCR or Bedrock."""
from datetime import date
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import ainan_data
from ainan_pdf import CATEGORY_COLORS, _categories, _normalise


def _schedule_table(block: int, burnable: str, weekday: str) -> str:
    return f"""
    <h3>{block}. 地区{block}</h3>
    <table>
      <tr><th>区分</th><th>ブロック</th><th>収集日</th></tr>
      <tr><td>可燃ごみ</td><td>{block}</td><td>{burnable}</td></tr>
      <tr><td>びん・缶</td><td>{block}</td><td>第1{weekday}曜日</td></tr>
      <tr><td>ペットボトル</td><td>{block}</td><td>第2{weekday}曜日</td></tr>
      <tr><td>不燃物</td><td>{block}</td><td>第3{weekday}曜日</td></tr>
    </table>
    """


def test_schedule_html_requires_and_preserves_all_eight_blocks(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    html = "".join(
        _schedule_table(
            block,
            "月曜日、水曜日、金曜日" if block % 2 else "火曜日、木曜日、土曜日",
            "火" if block % 2 else "木",
        )
        for block in range(1, 9)
    )
    (source / "schedule-page.html").write_text(html, encoding="utf-8")
    monkeypatch.setattr(ainan_data, "DATA", tmp_path)

    rules = ainan_data.schedule_rules()

    assert [rule["number"] for rule in rules] == list(range(1, 9))
    assert rules[0]["address_labels"] == ["地区1"]
    assert rules[0]["rules"]["containers"] == "第1火曜日"
    assert rules[1]["rules"]["burnable"] == "火曜日、木曜日、土曜日"


def test_weekly_and_nth_weekday_rules_generate_all_2026_dates():
    weekly = ainan_data._rule_dates("月曜日、水曜日、金曜日", 2026)
    fourth_thursdays = ainan_data._rule_dates("第4木曜日", 2026)

    assert len(weekly) == 156
    assert weekly[0] == date(2026, 1, 2)
    assert weekly[-1] == date(2026, 12, 30)
    assert len(fourth_thursdays) == 12
    assert all(value.weekday() == 3 and 22 <= value.day <= 28 for value in fourth_thursdays)


def test_official_category_colors_preserve_multiple_disposal_options():
    array = np.full((100, 800, 3), 255, dtype=np.uint8)
    array[14:87, 493:575] = CATEGORY_COLORS["nonburnable"]
    array[14:87, 575:663] = CATEGORY_COLORS["small_appliances"]

    assert _categories(array, 10, 90, "不燃 小型家電", "電話機") == [
        "nonburnable",
        "small_appliances",
    ]


def test_ocr_normalisation_fixes_known_windows_ocr_confusions():
    assert _normalise("ボンべ") == "ボンベ"
    assert _normalise("モバイルバッテリ-") == "モバイルバッテリー"


def test_reviewed_registry_has_eight_blocks_without_embedding_registration():
    registry = json.loads(
        (ROOT / "data/regions/ainan/registry.json").read_text(encoding="utf-8")
    )
    reviews = json.loads(
        (ROOT / "data/regions/ainan/calendar_reviews.json").read_text(encoding="utf-8")
    )
    catalog = json.loads(
        (ROOT / "data/regions/catalog.json").read_text(encoding="utf-8")
    )

    assert registry["municipality_id"] == "38506"
    assert [area["calendar_id"] for area in registry["collection_areas"]] == [
        f"ainan-block-{number}" for number in range(1, 9)
    ]
    assert all(area["needs_local_confirmation"] for area in registry["collection_areas"])
    assert len(reviews["blocks"]) == 8
    assert reviews["blocks"][5]["rules"] == reviews["blocks"][1]["rules"]
    assert all(item["id"] != "38506" for item in catalog["municipalities"])


def test_ainan_workflow_never_imports_or_invokes_bedrock():
    source = (ROOT / "scripts/ainan_data.py").read_text(encoding="utf-8").lower()
    assert "boto3" not in source
    assert "invoke_model" not in source
    assert "build_regional_embeddings" not in source
