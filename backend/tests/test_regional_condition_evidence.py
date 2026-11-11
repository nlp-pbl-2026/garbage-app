"""Synthetic regressions for component names and explicit battery conditions."""

from datetime import time
from pathlib import Path
import pytest
from app.services.region_registry_service import (
    CategoryDefinition,
    RuleProfile,
    RegionContext,
)
from app.services.waste_guide_service import WasteGuideService, RetrievedDocument


def region():
    profile = RuleProfile(
        {
            k: CategoryDefinition(k, k, time(8))
            for k in ["batteries", "direct_delivery", "small_appliances"]
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


def test_plain_pet_row_is_not_the_target_of_a_detached_cap_query():
    assert not WasteGuideService._item_name_matches_query(
        "ペットボトル", "ペットボトルから外したプラスチック製キャップだけ"
    )
    assert WasteGuideService._item_name_matches_query(
        "キャップ", "ペットボトルから外したプラスチック製キャップだけ"
    )
    assert WasteGuideService._item_name_matches_query(
        "ペットボトル", "キャップを外したペットボトル本体"
    )


@pytest.mark.parametrize(
    "item,expected",
    [
        ("プラスチック（包装）フィルム", "プラスチックフィルム"),
        ("クリーム（ハンド）容器", "クリーム容器"),
        ("バケツ（プラ製）", "バケツ"),
    ],
)
def test_item_name_suffix_survives_parenthetical_qualifiers(item, expected):
    assert WasteGuideService._base_item_name(item) == expected


def test_plastic_film_is_not_an_exact_match_for_a_straw():
    documents = [
        RetrievedDocument(
            "品目: プラスチック（包装）フィルム\n分類コード: plastic_packaging", 0.9
        ),
        RetrievedDocument("品目: ストロー\n分類コード: burnable", 0.8),
    ]
    assert [
        i
        for i, *_ in WasteGuideService._matching_structured_documents(
            query="プラスチック製ストロー", documents=documents
        )
    ] == [2]


def test_specific_appliance_precedes_generic_battery_while_preserving_source_indexes():
    documents = [
        RetrievedDocument("品目: 電池\n分類コード: batteries", 0.99),
        RetrievedDocument(
            "品目: 携帯電話（電池取り外し済み）\n分類コード: small_appliances", 0.9
        ),
    ]
    matches = WasteGuideService._matching_structured_documents(
        query="電池を取り外した携帯電話", documents=documents
    )
    assert [i for i, *_ in matches] == [2]


@pytest.mark.parametrize(
    "item,query,expected",
    [
        ("バッテリー", "電池とバッテリーを取り外した携帯電話", False),
        ("電池", "電池を外したラジオ", False),
        ("電池", "携帯電話から取り外した電池", True),
        ("バッテリー", "車のバッテリー", True),
    ],
)
def test_removal_wording_keeps_the_requested_appliance_or_detached_battery(
    item, query, expected
):
    assert WasteGuideService._item_name_matches_query(item, query) == expected


def test_torn_clothes_condition_does_not_ask_washing_again():
    doc = RetrievedDocument(
        '品目: Tシャツ\n分類コード: clothes\n条件付き分類コード: ["burnable"]\n出し方・注意: 汚れが落ちない・破れたものは燃えるごみ',
        0.9,
    )
    assert (
        WasteGuideService._conditional_evidence_question(
            query="汚れが落ちず破れたTシャツ",
            clarifications=[],
            documents=[doc],
            region=region(),
        )
        is None
    )


@pytest.mark.parametrize(
    "query,clarifications,expected",
    [
        ("使わなくなったモバイルバッテリー", [], "取り外せますか"),
        ("正常なモバイルバッテリー", [], "取り外せますか"),
        ("膨張しているモバイルバッテリー", [], None),
        ("電池を取り外せないモバイルバッテリー", [], None),
        ("機器から取り外した正常なモバイルバッテリー", [], None),
        (
            "モバイルバッテリー",
            [{"question": "電池を取り外せますか？", "answer": "はい"}],
            "破損",
        ),
        (
            "モバイルバッテリー",
            [{"question": "電池を取り外せますか？", "answer": "いいえ"}],
            None,
        ),
        (
            "モバイルバッテリー",
            [
                {"question": "電池を取り外せますか？", "answer": "はい"},
                {
                    "question": "電池に破損・変形・膨張はありますか？",
                    "answer": "いいえ",
                },
            ],
            None,
        ),
    ],
)
def test_only_item_specific_official_removal_and_damage_branch_asks(
    query, clarifications, expected
):
    doc = RetrievedDocument(
        '品目: モバイルバッテリー\n分類コード: direct_delivery\n条件付き分類コード: ["batteries"]\n出し方・注意: 電池の取り外し可否や状態が不明なら確認。取り外せない又は膨張時は直接持込。',
        0.9,
    )
    actual = WasteGuideService._conditional_evidence_question(
        query=query, clarifications=clarifications, documents=[doc], region=region()
    )
    if expected is None:
        assert actual is None
    else:
        assert expected in actual


def test_generic_preparation_text_does_not_introduce_an_unrelated_battery_question():
    doc = RetrievedDocument(
        "品目: ラジオ\n分類コード: small_appliances\n区分共通の出し方: モバイルバッテリーの取り外し可否が不明なら確認",
        0.9,
    )
    assert (
        WasteGuideService._conditional_evidence_question(
            query="ラジオ", clarifications=[], documents=[doc], region=region()
        )
        is None
    )
