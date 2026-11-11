"""Source-independent regressions for failures found in Imabari live cases."""

import pytest

from app.services.waste_guide_service import WasteGuideService as Service
from app.services.waste_guide_service import RetrievedDocument
from app.services.region_registry_service import (
    CategoryDefinition,
    RegionContext,
    RuleProfile,
)
from pathlib import Path


@pytest.mark.parametrize(
    "query",
    [
        "水洗いして汚れを落とした白色の食品トレイ",
        "プラスチック製バケツ、長辺20cmで洗って汚れを落としました",
        "汚れを落としてあります",
        "汚れを除去しました",
    ],
)
def test_completed_cleaning_is_not_asked_again(query):
    assert Service._cleaning_is_confirmed(query)


@pytest.mark.parametrize(
    "query",
    [
        "水洗いしていない食品トレイ",
        "洗っても汚れが落ちない",
        "汚れを落とせない",
        "汚れを落としたい",
        "汚れを落としていません",
    ],
)
def test_incomplete_or_negated_cleaning_is_not_confirmed(query):
    assert not Service._cleaning_is_confirmed(query)


@pytest.mark.parametrize(
    "item", ["電池", "リチウムイオン電池", "小型リチウムイオン電池", "バッテリー"]
)
def test_nonremovable_battery_is_not_an_exact_standalone_battery(item):
    query = "小型の充電式家電でリチウムイオン電池が取り外せません"
    assert not Service._item_name_matches_query(item, query)


def test_explicit_loose_battery_still_matches():
    assert Service._item_name_matches_query(
        "リチウムイオン電池", "小型家電から取り外したリチウムイオン電池を捨てたい"
    )
    assert Service._item_name_matches_query(
        "モバイルバッテリー", "モバイルバッテリーを捨てたい"
    )


def test_appliance_with_nonremovable_battery_still_matches_its_own_name():
    assert Service._item_name_matches_query(
        "携帯電話", "リチウムイオン電池を外せない携帯電話本体"
    )


@pytest.mark.parametrize(
    "color,expected",
    [
        ("白色", "resources"),
        ("色付き", "plastics"),
        ("白色以外", "plastics"),
        ("", None),
    ],
)
def test_exact_tray_candidates_keep_their_official_colour_condition(color, expected):
    profile = RuleProfile(
        categories={
            "resources": CategoryDefinition("資源"),
            "plastics": CategoryDefinition("プラ"),
        },
        items_path=Path("unused.csv"),
        embedding_index_path=Path("unused.npz"),
        calendar_path=Path("unused.json"),
    )
    region = RegionContext(
        "test",
        "a",
        "fixture",
        "c",
        "p",
        "v",
        "2026-04-01",
        "2027-03-31",
        municipality_name="fixture",
        profile=profile,
    )
    docs = [
        RetrievedDocument(
            text=f"品目: トレイ（食品用・{label}）\n分類コード: {code}\n分類: {label}\n出し方・注意: 水洗いする",
            score=0.8,
            uri=region.evidence_prefix + str(i),
        )
        for i, (label, code) in enumerate(
            [("白色", "resources"), ("白色以外", "plastics")]
        )
    ]
    result = Service._resolve_exact_structured_decision(
        query=f"洗った{color}の食品トレイ",
        clarifications=[],
        documents=docs,
        region=region,
    )
    assert (result.category_code if result else None) == expected
