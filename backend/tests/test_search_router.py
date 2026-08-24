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

    with patch("app.routers.search_router.WasteGuideService") as service_class:
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


@pytest.mark.asyncio
async def test_classify_endpoint_returns_follow_up_question():
    result = WasteGuideResult(
        status="needs_clarification",
        rewritten_query="容器",
        follow_up_question="素材は紙ですか、プラスチックですか？",
    )

    with patch("app.routers.search_router.WasteGuideService") as service_class:
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
async def test_request_rejects_blank_query():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/search/classify", json={"query": "   "})

    assert response.status_code == 422
