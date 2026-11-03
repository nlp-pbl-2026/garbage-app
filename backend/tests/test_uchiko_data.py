"""Synthetic Uchiko data tests: no network, official files or Bedrock."""
from datetime import date
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import uchiko_data
from uchiko_pdf import (
    category_options,
    extract_items_from_pages,
    extract_resource_tables_from_page,
)


class FakePage:
    def __init__(self, *tables):
        self.tables = list(tables)

    def extract_tables(self):
        return self.tables


def test_weekly_rules_remove_only_official_no_collection_dates():
    values = uchiko_data._weekly_dates(
        "毎週火・金", ("2026-01-02", "2026-05-05")
    )

    assert len(values) == 102
    assert "2026-01-02" not in values
    assert "2026-05-05" not in values
    assert values[0] == "2026-01-06"
    assert values[-1] == "2026-12-29"
    assert all(date.fromisoformat(value).weekday() in {1, 4} for value in values)


def test_item_parser_repairs_split_parenthesis_and_preserves_conditions():
    page = FakePage([
        ["", "品目", "種類", "備考"],
        ["せ", "洗剤容器（紙・プラスチック・詰替え容器", "）可燃", ""],
        ["て", "テニスラケット", "（素材）", "金属製は不燃ごみ。カーボン製は可燃ごみ。袋に入らないものは粗大"],
    ])

    items = extract_items_from_pages([page])

    assert items[0]["item"] == "洗剤容器（紙・プラスチック・詰替え容器）"
    assert items[0]["category"] == "burnable"
    assert items[1]["category"] == "material_dependent"
    assert items[1]["category_options"] == ["bulky", "nonburnable", "burnable"]


def test_literal_resource_table_keeps_substitution_dates():
    header = ["ごみの種類", None, "収集曜日"] + [f"{month}月" for month in range(1, 13)]
    table = [
        header,
        ["資源ごみ", "古紙", "第1火曜日", "6", "3", "3", "7", "※\n8", "2", "7", "4", "1", "6", "3", "1"],
        [None, "空き缶", "第2火曜日", "13", "10", "10", "14", "12", "9", "14", "11", "8", "13", "10", "8"],
        [None, "空きびん、ペットボトル\n白色トレイ、布・古着", "第3火曜日", "20", "17", "17", "21", "19", "16", "21", "18", "15", "20", "17", "15"],
        [None, "燃えないごみ", "第4火曜日", "27", "24", "24", "28", "26", "23", "28", "25", "22", "27", "24", "22"],
    ]

    result = extract_resource_tables_from_page(FakePage(table))[0]

    assert result["days"]["2026-05-08"] == ["waste_paper"]
    assert result["days"]["2026-05-19"] == [
        "bottles", "pet_bottles", "textiles", "white_trays"
    ]
    assert result["rules"]["nonburnable"] == "第4火曜日"


def test_category_options_capture_size_area_and_material_conditions():
    assert category_options("※一辺が20㎝以上のものは不燃ごみ", "cans") == [
        "nonburnable"
    ]
    assert category_options(
        "※生ごみ分別収集地区のみ。その他の地区は可燃ごみ", "organic"
    ) == ["burnable"]
    assert category_options("袋に入らないものは粗大", "nonburnable") == ["bulky"]


def test_reviewed_registry_has_26_profiles_and_calendar_year_boundary():
    registry = json.loads(
        (ROOT / "data/regions/uchiko/registry.json").read_text(encoding="utf-8")
    )
    reviews = json.loads(
        (ROOT / "data/regions/uchiko/calendar_reviews.json").read_text(encoding="utf-8")
    )
    item_reviews = json.loads(
        (ROOT / "data/regions/uchiko/item_reviews.json").read_text(encoding="utf-8")
    )
    catalog = json.loads(
        (ROOT / "data/regions/catalog.json").read_text(encoding="utf-8")
    )

    assert registry["municipality_id"] == "38422"
    assert registry["valid_from"] == "2026-01-01"
    assert registry["valid_to"] == "2026-12-31"
    assert len(registry["collection_areas"]) == 26
    assert len(reviews["areas"]) == 26
    assert reviews["verification"]["calendar_basis"].startswith("Calendar year")
    assert item_reviews["official_items"] == 876
    assert all(area["needs_local_confirmation"] for area in registry["collection_areas"])
    assert all(item["id"] != "38422" for item in catalog["municipalities"])
    assert not (ROOT / "data/regions/uchiko/knowledge/item_embeddings.npz").exists()


def test_uchiko_workflow_never_imports_or_invokes_bedrock():
    source = (ROOT / "scripts/uchiko_data.py").read_text(encoding="utf-8").lower()
    assert "boto3" not in source
    assert "invoke_model" not in source
    assert "build_regional_embeddings" not in source
