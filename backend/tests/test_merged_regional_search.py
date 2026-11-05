"""Merge regressions: synthetic evidence and tracked metadata, never paid APIs."""

import json
from datetime import time
from pathlib import Path
import pytest
from app.services.region_registry_service import (
    CategoryDefinition,
    RuleProfile,
    RegionContext,
    get_registry,
)
from app.services.waste_guide_service import WasteGuideService, RetrievedDocument


def context():
    profile = RuleProfile(
        {
            code: CategoryDefinition(code, code, time(8))
            for code in ["non_burnable", "bulky", "not_collected", "paper", "burnable"]
        },
        Path("/unused.csv"),
        Path("/unused.npz"),
        Path("/unused.json"),
    )
    return RegionContext(
        "90001",
        "a",
        "合成地区",
        "c",
        "p",
        "v1",
        "2026-04-01",
        "2027-03-31",
        profile=profile,
    )


@pytest.mark.parametrize(
    "query,item,expected",
    [
        ("キャップを外した飲料用ペットボトル本体", "キャップ", False),
        ("キャップを外した飲料用ペットボトル本体", "ペットボトル本体", True),
        ("ペットボトル本体から外したキャップだけ", "ペットボトル本体", False),
        ("ペットボトル本体から外したキャップだけ", "キャップ", True),
    ],
)
def test_exact_supplement_respects_body_vs_detached_part(query, item, expected):
    assert WasteGuideService._item_name_matches_query(item, query) == expected


@pytest.mark.parametrize(
    "query,clarifications",
    [
        ("合成家具。大人2人で運べません", []),
        ("合成家具", [{"question": "大人2人で運べますか？", "answer": "いいえ"}]),
    ],
)
def test_exact_supplement_does_not_overwrite_an_unhandled_carry_condition(
    query, clarifications
):
    doc = RetrievedDocument(
        '品目: 合成家具\n分類コード: bulky\n条件付き分類コード: ["not_collected"]\n出し方・注意: 大人2人で運べるもの。運べないものは収集不可。',
        0.95,
    )
    assert (
        WasteGuideService._resolve_exact_structured_decision(
            query=query,
            clarifications=clarifications,
            documents=[doc],
            region=context(),
        )
        is None
    )


def test_unhandled_paper_pack_condition_is_left_to_the_regional_classifier():
    doc = RetrievedDocument(
        '品目: 合成紙パック\n分類コード: paper\n条件付き分類コード: ["burnable"]\n出し方・注意: 内側が銀色のものは燃やす',
        0.95,
    )
    assert (
        WasteGuideService._resolve_exact_structured_decision(
            query="内側が銀色の合成紙パック",
            clarifications=[],
            documents=[doc],
            region=context(),
        )
        is None
    )


def test_main_exact_supplement_still_resolves_an_explicit_bag_branch():
    doc = RetrievedDocument(
        '品目: 合成大型品\n分類コード: non_burnable\n条件付き分類コード: ["bulky"]\n出し方・注意: 袋に入らないものはbulky',
        0.95,
    )
    decision = WasteGuideService._resolve_exact_structured_decision(
        query="袋に入らない合成大型品",
        clarifications=[],
        documents=[doc],
        region=context(),
    )
    assert decision and decision.category_code == "bulky"


def test_both_sides_of_merge_share_backend_flutter_metadata_without_runtime_data():
    root = Path(__file__).resolve().parents[2]
    catalog = get_registry()
    ui = json.loads(
        (root / "frontend/assets/data/municipality_catalog.json").read_text()
    )
    entries = {e["id"]: e for e in ui["municipalities"]}
    assert len(entries) == len(ui["municipalities"])
    assert set(entries) == set(catalog.entries)
    assert {
        "38215",
        "38207",
        "38402",
        "38506",
        "38488",
        "38484",
        "38422",
        "38401",
    } <= set(entries)
    for city, entry in entries.items():
        registry = catalog.registry(city)
        expected = {k: v for k, v in registry.data.items() if k != "rule_profiles"}
        assert (
            json.loads((root / "frontend" / entry["registry_asset"]).read_text())
            == expected
        )
        assert entry["version"] == registry.data["version"]
        for key, profile in registry.profiles.items():
            cats = entry["profiles"][key]["categories"]
            assert set(cats) == set(profile.categories)
            for code, definition in profile.categories.items():
                value = cats[code]
                assert value["name"] == definition.name
                assert value.get("collection_type_id") == definition.collection_type_id
                assert value.get("cutoff") == (
                    definition.cutoff.strftime("%H:%M") if definition.cutoff else None
                )
                assert value.get("time_note", "") == definition.time_note


@pytest.mark.parametrize("washed", ["水洗いした", "水洗いしました", "水洗い済み"])
def test_confirmed_water_washing_is_not_asked_again_after_main_merge(washed):
    doc = RetrievedDocument(
        '品目: 合成トレイ\n分類コード: paper\n条件付き分類コード: ["burnable"]\n出し方・注意: 汚れが落ちないものはburnable',
        0.95,
    )
    query = washed + "合成トレイ"
    region = context()
    decision = WasteGuideService._resolve_exact_structured_decision(
        query=query, clarifications=[], documents=[doc], region=region
    )
    assert decision and decision.category_code == "paper"
    assert (
        WasteGuideService._conditional_evidence_question(
            query=query,
            clarifications=[],
            documents=[doc],
            region=region,
            selected_evidence_indexes=(1,),
        )
        is None
    )


def test_exact_primary_keeps_official_shared_disposal_guidance():
    doc = RetrievedDocument(
        "品目: 合成紙品\n分類コード: paper\n出し方・注意: 汚れを落とす\n区分共通の出し方（個別条件優先）: 指定の方法で束ね、当日8時までに出す",
        0.95,
    )
    decision = WasteGuideService._resolve_exact_structured_decision(
        query="合成紙品", clarifications=[], documents=[doc], region=context()
    )
    assert decision and "汚れを落とす" in decision.disposal_instructions
    assert "当日8時まで" in decision.disposal_instructions


def test_exact_alternate_does_not_inherit_primary_stream_instructions():
    doc = RetrievedDocument(
        '品目: 合成大型品\n分類コード: non_burnable\n条件付き分類コード: ["bulky"]\n出し方・注意: 袋に入らないものはbulky\n区分共通の出し方: 小物を不燃ごみの袋へ',
        0.95,
    )
    decision = WasteGuideService._resolve_exact_structured_decision(
        query="袋に入らない合成大型品",
        clarifications=[],
        documents=[doc],
        region=context(),
    )
    assert decision and decision.category_code == "bulky"
    assert "小物を不燃ごみの袋へ" not in decision.disposal_instructions
