"""Synthetic Niihama parser/gate tests. No official data or paid calls."""

from io import BytesIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import niihama_data
from niihama_pdf import observed_types, color_code
from app.services.waste_guide_service import RetrievedDocument, WasteGuideService


@pytest.mark.parametrize(
    "note,primary,expected",
    [
        ("30㎝以下は不燃ごみ", "bulky", ["non_burnable"]),
        ("30㎝超えは大型ごみ", "burnable", ["bulky"]),
        ("取っ手も含め30㎝以下は不燃ごみ", "bulky", ["non_burnable"]),
        ("金属製は不燃ごみ", "burnable", ["non_burnable"]),
        ("30㎝超えは清掃センターへ自己搬入", "non_burnable", ["self_delivery"]),
        ("電池は外して有害ごみ", "non_burnable", []),
        ("金具は不燃ごみ", "burnable", []),
        ("中身を使い切る", "bottles_cans", []),
        (
            "内側がアルミコーティングのものや500ml未満のものは燃やすごみ",
            "paper",
            ["burnable"],
        ),
        ("※1 以上は販売店へ相談", "bulky", ["not_collected"]),
        (
            "切るかたたんで30cm以下のものは燃やすごみ、それ以外は大型ごみ。",
            "bulky",
            ["burnable"],
        ),
        ("30cm以下にたためるものは燃やすごみ", "bulky", ["burnable"]),
    ],
)
def test_only_whole_item_conditions_authorize_alternatives(note, primary, expected):
    assert niihama_data.classification_options(note, primary) == expected


@pytest.mark.parametrize(
    "profile,color,expected",
    [
        ("oshima", "non_burnable", {"non_burnable", "textiles"}),
        ("oshima", "paper", {"bottles_cans", "pet_bottles", "paper"}),
        ("besshiyama", "paper", {"bottles_cans", "pet_bottles", "paper"}),
    ],
)
def test_same_symbol_has_reviewed_profile_and_colour_specific_meaning(
    profile, color, expected
):
    assert observed_types("※", profile, color) == expected
    with pytest.raises(ValueError):
        observed_types("※", "mainland", color)


@pytest.mark.parametrize("symbol", ["", "休", "●", "/"])
def test_facility_symbols_never_create_curbside_collections(symbol):
    assert observed_types(symbol, "mainland", None) == set()
    assert color_code((1, 1, 1)) is None


def question(query, clarifications=(), *, enabled=True, conditional=True):
    region = SimpleNamespace(
        rules=SimpleNamespace(
            size_threshold_cm=30 if enabled else None,
            size_question="取っ手を含め30cm以下ですか？",
        ),
        municipality_id="90001",
    )
    doc = "品目: バケツ\n分類コード: burnable\n分類: 燃やすごみ\n"
    if conditional:
        doc += '条件付き分類コード: ["bulky"]\n出し方・注意: 30cm超えは大型ごみ\n'
    doc += "区分共通の出し方: 原則30cm以下。"
    return WasteGuideService._conditional_evidence_question(
        query=query,
        clarifications=list(clarifications),
        documents=[RetrievedDocument(doc)],
        region=region,
    )


def test_size_boundary_requires_measured_user_information_only_when_opted_in():
    assert question("壊れたプラスチック製バケツ") == "取っ手を含め30cm以下ですか？"
    assert question("20cmのプラスチック製バケツ") is None
    assert question("40センチのプラスチック製バケツ") is None
    assert question("プラスチック製バケツ", enabled=False) is None
    assert question("プラスチック製バケツ", conditional=False) is None


@pytest.mark.parametrize("answer", ["はい", "いいえ"])
def test_short_size_answers_are_tied_to_the_dimensional_question(answer):
    assert (
        question(
            "プラスチック製バケツ", [{"question": "30cm以下ですか？", "answer": answer}]
        )
        is None
    )
    assert question(
        "プラスチック製バケツ",
        [{"question": "プラスチック製ですか？", "answer": answer}],
    )


def test_changed_download_never_overwrites_existing_source(tmp_path, monkeypatch):
    monkeypatch.setattr(niihama_data, "DATA", tmp_path)
    target = tmp_path / "source/one.pdf"
    target.parent.mkdir()
    target.write_bytes(b"original")
    (tmp_path / "sources.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "file": "one.pdf",
                        "url": "https://www.city.niihama.lg.jp/uploaded/attachment/one.pdf",
                        "sha256": niihama_data.digest(target),
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(niihama_data, "urlopen", lambda *a, **k: BytesIO(b"changed"))
    with pytest.raises(ValueError, match="review required"):
        niihama_data.fetch()
    assert target.read_bytes() == b"original"


def test_unverified_index_never_registers_city(tmp_path, monkeypatch):
    monkeypatch.setattr(niihama_data, "ROOT", tmp_path)
    p = tmp_path / "data/regions/catalog.json"
    p.parent.mkdir(parents=True)
    p.write_text('{"municipalities":[]}')
    monkeypatch.setattr(
        niihama_data,
        "verify",
        lambda: (_ for _ in ()).throw(ValueError("missing index")),
    )
    with pytest.raises(ValueError, match="missing index"):
        niihama_data.activate()
    assert p.read_text() == '{"municipalities":[]}'


def test_unrelated_size_candidate_does_not_block_selected_carry_in_evidence():
    region = SimpleNamespace(
        rules=SimpleNamespace(size_threshold_cm=30, size_question="30cm以下ですか？"),
        municipality_id="90001",
    )
    docs = [
        RetrievedDocument(
            '品目: 携帯式マッサージ器\n分類コード: non_burnable\n条件付き分類コード: ["bulky"]\n出し方・注意: 30cm超えは大型ごみ'
        ),
        RetrievedDocument(
            "品目: マッサージチェア\n分類コード: self_delivery\n出し方・注意: 清掃センターへ自己搬入"
        ),
    ]
    assert (
        WasteGuideService._conditional_evidence_question(
            query="家庭用マッサージチェア",
            clarifications=[],
            documents=docs,
            region=region,
            selected_evidence_indexes=(2,),
        )
        is None
    )


def test_unknown_dimension_is_not_a_measurement_and_numeric_reply_has_question_units():
    assert question("30cm以下か分からないプラスチック製バケツ")
    assert (
        question(
            "プラスチック製バケツ",
            [{"question": "最長部分は何cmですか？", "answer": "20"}],
        )
        is None
    )
    assert question(
        "プラスチック製バケツ", [{"question": "いくつありますか？", "answer": "20"}]
    )
