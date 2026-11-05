"""Synthetic Kihoku data tests: no network, official files or Bedrock."""
import csv
from datetime import date
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import kihoku_data
from kihoku_pdf import extract_items


def test_weekly_and_twice_monthly_rules_cover_review_period():
    start = date(2026, 4, 1)
    end = date(2026, 12, 31)

    burnable = kihoku_data._rule_dates("月・木", start, end)
    pet = kihoku_data._rule_dates("第1・第3金", start, end)

    assert len(burnable) == 79
    assert burnable[0] == date(2026, 4, 2)
    assert burnable[-1] == date(2026, 12, 31)
    assert len(pet) == 18
    assert all(value.weekday() == 4 for value in pet)
    assert all(1 <= value.day <= 21 for value in pet)


def test_two_column_tsv_parser_preserves_item_category_and_note(tmp_path):
    path = tmp_path / "items.tsv"
    fields = [
        "level", "page_num", "par_num", "block_num", "line_num", "word_num",
        "left", "top", "width", "height", "conf", "text",
    ]
    rows = [
        ["5", "3", "0", "0", "0", "0", "65", "300", "30", "11", "100", "紙くず"],
        ["5", "3", "0", "1", "0", "0", "170", "300", "11", "11", "100", "可"],
        ["5", "3", "0", "1", "0", "1", "184", "300", "11", "11", "100", "燃"],
        ["5", "3", "0", "2", "0", "0", "201", "300", "80", "11", "100", "指定袋へ"],
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(fields)
        writer.writerows(rows)

    items = extract_items(path)

    assert items == [{
        "item": "紙くず",
        "category": "burnable",
        "source_category": "可燃",
        "note": "指定袋へ",
        "source_page": 3,
        "item_id": "kihoku-0001",
    }]


def test_reviewed_registry_has_eight_registered_areas():
    registry = json.loads(
        (ROOT / "data/regions/kihoku/registry.json").read_text(encoding="utf-8")
    )
    reviews = json.loads(
        (ROOT / "data/regions/kihoku/calendar_reviews.json").read_text(encoding="utf-8")
    )
    item_reviews = json.loads(
        (ROOT / "data/regions/kihoku/item_reviews.json").read_text(encoding="utf-8")
    )
    catalog = json.loads(
        (ROOT / "data/regions/catalog.json").read_text(encoding="utf-8")
    )

    assert registry["municipality_id"] == "38488"
    assert len(registry["collection_areas"]) == 8
    assert all(area["needs_local_confirmation"] for area in registry["collection_areas"])
    assert len(reviews["areas"]) == 8
    assert item_reviews["official_items"] == 1219
    assert any(item["id"] == "38488" for item in catalog["municipalities"])
    assert (ROOT / "data/regions/kihoku/knowledge/index_manifest.json").exists()


def test_april_2026_notices_override_or_extend_the_older_item_table():
    rules = json.loads(
        (ROOT / "data/regions/kihoku/official_rules.json").read_text(encoding="utf-8")
    )
    base = {
        "item_id": "test",
        "category": "not_collected",
        "source_category": "禁止",
        "note": "販売店へ",
        "source_page": 1,
    }
    battery = kihoku_data._item_row({**base, "item": "充電式電池"}, rules)
    assert battery["category"] == "rechargeable_batteries"
    assert "令和8年4月" in battery["note"]
    assert battery["source_url"].endswith("18393.pdf#page=2")

    burnable = {**base, "category": "burnable", "source_category": "可燃", "note": ""}
    toothbrush = kihoku_data._item_row({**burnable, "item": "歯ブラシ"}, rules)
    assert toothbrush["category"] == "burnable"
    assert json.loads(toothbrush["category_options"]) == ["clean_plastic"]
    assert "従来どおり可燃ごみ" in toothbrush["note"]

    plastic_container = kihoku_data._item_row(
        {**burnable, "item": "化粧品のボトル・容器（プラ製）"}, rules
    )
    assert json.loads(plastic_container["category_options"]) == ["clean_plastic"]


def test_kihoku_workflow_never_imports_or_invokes_bedrock():
    source = (ROOT / "scripts/kihoku_data.py").read_text(encoding="utf-8").lower()
    assert "boto3" not in source
    assert "invoke_model" not in source
    assert "build_regional_embeddings" not in source
