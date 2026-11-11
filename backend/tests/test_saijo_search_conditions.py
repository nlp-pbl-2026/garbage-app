"""Synthetic regressions for conditions exposed by the Saijo live evaluation."""

from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.waste_guide_service import (
    WasteGuideService as Service,
    RetrievedDocument,
)


def region():
    names = {
        "burnable": "もえるごみ",
        "non_burnable": "もえないごみ",
        "pet_bottles": "ペットボトル",
        "bulky": "粗大ごみ",
        "not_collected": "市では収集しない",
    }
    return SimpleNamespace(
        municipality_id="99999",
        category_codes=list(names),
        category_names=names,
        rules=SimpleNamespace(size_threshold_cm=None, size_question="袋に入りますか？"),
    )


def doc(item, code, note="", options="[]"):
    return RetrievedDocument(
        text=f"品目: {item}\n分類コード: {code}\n条件付き分類コード: {options}\n出し方・注意: {note}",
        score=0.9,
        uri="regional://99999/citywide/test/item",
    )


def test_cap_evidence_cannot_authorize_pet_body_category_in_its_note():
    d = doc(
        "ペットボトルから取り外したプラスチック製キャップ",
        "burnable",
        "ペットボトルから外したプラ製キャップだけはもえるごみ。本体は別。",
    )
    result = Service._resolve_exact_structured_decision(
        query="ペットボトルから取り外したプラスチック製キャップだけ",
        clarifications=[],
        documents=[d],
        region=region(),
    )
    assert result.category_code == "burnable"


def test_danball_spelling_selects_cardboard_before_bowl():
    docs = [
        doc("ボール（調理用）", "non_burnable"),
        doc("ダンボール", "burnable", "汚れが落ちないものはもえるごみ"),
    ]
    matches = Service._matching_structured_documents(
        query="汚れが取れない段ボール", documents=docs
    )
    assert matches[0][2] == "ダンボール"


def test_numeric_qualifiers_do_not_default_to_first_unevaluated_range():
    docs = [doc("木（3cm以上5cm未満）", "bulky"), doc("木（5cm以上）", "not_collected")]
    assert (
        Service._resolve_exact_structured_decision(
            query="直径6cmの木", clarifications=[], documents=docs, region=region()
        )
        is None
    )


def test_short_material_branch_requires_missing_material_but_keeps_answer():
    d = doc("アクセサリー", "burnable", "金属製はもえないごみへ", '["non_burnable"]')
    assert Service._conditional_evidence_question(
        query="アクセサリー", clarifications=[], documents=[d], region=region()
    )
    assert (
        Service._conditional_evidence_question(
            query="アクセサリー",
            clarifications=[{"question": "何製ですか？", "answer": "金属です"}],
            documents=[d],
            region=region(),
        )
        is None
    )


@pytest.mark.parametrize(
    "query,clarifications,question",
    [
        ("プラスチック製おもちゃ", [], True),
        ("ティッシュ箱より小さいプラスチック製おもちゃ", [], False),
        ("ティッシュ箱より大きいプラスチック製おもちゃ", [], False),
        (
            "プラスチック製おもちゃ",
            [{"question": "ティッシュ箱より小さいですか？", "answer": "はい"}],
            False,
        ),
        (
            "プラスチック製おもちゃ",
            [{"question": "ティッシュ箱より小さいですか？", "answer": "いいえ"}],
            False,
        ),
    ],
)
def test_comparative_size_is_required_only_when_unanswered(
    query, clarifications, question
):
    d = doc(
        "おもちゃ（プラスチック製）",
        "non_burnable",
        "ティッシュペーパーの箱（縦26cm×横11cm×高さ6cm）より小さいものはもえるごみへ",
        '["burnable"]',
    )
    result = Service._conditional_evidence_question(
        query=query, clarifications=clarifications, documents=[d], region=region()
    )
    assert bool(result) == question


@pytest.mark.parametrize(
    "text,expected",
    [
        ("洗ってラベルとキャップを外した飲料PET本体", True),
        ("水洗いしたPET本体", True),
        ("洗っていないPET本体", False),
        ("洗ってくださいと言われたPET本体", False),
    ],
)
def test_cleaning_completion_is_not_lost_in_connected_sentence(text, expected):
    assert Service._cleaning_is_confirmed(text) == expected


@pytest.mark.parametrize(
    "qualifier,query,excluded",
    [
        ("幹の太さが3cm未満", "幹の太さ直径6cmの剪定木", True),
        ("幹の太さが3cm以上5cm未満", "幹の太さ直径6cmの剪定木", True),
        ("幹の太さが3cm以上5cm未満", "幹の太さ直径4cmの剪定木", False),
        ("幹の太さが3cm以上5cm未満", "幹の太さ直径5cmの剪定木", True),
        ("幹の太さが3cm以上5cm未満", "幹の太さ直径60mmの剪定木", True),
        ("幹の太さが5cm以上又は長辺2m以上", "直径4cmの剪定木", False),
        ("幹の太さが3cm未満", "剪定木の束の直径30cm", False),
        ("幹の太さが3cm未満", "幹の太さ直径6cmかもしれない剪定木", False),
    ],
)
def test_explicit_diameter_rejects_only_demonstrably_inapplicable_same_item(
    qualifier, query, excluded
):
    assert (
        Service._diameter_excludes_document(
            doc(f"剪定木（{qualifier}）", "bulky"), query=query, clarifications=[]
        )
        == excluded
    )


@pytest.mark.parametrize(
    "query,expected",
    [
        ("長さ2mちょうどの剪定木", True),
        ("長辺200cmの剪定木", True),
        ("長さ1mの剪定木", False),
        ("長さ2m未満に切った剪定木", False),
        ("長さ2mの家具", False),
    ],
)
def test_conflicting_inclusive_length_boundary_is_held_not_guessed(query, expected):
    documents = [
        doc("剪定木（幹の太さ3cm以上5cm未満）", "bulky", "長さ2m以下にする"),
        doc("剪定木（幹の太さ5cm以上又は長辺2m以上）", "not_collected"),
    ]
    assert (
        Service._conflicting_length_boundary(documents, query=query, clarifications=[])
        == expected
    )


@pytest.mark.parametrize(
    "name,label",
    [("西条地域：大久保地区", "西条地域：大久保地区"), ("清水", "清水地区")],
)
def test_answer_does_not_duplicate_district_suffix(name, label):
    from app.services.waste_guide_service import ClassificationDecision

    selected = region()
    selected.area_name = name
    selected.rules.categories = {
        "burnable": SimpleNamespace(time_note="", answer_note="")
    }
    answer = Service._build_answer(
        ClassificationDecision(
            is_resolved=True, item_name="紙くず", category_code="burnable"
        ),
        SimpleNamespace(display_date="2026年11月12日"),
        region=selected,
    )
    assert label + "の次回収集日" in answer
    assert "地区地区" not in answer


def test_official_pet_body_alias_matches_the_explicit_body_not_detached_cap():
    name = "ペットボトル類の本体"
    query = "キャップ・ラベルを外して水洗いしたPETマーク付き飲料用ペットボトル本体。プラマークはありません"
    assert Service._item_name_matches_query(name, query)
    assert not Service._item_name_matches_query(
        name, "ペットボトルから取り外したプラスチック製キャップだけ"
    )
