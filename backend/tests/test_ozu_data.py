"""Synthetic Ozu source/parser tests: no official files, network or Bedrock."""
from datetime import date
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import ozu_data as data
from ozu_pdf import Grid, _vector_anchor


def test_official_html_calendar_rows_keep_region_number_title_area_and_attachment(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setattr(data, "EXPECTED_CALENDARS", {key: 1 for key in data.REGION_NAMES})
    for offset, region in enumerate(data.REGION_NAMES):
        attachment = 12345 + offset
        (source / f"{region}.html").write_text(
            f'<table><tr><td>１</td><td><a href="/uploaded/attachment/{attachment}.pdf">'
            '令和８年度　試験地区 [PDFファイル／1KB]</a></td><td>試験町全域</td></tr></table>',
            encoding="utf-8",
        )
    entries = data.calendar_entries(tmp_path)
    assert len(entries) == 4
    assert entries[0]["number"] == 1
    assert entries[0]["title"] == "令和８年度　試験地区"
    assert entries[0]["area"] == "試験町全域"
    assert entries[0]["filename"] == "calendar-12345.pdf"


def test_dictionary_category_mapping_preserves_city_specific_resource_groups():
    assert data.category_code("資源（缶・びん）", "空き缶") == "cans_bottles"
    assert data.category_code("資源（発泡スチロール）", "食品トレイ") == "pet_styro"
    assert data.category_code("資源ごみ", "衣装ケース（紙製）") == "paper_cloth"
    assert data.category_code("資源ごみ", "一斗缶") == "cans_bottles"
    assert data.category_code("１ページ３を参照【メーカー回収】", "パソコン") == "not_collected"


def test_dictionary_rows_keep_material_variants_and_do_not_treat_bag_name_as_category_option():
    rules = {"categories": {
        "burnable": {"name": "もやすごみ", "instructions": "burn"},
        "non_burnable": {"name": "もやさないごみ", "instructions": "non"},
    }}
    words = [
        {"page": 6, "x": 70, "y": 100, "text": "植木鉢"},
        {"page": 6, "x": 127, "y": 90, "text": "素焼き"},
        {"page": 6, "x": 192, "y": 90, "text": "もやさないごみ"},
        {"page": 6, "x": 290, "y": 90, "text": "もやさないごみ袋に入れて出す。"},
        {"page": 6, "x": 127, "y": 110, "text": "プラスチック製"},
        {"page": 6, "x": 192, "y": 110, "text": "もやすごみ"},
        {"page": 6, "x": 290, "y": 110, "text": "もやすごみ袋に入れて出す。"},
    ]
    rows = data.item_rows_from_words(words, rules, expected_count=2)
    assert [(row["item"], row["category"]) for row in rows] == [
        ("植木鉢（素焼き）", "non_burnable"),
        ("植木鉢（プラスチック製）", "burnable"),
    ]
    assert all(row["category_options"] == "[]" for row in rows)


def test_grid_uses_irregular_official_column_widths_without_shifting_weekdays():
    grid = Grid(2026, 4, (29, 72, 114, 168, 219, 290, 341, 383),
                (246, 286, 325, 365, 405, 444))
    assert grid.locate(240, 380) == date(2026, 4, 23)
    assert grid.locate(320, 380) == date(2026, 4, 24)
    assert grid.locate(100, 420) == date(2026, 4, 27)


def test_vector_signatures_distinguish_each_collection_icon():
    class Rect:
        def __init__(self, width, height):
            self.width = width
            self.height = height

    def drawing(width, height, items):
        return {"rect": Rect(width, height), "items": [None] * items}

    assert _vector_anchor(drawing(18.4, 19.2, 11)) == ("burnable",)
    assert _vector_anchor(drawing(15.2, 14.0, 17)) == ("non_burnable",)
    assert _vector_anchor(drawing(10.8, 24.9, 10)) == ("cans_bottles",)
    assert _vector_anchor(drawing(10.9, 27.1, 16)) == ("pet_styro",)
    assert _vector_anchor(drawing(22.4, 18.2, 39)) == ("paper_cloth",)
    assert _vector_anchor(drawing(12.8, 23.6, 8)) == ("hazardous",)
    assert _vector_anchor(drawing(18.0, 3.2, 11)) == ("bulky",)
