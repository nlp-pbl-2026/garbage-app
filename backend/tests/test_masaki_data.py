"""Synthetic Masaki source/data tests: no network, official files or Bedrock."""
from datetime import date
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import masaki_data
from masaki_pdf import category_code, category_options, current_note


def test_two_school_zone_rules_and_printed_collection_holidays():
    start = date(2026, 4, 1)
    end = date(2027, 3, 31)
    masaki = masaki_data._calendar_dates(
        masaki_data.AREA_DEFINITIONS[0], start, end
    )
    kitaiyo = masaki_data._calendar_dates(
        masaki_data.AREA_DEFINITIONS[1], start, end
    )

    assert "plastic" in masaki["2026-04-01"]
    assert "pet_bottles" in kitaiyo["2026-04-01"]
    assert "pet_bottles" in masaki["2026-04-03"]
    assert "plastic" in kitaiyo["2026-04-03"]
    assert "burnable" not in masaki.get("2026-12-31", [])
    assert "burnable" not in kitaiyo.get("2026-12-31", [])
    assert "pet_bottles" not in masaki.get("2027-01-01", [])
    assert "plastic" not in kitaiyo.get("2027-01-01", [])
    assert "cans" not in masaki.get("2027-01-02", [])
    assert "hazardous" not in masaki.get("2027-01-16", [])


def test_current_rule_removes_only_superseded_dirty_plastic_fallback():
    outdated = "洗って出す（汚れが取れないときは可燃）"
    current = current_note(outdated, "plastic")

    assert "現行ルール" in current
    assert "プラスチック類" in current
    assert "可燃" not in current
    assert current_note("紙製のふたは可燃", "plastic") == "紙製のふたは可燃"
    assert current_note(outdated, "burnable") == outdated


def test_item_categories_and_explicit_alternatives_are_preserved():
    assert category_code("紙（雑）") == "mixed_paper"
    assert category_code("せんてい") == "pruning"
    assert category_code("廃食用油") == "waste_oil"
    assert category_options(
        "電池は有害。45リットルの袋に入らなければ粗大", "landfill"
    ) == ["bulky", "hazardous"]


def test_reviewed_registry_has_two_registered_school_zones():
    registry = json.loads(
        (ROOT / "data/regions/masaki/registry.json").read_text(encoding="utf-8")
    )
    reviews = json.loads(
        (ROOT / "data/regions/masaki/calendar_reviews.json").read_text(
            encoding="utf-8"
        )
    )
    item_reviews = json.loads(
        (ROOT / "data/regions/masaki/item_reviews.json").read_text(encoding="utf-8")
    )
    catalog = json.loads(
        (ROOT / "data/regions/catalog.json").read_text(encoding="utf-8")
    )

    assert registry["municipality_id"] == "38401"
    assert registry["valid_from"] == "2026-04-01"
    assert registry["valid_to"] == "2027-03-31"
    assert len(registry["collection_areas"]) == 2
    assert len(reviews["areas"]) == 2
    assert item_reviews["official_items"] == 1384
    assert item_reviews["current_rule_overrides"] == 32
    assert all(
        area["needs_local_confirmation"]
        for area in registry["collection_areas"]
    )
    assert any(item["id"] == "38401" for item in catalog["municipalities"])
    assert (
        ROOT / "data/regions/masaki/knowledge/index_manifest.json"
    ).exists()


def test_masaki_workflow_never_imports_or_invokes_bedrock():
    source = (ROOT / "scripts/masaki_data.py").read_text(encoding="utf-8").lower()
    assert "boto3" not in source
    assert "invoke_model" not in source
    assert "build_regional_embeddings" not in source
