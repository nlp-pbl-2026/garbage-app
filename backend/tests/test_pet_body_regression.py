"""Synthetic regressions for retrieval intent and selected-evidence conditions."""

from datetime import time
from pathlib import Path

import pytest
from app.services.region_registry_service import (
    RegionContext,
    RuleProfile,
    CategoryDefinition,
)
from app.services.waste_guide_service import (
    BedrockGateway,
    RetrievedDocument,
    WasteGuideService,
)


@pytest.mark.parametrize(
    "mark,state",
    [
        ("PETマーク付き", "PETマークあり"),
        ("PET表示がある", "PETマークあり"),
        ("ＰＥＴマークのない", "PETマークなし"),
        ("PETマークはありません", "PETマークなし"),
        ("プラマークはありません", "プラマークなし"),
        ("プラ表示なし", "プラマークなし"),
        ("プラマークが付いていません", "プラマークなし"),
        ("プラマークは分かりません", "プラマーク"),
        ("PETマークがあるか分からない", "PETマーク"),
        ("PETマーク", "PETマーク"),
    ],
)
@pytest.mark.parametrize(
    "model_query", ["ボトル", "ボトル PETマークあり プラマークあり"]
)
def test_rewrite_keeps_user_mark_polarity_and_never_confirms_unknown(
    mark, state, model_query
):
    actual = BedrockGateway._preserve_explicit_features(
        model_query, query=f"{mark}ボトル", clarifications=[]
    )
    assert state in actual
    term = state.replace("あり", "").replace("なし", "")
    if not state.endswith("あり"):
        assert term + "あり" not in actual


@pytest.mark.parametrize(
    "query,clarifications",
    [
        ("キャップとラベルを外して水洗いしたPETマーク付き飲料用ペットボトル本体", []),
        ("ＰＥＴマークのある飲料用ペットボトル本体、キャップは取り外し済み", []),
        (
            "飲み終わったボトル",
            [
                {
                    "question": "何を捨てますか？",
                    "answer": "PETマーク付きの飲料用ペットボトル本体です",
                }
            ],
        ),
    ],
)
def test_removed_cap_is_not_reintroduced_when_pet_body_is_the_explicit_target(
    query, clarifications
):
    actual = BedrockGateway._preserve_explicit_features(
        "飲料用ペットボトル", query=query, clarifications=clarifications
    )
    assert "本体" in actual
    assert "キャップ" not in actual and "ふた" not in actual


@pytest.mark.parametrize(
    "query",
    [
        "ペットボトルから外したプラマーク付きキャップだけ",
        "ペットボトル本体から外したキャップ",
        "ペットボトルの本体ではなくキャップだけ",
        "ペットボトル本体を捨てず、キャップだけ",
    ],
)
def test_body_is_not_added_when_detached_cap_is_the_target(query):
    actual = BedrockGateway._preserve_explicit_features(
        "プラスチック製のキャップ", query=query, clarifications=[]
    )
    assert "キャップ" in actual and "本体" not in actual


def region(city="90001"):
    profile = RuleProfile(
        {
            "pet_bottles": CategoryDefinition("PET", "pet", time(8)),
            "plastic_packaging": CategoryDefinition("プラ", "plastic", time(8)),
        },
        Path("/unused/items.csv"),
        Path("/unused/index.npz"),
        Path("/unused/calendar.json"),
    )
    return RegionContext(
        city,
        "a",
        "試験地区",
        "cal",
        "test",
        "test-v1",
        "2026-04-01",
        "2027-03-31",
        profile=profile,
    )


CAP = RetrievedDocument(
    "品目: キャップ\n分類コード: plastic_packaging\n出し方・注意: プラマークがあるか確認\n区分共通の出し方: プラマークのある容器包装が対象",
    0.9,
)
PET = RetrievedDocument(
    "品目: ペットボトル本体\n分類コード: pet_bottles\n出し方・注意: すすいで出す", 0.85
)


def test_pet_decision_does_not_inherit_mark_question_from_higher_cap_candidate():
    q = WasteGuideService._conditional_evidence_question(
        query="PETマーク付き飲料用ペットボトル本体",
        clarifications=[],
        documents=[CAP, PET],
        region=region(),
        selected_evidence_indexes=(2,),
    )
    assert q is None


def test_real_plastic_mark_condition_still_asks_on_the_selected_cap_evidence():
    q = WasteGuideService._conditional_evidence_question(
        query="ペットボトルから外したキャップ",
        clarifications=[],
        documents=[PET, CAP],
        region=region(),
        selected_evidence_indexes=(2,),
    )
    assert q == "プラマークは付いていますか？"


def test_legacy_matsuyama_guard_is_unchanged():
    q = WasteGuideService._conditional_evidence_question(
        query="PETマーク付き飲料用ペットボトル本体",
        clarifications=[],
        documents=[CAP, PET],
        region=region("38201"),
        selected_evidence_indexes=(2,),
    )
    assert q == "プラマークは付いていますか？"


@pytest.mark.parametrize(
    "answer,expected", [("はい", "PETマークあり"), ("いいえ", "PETマークなし")]
)
def test_short_answer_confirms_only_the_mark_actually_asked(answer, expected):
    actual = BedrockGateway._preserve_explicit_features(
        "ペットボトル",
        query="PETマークがあるか分からないペットボトル本体",
        clarifications=[{"question": "PETマークはありますか？", "answer": answer}],
    )
    assert expected in actual
    assert "プラマークあり" not in actual


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["body", "cap"])
async def test_decide_api_keeps_selected_part_category_and_its_collection_date(
    target, monkeypatch, tmp_path
):
    """Exercise JSON model output -> conditions -> API -> calendar, all synthetic."""
    from dataclasses import replace
    from datetime import date
    import json
    from unittest.mock import patch
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.services.calendar_service import CalendarService
    from app.services.item_search_service import ItemMatch
    import csv

    ctx = region()
    matches = [
        ItemMatch(
            "cap",
            "キャップ",
            "plastic_packaging",
            "プラ",
            "プラマークがあるか確認",
            0.9,
            disposal_instructions="プラマークのある容器包装が対象",
        ),
        ItemMatch(
            "body", "ペットボトル本体", "pet_bottles", "PET", "すすいで出す", 0.85
        ),
    ]
    items_path = tmp_path / "items.csv"
    with items_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "item_id",
                "item",
                "category",
                "category_display",
                "note",
                "disposal_instructions",
            ],
        )
        writer.writeheader()
        for match in matches:
            writer.writerow({key: getattr(match, key) for key in writer.fieldnames})
    ctx = replace(ctx, profile=replace(ctx.rules, items_path=items_path))
    calendar = CalendarService(
        region=ctx,
        bundle={
            "municipality_id": "90001",
            "version": "test-v1",
            "valid_from": "2026-04-01",
            "valid_to": "2027-03-31",
            "calendars": {
                "cal": {
                    "verification_status": "checked",
                    "days": {"2026-11-06": ["pet"], "2026-11-08": ["plastic"]},
                }
            },
        },
    )
    category = "pet_bottles" if target == "body" else "plastic_packaging"
    docs = [
        RetrievedDocument(
            m.evidence_text, m.score, ctx.evidence_prefix + "items/" + m.item_id
        )
        for m in (matches if target == "body" else matches[::-1])
    ]

    class Runtime:
        def converse(self, **kwargs):
            return {
                "output": {
                    "message": {
                        "content": [
                            {
                                "text": json.dumps(
                                    {
                                        "is_resolved": True,
                                        "item_name": target,
                                        "category_code": category,
                                        "confidence": 0.99,
                                        "disposal_instructions": "合成の出し方",
                                        "evidence_indexes": [2],
                                    }
                                )
                            }
                        ]
                    }
                }
            }

    gateway = BedrockGateway(runtime_client=Runtime(), agent_runtime_client=object())
    service = WasteGuideService(
        gateway=gateway, calendar=calendar, today_provider=lambda: date(2026, 11, 5)
    )
    monkeypatch.setattr(service, "_validate_region", lambda *a: ctx)
    query = (
        "キャップとラベルを外したPETマーク付き飲料用ペットボトル本体"
        if target == "body"
        else "ペットボトルから外したプラマーク付きキャップだけ"
    )
    with patch(
        "app.routers.search_router.WasteGuideService", return_value=service
    ), patch("app.routers.search_router.SearchLogService"):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://synthetic"
        ) as client:
            res = await client.post(
                "/api/search/decide",
                json={
                    "municipality_id": "90001",
                    "district_id": "a",
                    "query": query,
                    "rewritten_query": query,
                    "documents": [
                        {"snippet": d.text, "score": d.score, "uri": d.uri}
                        for d in docs
                    ],
                },
            )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "answered"
    assert body["follow_up_question"] is None
    assert body["classification"]["category_code"] == category
    assert body["next_collection"]["date"] == (
        "2026-11-06" if target == "body" else "2026-11-08"
    )
