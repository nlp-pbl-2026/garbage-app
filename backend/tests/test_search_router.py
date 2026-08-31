from datetime import date
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.calendar_service import CollectionDate
from app.services.waste_guide_service import (
    ClassificationDecision,
    RetrievedDocument,
    WasteGuideResult,
)


@pytest.mark.asyncio
async def test_classify_endpoint_returns_answer():
    result = WasteGuideResult(
        status="answered",
        rewritten_query="ペットボトル",
        answer="ペットボトルは「ペットボトル」です。",
        decision=ClassificationDecision(
            is_resolved=True,
            item_name="ペットボトル",
            category_code="ペット",
            disposal_instructions="すすいで出してください。",
            confidence=0.97,
        ),
        next_collection=CollectionDate(
            date=date(2026, 9, 2), collection_type="ペットボトル"
        ),
        sources=[
            RetrievedDocument(
                text="ペットボトルの出し方",
                score=0.91,
                uri="s3://new-bucket/items.csv",
            )
        ],
    )

    with (
        patch("app.routers.search_router.WasteGuideService") as service_class,
        patch("app.routers.search_router.SearchLogService") as log_class,
    ):
        service_class.return_value.query.return_value = result
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/search/classify",
                json={"query": "これは何ごみ？"},
            )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "answered"
    assert body["classification"]["category_code"] == "ペット"
    assert body["next_collection"]["date"] == "2026-09-02"
    assert body["sources"][0]["score"] == 0.91
    assert body["request_id"]
    event = log_class.return_value.record.call_args.args[0]
    assert event["query"] == "これは何ごみ？"
    assert event["confidence"] == 0.97
    assert event["status"] == "answered"


@pytest.mark.asyncio
async def test_classify_endpoint_returns_follow_up_question():
    result = WasteGuideResult(
        status="needs_clarification",
        rewritten_query="容器",
        follow_up_question="素材は紙ですか、プラスチックですか？",
    )

    with (
        patch("app.routers.search_router.WasteGuideService") as service_class,
        patch("app.routers.search_router.SearchLogService"),
    ):
        service_class.return_value.query.return_value = result
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/search/classify", json={"query": "この容器は？"}
            )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_clarification"
    assert body["answer"] is None
    assert body["follow_up_question"] == "素材は紙ですか、プラスチックですか？"


@pytest.mark.asyncio
async def test_staged_endpoints_pass_actual_results_between_agents():
    documents = [RetrievedDocument(text="傘は粗大ごみ", score=0.88)]
    result = WasteGuideResult(
        status="needs_clarification",
        rewritten_query="壊れた傘 素材 大きさ",
        follow_up_question="傘の長さは何cmですか？",
        sources=documents,
    )
    with (
        patch("app.routers.search_router.WasteGuideService") as service_class,
        patch("app.routers.search_router.SearchLogService"),
    ):
        service = service_class.return_value
        service.rewrite.return_value = "壊れた傘 素材 大きさ"
        service.retrieve.return_value = documents
        service.decide.return_value = result
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            rewrite = await client.post(
                "/api/search/rewrite", json={"query": "雨の日の長いやつ"}
            )
            retrieve = await client.post(
                "/api/search/retrieve",
                json={"rewritten_query": rewrite.json()["rewritten_query"]},
            )
            decide = await client.post(
                "/api/search/decide",
                json={
                    "query": "雨の日の長いやつ",
                    "rewritten_query": rewrite.json()["rewritten_query"],
                    "documents": retrieve.json()["documents"],
                },
            )

    assert rewrite.status_code == 200
    assert retrieve.json()["documents"][0]["score"] == 0.88
    assert decide.json()["follow_up_question"] == "傘の長さは何cmですか？"
    passed_documents = service.decide.call_args.kwargs["documents"]
    assert passed_documents[0].text == "傘は粗大ごみ"


@pytest.mark.asyncio
async def test_analytics_endpoint_requires_key(monkeypatch):
    monkeypatch.setattr("app.routers.search_router.config.ANALYTICS_API_KEY", "secret")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/search/analytics")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_analytics_endpoint_returns_summary(monkeypatch):
    monkeypatch.setattr("app.routers.search_router.config.ANALYTICS_API_KEY", "secret")
    summary = {
        "total_searches": 1,
        "answered_count": 1,
        "clarification_count": 0,
        "average_confidence": 0.93,
        "average_duration_ms": 1200.0,
        "categories": {"可燃ごみ": 1},
        "recent": [],
    }
    with patch("app.routers.search_router.SearchLogService") as log_class:
        log_class.return_value.summary.return_value = summary
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/search/analytics", headers={"X-Analytics-Key": "secret"}
            )

    assert response.status_code == 200
    assert response.json()["average_confidence"] == 0.93


@pytest.mark.asyncio
async def test_request_rejects_blank_query():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/search/classify", json={"query": "   "})

    assert response.status_code == 422
