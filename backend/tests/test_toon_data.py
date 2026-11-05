"""Synthetic Toon/time-window regressions: no official PDFs or paid API calls."""

import json
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import toon_data
from toon_pdf import traces
from app.services.region_registry_service import RegionRegistry
from app.services.calendar_service import CalendarService


@pytest.fixture
def time_registry(tmp_path):
    data = {
        "municipality_id": "90001",
        "municipality_name": "合成市",
        "version": "test-v1",
        "valid_from": "2026-04-01",
        "valid_to": "2027-03-31",
        "collection_areas": [
            {
                "id": "test",
                "name": "試験地区",
                "calendar_id": "cal",
                "rule_profile_id": "profile",
            }
        ],
        "calendars": [{"id": "cal", "rule_profile_id": "profile"}],
        "rule_profiles": {
            "profile": {
                "items_path": "items.csv",
                "embedding_index_path": "index.npz",
                "calendar_path": "calendar.json",
                "classification_rules": "合成ルール",
                "categories": {
                    "known": {
                        "name": "確認済",
                        "collection_type_id": "known",
                        "start_time": "06:00",
                        "cutoff": "08:00",
                        "time_note": "午前6〜8時に出してください。",
                    },
                    "local": {
                        "name": "地域時刻",
                        "collection_type_id": "local",
                        "cutoff_status": "unverified",
                        "time_note": "搬出時刻は地域で確認してください。",
                    },
                },
            }
        },
    }
    p = tmp_path / "registry.json"
    p.write_text(json.dumps(data))
    return p, data


def test_dates_remain_available_without_inventing_a_local_deadline(time_registry):
    p, _ = time_registry
    r = RegionRegistry(p).resolve("90001", "test")
    bundle = {
        "municipality_id": "90001",
        "version": "test-v1",
        "valid_from": "2026-04-01",
        "valid_to": "2027-03-31",
        "calendars": {
            "cal": {
                "verification_status": "checked",
                "days": {
                    "2026-11-05": ["known", "local"],
                    "2026-11-12": ["known", "local"],
                },
            }
        },
    }
    cal = CalendarService(region=r, bundle=bundle)
    at = datetime(2026, 11, 5, 7, tzinfo=ZoneInfo("Asia/Tokyo"))
    assert cal.next_collection("known", at=at).date == date(2026, 11, 5)
    assert cal.next_collection("local", at=at).date == date(2026, 11, 12)
    # Legacy global overrides must not fabricate a locally unverified deadline.
    assert cal.next_collection("local", at=at, cutoff_hour=8).date == date(2026, 11, 12)
    assert cal.next_collection("local", from_date=date(2026, 11, 5)).date == date(
        2026, 11, 5
    )
    assert r.rules.categories["local"].cutoff is None
    assert r.rules.categories["known"].start_time.hour == 6
    from app.services.waste_guide_service import (
        WasteGuideService,
        ClassificationDecision,
    )

    d = ClassificationDecision(True, "試験品", "local", "出し方", 0.99)
    answer = WasteGuideService._build_answer(
        d, cal.next_collection("local", at=at), region=r
    )
    assert "搬出時刻は地域で確認" in answer and "0時" not in answer


@pytest.mark.parametrize(
    "change",
    [
        {"cutoff": "08:00"},
        {"time_note": ""},
        {"cutoff_status": "checked"},
        {"cutoff_status": "guessed"},
    ],
)
def test_missing_or_invented_time_metadata_fails_closed(time_registry, change):
    p, data = time_registry
    data["rule_profiles"]["profile"]["categories"]["local"].update(change)
    p.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        RegionRegistry(p)


@pytest.mark.parametrize(
    "note,primary,expected",
    [
        ("45リットルの無色透明袋に入らないものは「粗大」", "non_burnable", ["bulky"]),
        ("コンテナに入らない大型のものは「粗大」", "metals", ["bulky"]),
        ("汚れたものは「燃やす」", "paper", ["burnable"]),
        ("電子式は電池を外して「その他」", "thermometers", ["non_burnable"]),
        ("充電式は「不可」", "batteries", ["not_collected"]),
        ("刃は取り除いて「金属」", "paper", []),
        ("電池は外す", "non_burnable", []),
        ("大人2人で運べる大きさのものに限る", "bulky", ["not_collected"]),
    ],
)
def test_only_whole_item_branches_authorize_other_categories(note, primary, expected):
    assert toon_data.classification_options(note, primary) == expected


def test_glyph_trace_bypasses_stale_actualtext_and_splits_large_position_gaps():
    class Page:
        def get_texttrace(self):
            return [
                {
                    "type": 0,
                    "opacity": 1,
                    "size": 10,
                    "chars": [
                        (ord("1"), 0, (0, 0), (0, 0, 5, 10)),
                        (ord("2"), 0, (50, 0), (50, 0, 55, 10)),
                    ],
                }
            ]

    assert [s["text"] for s in traces(Page())] == ["1", "2"]


def test_changed_official_download_does_not_overwrite_old_source(tmp_path, monkeypatch):
    monkeypatch.setattr(toon_data, "DATA", tmp_path)
    p = tmp_path / "source/one.pdf"
    p.parent.mkdir()
    p.write_bytes(b"reviewed")
    (tmp_path / "sources.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "file": "one.pdf",
                        "url": "https://www.city.toon.ehime.jp/uploaded/attachment/one.pdf",
                        "sha256": toon_data.digest(p),
                    }
                ]
            }
        )
    )
    monkeypatch.setattr(toon_data, "urlopen", lambda *a, **k: BytesIO(b"changed"))
    with pytest.raises(ValueError, match="review required"):
        toon_data.fetch()
    assert p.read_bytes() == b"reviewed"


def test_missing_index_never_activates_municipality(tmp_path, monkeypatch):
    monkeypatch.setattr(toon_data, "ROOT", tmp_path)
    p = tmp_path / "data/regions/catalog.json"
    p.parent.mkdir(parents=True)
    p.write_text('{"municipalities":[]}')

    def missing():
        raise ValueError("Missing index")

    monkeypatch.setattr(toon_data, "verify", missing)
    with pytest.raises(ValueError, match="Missing index"):
        toon_data.activate()
    assert p.read_text() == '{"municipalities":[]}'


@pytest.mark.parametrize(
    "query,clarifications,ask",
    [
        ("大きな木製家具", [], True),
        ("大人2人で運べるか分かりません", [], True),
        ("1m程度の家具。標準的な大人2人で運べます", [], False),
        ("大人2人で運べません", [], False),
        (
            "木製家具",
            [{"question": "標準的な大人2人で運べますか？", "answer": "はい"}],
            False,
        ),
        (
            "木製家具",
            [{"question": "標準的な大人2人で運べますか？", "answer": "いいえ"}],
            False,
        ),
        ("木製家具", [{"question": "木製ですか？", "answer": "はい"}], True),
    ],
)
def test_explicit_two_adult_condition_requires_user_confirmation(
    query, clarifications, ask
):
    from app.services.waste_guide_service import WasteGuideService, RetrievedDocument

    doc = RetrievedDocument(
        '品目: 家具\n分類コード: bulky\n条件付き分類コード: ["not_collected"]\n出し方・注意: 標準的な大人2人で運べるもの。運べないものは不可。',
        1.0,
        "regional://synthetic",
    )
    question = WasteGuideService._carry_condition_question(
        query=query, clarifications=clarifications, documents=[doc]
    )
    assert bool(question) == ask
    if ask:
        assert "2人" in question


@pytest.mark.parametrize(
    "note,primary,expected",
    [
        ("指定ごみ袋に入るものは「燃やす」", "bulky", ["burnable"]),
        ("500ml未満、内側が銀色のものは「燃やす」", "paper", ["burnable"]),
        ("ガラス製は「びん」", "plastic_packaging", ["bottles_glass"]),
        (
            "プラマークがないものは「その他」、家庭で使用するものに限る",
            "plastic_packaging",
            ["non_burnable"],
        ),
        ("金属製以外は「その他」", "metals", ["non_burnable"]),
        ("ビニール・金銀加工しているものは「燃やす」", "paper", ["burnable"]),
        (
            "45リットルの無色透明袋に入らないものは縛って「粗大」",
            "non_burnable",
            ["bulky"],
        ),
        ("金属部分は「金属」", "paper", []),
        ("紙の台紙は「紙」", "plastic_packaging", []),
        ("プラ製の刃は「プラ」", "paper", []),
        ("フィルターは「その他」", "bulky", []),
    ],
)
def test_explicit_conditions_are_kept_but_removed_parts_are_not_promoted(
    note, primary, expected
):
    assert toon_data.classification_options(note, primary) == expected
