import base64
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.calendar_service import CollectionDate
from app.services.item_search_service import ItemMatch
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
    assert event["text_retained"] is True
    assert event["query"] == "これは何ごみ？"
    assert event["rewritten_query"] == result.rewritten_query
    assert event["answer"] == result.answer
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
        patch("app.routers.search_router.SearchLogService") as log_class,
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
    assert (
        log_class.return_value.record.call_args.args[0]["follow_up_question"]
        == body["follow_up_question"]
    )


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
        patch("app.routers.search_router.SearchLogService") as log_class,
    ):
        service = service_class.return_value
        service.rewrite.return_value = "壊れた傘 素材 大きさ"
        service.retrieve.return_value = documents
        service.verify_documents.return_value = documents
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
                    "clarifications": [
                        {"question": "どんな品物ですか？", "answer": "傘です"}
                    ],
                },
            )

    assert rewrite.status_code == 200
    assert retrieve.json()["documents"][0]["score"] == 0.88
    assert decide.json()["follow_up_question"] == "傘の長さは何cmですか？"
    passed_documents = service.decide.call_args.kwargs["documents"]
    assert passed_documents[0].text == "傘は粗大ごみ"
    event = log_class.return_value.record.call_args.args[0]
    assert event["query"] == "雨の日の長いやつ"
    assert event["rewritten_query"] == result.rewritten_query
    assert event["clarifications"] == [
        {"question": "どんな品物ですか？", "answer": "傘です"}
    ]
    assert event["follow_up_question"] == "傘の長さは何cmですか？"


@pytest.mark.asyncio
@pytest.mark.parametrize("entrypoint", ["main", "lambda"])
@pytest.mark.parametrize(
    "configured_key, supplied_key, status",
    [("secret", None, 403), ("secret", "wrong", 403), ("", "secret", 404)],
)
async def test_analytics_endpoint_requires_key(
    monkeypatch, entrypoint, configured_key, supplied_key, status
):
    from app.lambda_main import app as lambda_app

    monkeypatch.setattr(
        "app.routers.search_router.config.ANALYTICS_API_KEY", configured_key
    )
    with patch("app.routers.search_router.SearchLogService") as log_class:
        async with AsyncClient(
            transport=ASGITransport(app=app if entrypoint == "main" else lambda_app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/search/analytics",
                headers={"X-Analytics-Key": supplied_key} if supplied_key else {},
            )
    assert response.status_code == status
    log_class.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("entrypoint", ["main", "lambda"])
async def test_analytics_endpoint_returns_summary(monkeypatch, entrypoint):
    from app.lambda_main import app as lambda_app
    from app.services.search_log_service import SearchLogService

    monkeypatch.setattr("app.routers.search_router.config.ANALYTICS_API_KEY", "secret")
    event = {
        "event_type": "search",
        "query": "洗った缶",
        "rewritten_query": "アルミ缶",
        "clarifications": [{"question": "素材は？", "answer": "アルミです"}],
        "answer": "かん類です。",
        "follow_up_question": None,
        "status": "answered",
        "category_name": "かん類",
        "confidence": 0.93,
        "duration_ms": 1200.0,
    }
    # Use the real storage/read filtering and aggregation behind the access check.
    service = SearchLogService(
        table=SimpleNamespace(scan=lambda **kwargs: {"Items": [event]})
    )
    with patch("app.routers.search_router.SearchLogService") as log_class:
        log_class.return_value = service
        async with AsyncClient(
            transport=ASGITransport(app=app if entrypoint == "main" else lambda_app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/search/analytics", headers={"X-Analytics-Key": "secret"}
            )

    assert response.status_code == 200
    assert response.json()["average_confidence"] == 0.93
    assert response.json()["categories"] == {"かん類": 1}
    assert response.json()["recent"] == [event]


@pytest.mark.asyncio
async def test_request_rejects_blank_query():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/api/search/classify", json={"query": "   "})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rewrite_endpoint_accepts_image_without_text():
    with patch("app.routers.search_router.WasteGuideService") as service_class:
        service_class.return_value.rewrite.return_value = "木製のいす"
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/search/rewrite",
                json={
                    "query": "",
                    "image": {
                        "media_type": "image/jpeg",
                        "data_base64": base64.b64encode(b"test-image").decode(),
                    },
                },
            )

    assert response.status_code == 200
    image = service_class.return_value.rewrite.call_args.kwargs["image"]
    assert image.format == "jpeg"
    assert image.data == b"test-image"


@pytest.mark.asyncio
async def test_items_endpoint_uses_search_catalog_and_filters_bulky_items():
    matches = [
        ItemMatch(
            item_id="item_1",
            item="ソファ",
            category="粗大",
            category_display="粗大ごみ",
            note="大きさを確認",
            score=1.0,
        )
    ]
    with patch("app.routers.search_router.ItemSearchService") as service_class:
        service_class.return_value.list_items.return_value = matches
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/search/items/38201", params={"category": "粗大"}
            )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": 1,
                "item_name": "ソファ",
                "category": "粗大ごみ",
                "fee_amount": 0,
                "size_category": None,
                "size_threshold_cm": None,
                "weight_category": None,
                "weight_threshold_kg": None,
                "notes": "大きさを確認",
            }
        ],
        "total_count": 1,
        "municipality_name": "松山市",
    }
    service_class.return_value.list_items.assert_called_once_with(
        category="粗大", query=None, limit=None
    )
