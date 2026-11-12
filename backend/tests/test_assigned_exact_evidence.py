"""Assigned municipalities resolve exact official rows without extra AWS calls."""

from __future__ import annotations

import pytest

from app.services.item_search_service import ItemSearchService
from app.services.region_registry_service import get_registry
from app.services.waste_guide_service import RetrievedDocument, WasteGuideService


def official_documents(municipality_id: str, district_id: str, query: str):
    region = get_registry().resolve(municipality_id, district_id)
    search = ItemSearchService(
        items_path=region.asset_path("items_path"),
        municipality_id=municipality_id,
    )
    documents = WasteGuideService._exact_item_documents(
        search=search,
        query=query,
        region=region,
    )
    assert documents, query
    return region, documents


@pytest.mark.parametrize(
    ("municipality_id", "district_id", "query", "clarifications", "category"),
    [
        ("38207", "38207-main-01", "指定ごみ袋に入る扇風機", [], "non_burnable"),
        (
            "38402",
            "38402-asou",
            "衣装ケースを捨てたい",
            [
                {
                    "question": "砥部町の指定袋に入る大きさですか？",
                    "answer": "いいえ、入りません",
                }
            ],
            "facility_dropoff",
        ),
        ("38402", "38402-asou", "汚れが落ちない油のプラスチック容器", [], "burnable"),
        ("38506", "38506-block-1", "木製で指定袋に入るテニスラケット", [], "burnable"),
        ("38422", "38422-uchiko-a", "空のペットボトル", [], "pet_bottles"),
        ("38422", "38422-uchiko-a", "石製のうすを処分したい", [], "not_collected"),
        (
            "38401",
            "38401-masaki-school",
            "IHクッキングヒーターを捨てたい",
            [
                {
                    "question": "45リットルの袋に入る大きさですか？",
                    "answer": "いいえ、入りません",
                }
            ],
            "bulky",
        ),
        ("38401", "38401-masaki-school", "汚れを取り除いた食品用トレイ", [], "plastic"),
    ],
)
def test_explicit_conditions_resolve_from_exact_official_evidence(
    municipality_id, district_id, query, clarifications, category
):
    region, documents = official_documents(municipality_id, district_id, query)

    decision = WasteGuideService._resolve_exact_structured_decision(
        query=query,
        clarifications=clarifications,
        documents=documents,
        region=region,
    )

    assert decision is not None
    assert decision.category_code == category
    assert len(decision.evidence_indexes) == 1
    assert 1 <= decision.evidence_indexes[0] <= len(documents)


@pytest.mark.parametrize(
    ("municipality_id", "district_id", "query", "expected"),
    [
        ("38207", "38207-main-01", "扇風機を捨てたい", "袋"),
        ("38402", "38402-asou", "衣装ケースを捨てたい", "袋"),
        ("38506", "38506-block-1", "ガステーブルを捨てたい", "袋"),
        ("38484", "38484-matsumaru", "圧力鍋を捨てたい", "袋"),
        ("38422", "38422-uchiko-a", "アイロン台を捨てたい", "袋"),
        ("38401", "38401-masaki-school", "IHクッキングヒーターを捨てたい", "45"),
        ("38488", "38488-izumi", "衣装ケースを捨てたい", "何製"),
    ],
)
def test_missing_official_condition_produces_specific_question(
    municipality_id, district_id, query, expected
):
    region, documents = official_documents(municipality_id, district_id, query)

    question = WasteGuideService._conditional_evidence_question(
        query=query,
        clarifications=[],
        documents=documents,
        region=region,
    )

    assert question is not None
    assert expected in question


class WrongVectorGateway:
    def retrieve(self, query):
        return [
            RetrievedDocument(
                text="品目: 鉛筆削り\n分類コード: nonburnable\n分類: 不燃",
                score=0.99,
                uri="regional://38422/uchiko/uchiko-2026.1/items/wrong",
            )
        ]


def test_original_exact_item_precedes_hallucinated_rewrite_candidate(monkeypatch):
    monkeypatch.setattr("app.config.LEXICAL_SEARCH_ENABLED", False)
    service = WasteGuideService(gateway=WrongVectorGateway())

    documents = service.retrieve(
        rewritten_query="石製筆削り 処分",
        original_query="石製のうすを処分したい",
        municipality_id="38422",
        district_id="38422-uchiko-a",
    )

    assert documents[0].text.startswith("品目: うす（石製・木製）")
    assert documents[0].uri.endswith("/items/uchiko-0057")


def test_item_search_normalizes_isho_spelling_variant():
    region = get_registry().resolve("38402", "38402-asou")
    search = ItemSearchService(
        items_path=region.asset_path("items_path"), municipality_id="38402"
    )

    assert search.search("衣装ケース", limit=1)[0].item == "衣裳ケース"


@pytest.mark.parametrize(
    "query,expected",
    [
        ("汚れが落ちない油のプラスチック容器", "burnable"),
        ("水洗いして汚れを落とした油のプラスチック容器", "plastic_packaging"),
        ("油のプラスチック容器", None),
    ],
)
def test_tobe_oil_container_uses_only_its_explicit_cleaning_branch(query, expected):
    region, documents = official_documents("38402", "38402-asou", query)
    decision = WasteGuideService._resolve_exact_structured_decision(
        query=query, clarifications=[], documents=documents, region=region
    )
    assert (decision.category_code if decision else None) == expected


def test_tobe_dirty_rule_is_not_borrowed_from_another_item_or_shared_guidance():
    region, documents = official_documents(
        "38402", "38402-asou", "汚れが落ちない油のプラスチック容器"
    )
    documents = [
        RetrievedDocument(
            text=(
                "品目: 油容器(プラ製)\n分類コード: plastic_packaging\n"
                "分類: プラスチック製容器包装\n出し方・注意: すすいで出す\n"
                "区分共通の出し方（上記の品目固有条件を優先）: 汚れが落ちないものは可燃ごみ"
            ),
            score=1,
        ),
        *documents,
    ]
    decision = WasteGuideService._resolve_exact_structured_decision(
        query="汚れが落ちない油のプラスチック容器",
        clarifications=[],
        documents=documents,
        region=region,
    )
    assert decision is None or decision.category_code == "plastic_packaging"
