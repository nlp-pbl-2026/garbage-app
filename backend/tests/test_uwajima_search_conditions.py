"""API-free regressions of official conditional routes, not model guesses."""

from pathlib import Path
import pytest
from app.services.waste_guide_service import (
    WasteGuideService as Service,
    RetrievedDocument,
)
from app.services.region_registry_service import (
    RegionContext,
    RuleProfile,
    CategoryDefinition,
)


def region():
    profile = RuleProfile(
        categories={
            c: CategoryDefinition(c) for c in ["clean_plastics", "burnable", "bulky"]
        },
        items_path=Path("unused.csv"),
        embedding_index_path=Path("unused.npz"),
        calendar_path=Path("unused.json"),
    )
    return RegionContext(
        "90001",
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


def doc():
    return RetrievedDocument(
        text='品目: プラスチック製バケツ\n分類コード: clean_plastics\n条件付き分類コード: ["burnable","bulky"]\n出し方・注意: 洗浄乾燥済み・一辺50cm未満。50cm以上は対象外、袋に入れば可燃、入らなければ粗大。',
        score=0.8,
        uri="regional://fixture",
    )


@pytest.mark.parametrize(
    "size,expected",
    [
        ("49cm", None),
        ("50cm", "burnable"),
        ("500mm", "burnable"),
        ("0.5m", "burnable"),
        ("51cm", "burnable"),
    ],
)
def test_largest_edge_bound_is_strict_and_comes_from_evidence(size, expected):
    result = Service._resolve_recycling_size_exclusion(
        query=f"最大の辺が{size}のプラスチック製バケツ。指定袋に入ります。",
        clarifications=[],
        documents=[doc()],
        region=region(),
    )
    assert (result.category_code if result else None) == expected


def test_bag_dimensions_do_not_become_product_dimensions():
    assert (
        Service._resolve_recycling_size_exclusion(
            query="幅50cmの袋に入るプラスチックのバケツ",
            clarifications=[],
            documents=[doc()],
            region=region(),
        )
        is None
    )
    assert (
        Service._resolve_recycling_size_exclusion(
            query="最大の辺が50cmのバケツ",
            clarifications=[],
            documents=[doc()],
            region=region(),
        )
        is None
    )
    result = Service._resolve_recycling_size_exclusion(
        query="最大の辺が50cmのプラスチックのバケツ",
        clarifications=[dict(question="袋に入りますか", answer="指定袋には入りません")],
        documents=[doc()],
        region=region(),
    )
    assert result.category_code == "bulky"


def test_no_route_is_inferred_without_item_specific_official_exclusion():
    other = RetrievedDocument(
        text="品目: バケツ\n分類コード: burnable\n区分共通の出し方: 一辺50cm未満",
        score=0.8,
        uri="regional://fixture",
    )
    assert (
        Service._resolve_recycling_size_exclusion(
            query="最大の辺が50cmのバケツ。指定袋に入る",
            clarifications=[],
            documents=[other],
            region=region(),
        )
        is None
    )
