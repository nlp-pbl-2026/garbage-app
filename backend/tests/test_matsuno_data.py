"""Synthetic Matsuno data tests: no network, official files or Bedrock."""
from datetime import date
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import matsuno_data
from matsuno_pdf import category_options, extract_items_from_pages


class FakePage:
    def __init__(self, rows):
        self.rows = rows

    def extract_tables(self):
        return [self.rows]


def test_weekly_and_nth_weekday_rules_apply_reviewed_closures():
    start = date(2026, 4, 1)
    end = date(2027, 3, 31)

    burnable = matsuno_data._rule_dates("毎週月・木", start, end)
    special = matsuno_data._rule_dates("第2・第4水", start, end)

    assert len(burnable) == 103
    assert date(2026, 12, 31) not in burnable
    assert burnable[0] == date(2026, 4, 2)
    assert burnable[-1] == date(2027, 3, 29)
    assert len(special) == 24
    assert all(value.weekday() == 2 for value in special)
    assert all(8 <= value.day <= 28 for value in special)


def test_ruled_table_parser_recovers_merged_category_continuation():
    page = FakePage([
        ["品名", "分類", "備考"],
        ["充電式電池", None, "販売店または回収ボックスへ"],
        [None, "家 電", None],
        ["枝切りばさみ", "粗 大", "指定袋に入れば不燃へ"],
    ])

    items = extract_items_from_pages([page], start_page=22)

    assert items[0] == {
        "item": "充電式電池",
        "source_category": "家電",
        "note": "販売店または回収ボックスへ",
        "source_page": 22,
        "category": "small_appliances",
        "category_options": [],
        "item_id": "matsuno-0001",
    }
    assert items[1]["category"] == "bulky"
    assert items[1]["category_options"] == ["nonburnable"]


def test_prohibited_category_phrase_is_not_an_alternative():
    assert category_options("古紙に混ぜないこと", "burnable") == []
    assert category_options("汚れたものは可燃へ", "plastic") == ["burnable"]


def test_reviewed_registry_has_eleven_registered_areas():
    registry = json.loads(
        (ROOT / "data/regions/matsuno/registry.json").read_text(encoding="utf-8")
    )
    reviews = json.loads(
        (ROOT / "data/regions/matsuno/calendar_reviews.json").read_text(encoding="utf-8")
    )
    item_reviews = json.loads(
        (ROOT / "data/regions/matsuno/item_reviews.json").read_text(encoding="utf-8")
    )
    catalog = json.loads(
        (ROOT / "data/regions/catalog.json").read_text(encoding="utf-8")
    )

    assert registry["municipality_id"] == "38484"
    assert len(registry["collection_areas"]) == 11
    assert len(reviews["areas"]) == 11
    assert item_reviews["official_items"] == 1434
    assert {"matsuno-yoshino", "matsuno-kuzukawa"} <= {
        area["calendar_id"] for area in registry["collection_areas"]
    }
    assert all(area["needs_local_confirmation"] for area in registry["collection_areas"])
    assert any(item["id"] == "38484" for item in catalog["municipalities"])
    assert (ROOT / "data/regions/matsuno/knowledge/index_manifest.json").exists()


def test_stale_standalone_calendar_is_not_used_for_generated_dates():
    sources = json.loads(
        (ROOT / "data/regions/matsuno/sources.json").read_text(encoding="utf-8")
    )
    reviews = json.loads(
        (ROOT / "data/regions/matsuno/calendar_reviews.json").read_text(encoding="utf-8")
    )

    assert "2017 reference" in sources["source_notes"]["calendar.pdf"]
    assert sources["source_notes"]["sorting-book.pdf"].startswith("Current source")
    assert reviews["source_url"].endswith("7083.pdf#page=3")
    assert reviews["verification"]["stale_source_excluded"].endswith("1714.pdf")


def test_matsuno_workflow_never_imports_or_invokes_bedrock():
    source = (ROOT / "scripts/matsuno_data.py").read_text(encoding="utf-8").lower()
    assert "boto3" not in source
    assert "invoke_model" not in source
    assert "build_regional_embeddings" not in source
