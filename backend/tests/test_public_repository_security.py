"""HTTP trust-boundary regressions; no Bedrock calls or original-data writes."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from app import config
from app.lambda_main import app as lambda_app
from app.main import app
from app.middleware.request_size import SearchBodyLimitMiddleware
from app.schemas import SearchDecisionRequest
from app.services.item_search_service import ItemSearchService
from app.services.nakajima_rule_service import evidence_text, resolve_shared_item
from app.services.nakajima_search_service import NakajimaSearchService
from app.services.region_registry_service import get_registry
from app.services.waste_guide_service import (
    RetrievedDocument,
    UnsupportedRegionError,
    WasteGuideService,
    WasteGuideResult,
)

ROOT = Path(__file__).resolve().parents[2]
CITIES = [
    c["id"]
    for c in json.loads((ROOT / "data/regions/catalog.json").read_text())[
        "municipalities"
    ]
]


@pytest.mark.parametrize("city", CITIES)
def test_existing_twenty_city_profiles_fit_and_verify_without_models(city, monkeypatch):
    registry = get_registry().registry(city)
    service = WasteGuideService()
    monkeypatch.setattr(
        "boto3.client", lambda *_a, **_k: pytest.fail("No model/client needed")
    )
    for profile in registry.profiles:
        area = next(
            a for a in registry.areas.values() if a["rule_profile_id"] == profile
        )
        region = get_registry().resolve(city, area["id"])
        items = ItemSearchService(
            items_path=region.asset_path("items_path"), municipality_id=city
        ).list_items(limit=None)
        if region.is_nakajima:
            rows = NakajimaSearchService().rows
            documents = [service._nakajima_document(row) for row in rows[:8]]
            item = next(i for i in items if resolve_shared_item(i).category is not None)
            documents.append(
                RetrievedDocument(
                    text=evidence_text(item, resolve_shared_item(item)),
                    uri="nakajima://shared/" + item.item_id,
                    title="中島地域 2026年度共通分別ルール",
                    score=0.8,
                )
            )
        else:
            prefix = (
                "local://items/"
                if city == "38201"
                else region.evidence_prefix + "items/"
            )
            # Exercise every official row's schema bound, including the longest.
            for item in items:
                assert len(item.evidence_text) <= 4000
            largest = sorted(items, key=lambda i: len(i.evidence_text), reverse=True)[
                :20
            ]
            base = (
                region.rules.knowledge_title
                or f"{region.municipality_label}ごみ分別辞典"
            )
            documents = [
                RetrievedDocument(
                    text=i.evidence_text,
                    uri=prefix + i.item_id,
                    title=base + "（意味検索）",
                    score=0.8,
                )
                for i in largest
            ]
        request = SearchDecisionRequest(
            query="検証用の品物",
            rewritten_query="検証用の品物",
            municipality_id=city,
            district_id=area["id"],
            documents=[
                {"snippet": d.text, "title": d.title, "uri": d.uri, "score": d.score}
                for d in documents
            ],
        )
        assert (
            service.verify_documents(
                documents, municipality_id=city, district_id=area["id"]
            )
            == documents
        )
        assert len(request.documents) == len(documents)


def original_document():
    region = get_registry().resolve("38201", "38201-08")
    item = ItemSearchService(items_path=region.asset_path("items_path")).list_items(
        limit=1
    )[0]
    return RetrievedDocument(
        text=item.evidence_text, uri="local://items/" + item.item_id, score=0.8
    )


@pytest.mark.parametrize("change", ["body", "uri", "duplicate", "cross-city", "kb"])
def test_forged_or_unknown_evidence_never_reaches_classifier(change):
    document = original_document()
    changed = {
        "body": replace(document, text="分類コード: プラ\n出し方: forged-instruction"),
        "uri": replace(document, uri="local://items/not-a-real-id"),
        "cross-city": replace(document, uri="regional://38210/somewhere/items/1"),
        "kb": replace(document, uri="s3://unverified-source/record"),
    }.get(change, document)
    docs = [changed, changed] if change == "duplicate" else [changed]
    body = {
        "query": "これは何？",
        "rewritten_query": "品物",
        "documents": [
            {"snippet": d.text, "uri": d.uri, "score": d.score} for d in docs
        ],
    }
    with patch(
        "app.services.waste_guide_service.BedrockGateway",
        side_effect=AssertionError("No Bedrock"),
    ):
        with TestClient(lambda_app) as client:
            response = client.post("/api/search/decide", json=body)
    assert response.status_code == 422
    assert "forged-instruction" not in response.text


def test_old_flutter_pipeline_payload_needs_no_new_fields():
    doc = original_document()
    with patch("app.routers.search_router.WasteGuideService.decide") as decide, patch(
        "app.routers.search_router.SearchLogService"
    ):
        decide.return_value = WasteGuideResult(
            status="needs_clarification",
            rewritten_query="品物",
            follow_up_question="素材は何ですか？",
        )
        with TestClient(lambda_app) as client:
            response = client.post(
                "/api/search/decide",
                json={
                    "query": "これは何？",
                    "rewritten_query": "品物",
                    "documents": [
                        {"snippet": doc.text, "uri": doc.uri, "score": doc.score}
                    ],
                },
            )
        assert response.status_code == 200
        assert response.json()["follow_up_question"] == "素材は何ですか？"
        assert decide.call_args.kwargs["documents"][0].text == doc.text


def test_existing_three_mebibyte_image_still_fits_request_limit():
    import base64

    doc = original_document()
    with patch("app.routers.search_router.WasteGuideService.decide") as decide, patch(
        "app.routers.search_router.SearchLogService"
    ):
        decide.return_value = WasteGuideResult(
            status="needs_clarification",
            rewritten_query="品物",
            follow_up_question="素材は何ですか？",
        )
        with TestClient(lambda_app) as client:
            response = client.post(
                "/api/search/decide",
                json={
                    "query": "これは何？",
                    "rewritten_query": "品物",
                    "image": {
                        "media_type": "image/png",
                        "data_base64": base64.b64encode(b"x" * (3 * 1024**2)).decode(),
                    },
                    "documents": [
                        {"snippet": doc.text, "uri": doc.uri, "score": doc.score}
                    ],
                },
            )
        assert response.status_code == 200
        assert len(decide.call_args.kwargs["image"].data) == 3 * 1024**2


def test_nakajima_official_examples_do_not_require_shared_csv(monkeypatch):
    registry = get_registry().registry("38201")
    area = next(
        a for a in registry.areas.values() if a["rule_profile_id"] == "nakajima"
    )
    service = WasteGuideService()
    document = service._nakajima_document(NakajimaSearchService().rows[0])
    monkeypatch.setattr(
        "app.services.waste_guide_service.ItemSearchService",
        lambda *_a, **_k: pytest.fail("Shared CSV unnecessary"),
    )
    assert service.verify_documents(
        [document], municipality_id="38201", district_id=area["id"]
    )


@pytest.mark.parametrize(
    "documents",
    [
        [{"snippet": "x" * 4001}],
        [{"uri": "x" * 1001}],
        [{"score": float("inf")}],
        [{"score": float("nan")}],
        [{"score": 1.01}],
        [{}] * 21,
        [{"snippet": "あ" * 4000}] * 6,
    ],
)
def test_document_field_and_total_bounds(documents):
    with pytest.raises(ValidationError):
        SearchDecisionRequest(query="品物", rewritten_query="品物", documents=documents)


@pytest.mark.parametrize("target", [app, lambda_app])
def test_oversized_content_length_stops_before_any_model(target, monkeypatch):
    async def no_database_initialization():
        pass

    monkeypatch.setattr("app.main.init_db", no_database_initialization)
    with patch(
        "app.routers.search_router.WasteGuideService",
        side_effect=AssertionError("No search"),
    ):
        with TestClient(target) as client:
            response = client.post(
                "/api/search/decide",
                content=b"{}",
                headers={
                    "Content-Length": str(6 * 1024**2),
                    "Origin": "https://example.test",
                },
            )
    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == "*"


@pytest.mark.asyncio
async def test_streamed_body_limit_checks_bytes_without_trusting_headers():
    called = []

    async def downstream(scope, receive, send):
        called.append(True)

    application = SearchBodyLimitMiddleware(downstream, max_bytes=5)
    messages = iter(
        [
            {"type": "http.request", "body": b"123", "more_body": True},
            {"type": "http.request", "body": b"456", "more_body": False},
        ]
    )
    responses = []

    async def receive():
        return next(messages)

    async def send(message):
        responses.append(message)

    await application(
        {"type": "http", "method": "POST", "path": "/api/search/decide", "headers": []},
        receive,
        send,
    )
    assert not called
    assert responses[0]["status"] == 413


def test_missing_jwt_key_does_not_enable_lambda_auth_or_break_search(monkeypatch):
    monkeypatch.setattr(config, "SECRET_KEY", "")
    with TestClient(lambda_app) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/auth/login", json={}).status_code == 404


def test_nested_indices_and_local_secrets_stay_ignored():
    paths = [
        "data/regions/matsuyama/common/knowledge/item_embeddings.npz",
        "data/regions/imabari/knowledge/sekizen/item_embeddings.npz",
        "infra/terraform/private.tfvars",
        "infra/frontend/backend.hcl",
        "backend/garbage_app.db-wal",
    ]
    result = subprocess.check_output(
        ["git", "check-ignore", "--no-index", *paths], cwd=ROOT, text=True
    ).splitlines()
    assert result == paths
