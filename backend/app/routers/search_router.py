"""回答または追加質問を返す、ごみ分別検索API。"""

import asyncio
import logging
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException

from .. import config
from ..schemas import (
    GuideSource,
    NextCollection,
    SearchDecisionRequest,
    SearchAnalyticsSummary,
    SearchRetrieveRequest,
    SearchRetrieveResponse,
    SearchRewriteResponse,
    WasteClassification,
    WasteGuideRequest,
    WasteGuideResponse,
)
from ..services.search_log_service import SearchLogService
from ..services.waste_guide_service import (
    CATEGORY_NAMES,
    RetrievedDocument,
    UnsupportedRegionError,
    WasteGuideError,
    WasteGuideService,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


async def _run_step(operation):
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(operation),
            timeout=config.RAG_REQUEST_TIMEOUT_SECONDS,
        )
    except UnsupportedRegionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except (TimeoutError, asyncio.TimeoutError) as error:
        raise HTTPException(
            status_code=504,
            detail="検索がタイムアウトしました。しばらくしてからお試しください。",
        ) from error
    except WasteGuideError as error:
        logger.exception("Waste guide service failed")
        raise HTTPException(
            status_code=503,
            detail="ごみ分別サービスに接続できません。しばらくしてからお試しください。",
        ) from error


@router.post("/rewrite", response_model=SearchRewriteResponse)
async def rewrite_search_query(request: WasteGuideRequest) -> SearchRewriteResponse:
    """Nova Liteで曖昧な質問を地域資料向けの検索文へ言い換える。"""

    clarifications = [item.model_dump() for item in request.clarifications]
    rewritten = await _run_step(
        lambda: WasteGuideService().rewrite(
            query=request.query,
            municipality_id=request.municipality_id,
            district_id=request.district_id,
            clarifications=clarifications,
        )
    )
    return SearchRewriteResponse(rewritten_query=rewritten)


@router.post("/retrieve", response_model=SearchRetrieveResponse)
async def retrieve_regional_documents(
    request: SearchRetrieveRequest,
) -> SearchRetrieveResponse:
    """Bedrock Knowledge Baseから松山市・清水地区の根拠を取得する。"""

    documents = await _run_step(
        lambda: WasteGuideService().retrieve(
            rewritten_query=request.rewritten_query,
            municipality_id=request.municipality_id,
            district_id=request.district_id,
        )
    )
    return SearchRetrieveResponse(
        documents=[
            GuideSource(
                title=document.title,
                uri=document.uri,
                snippet=document.text,
                score=document.score,
            )
            for document in documents
        ]
    )


@router.post("/decide", response_model=WasteGuideResponse)
async def decide_waste(request: SearchDecisionRequest) -> WasteGuideResponse:
    """Nova Liteで分類し、カレンダーを照合して検索ログを保存する。"""

    service = WasteGuideService()
    started_at = monotonic()
    clarification_items = [item.model_dump() for item in request.clarifications]
    documents = [
        RetrievedDocument(
            text=document.snippet or "",
            score=document.score,
            uri=document.uri,
            title=document.title,
        )
        for document in request.documents
    ]
    result = await _run_step(
        lambda: service.decide(
            query=request.query,
            rewritten_query=request.rewritten_query,
            documents=documents,
            municipality_id=request.municipality_id,
            district_id=request.district_id,
            clarifications=clarification_items,
        )
    )
    return await _build_response_and_log(
        request=request,
        result=result,
        clarification_items=clarification_items,
        started_at=started_at,
    )


@router.post("/classify", response_model=WasteGuideResponse)
async def classify_waste(request: WasteGuideRequest) -> WasteGuideResponse:
    """一件の質問を分類し、回答または一つの追加質問を返す。"""

    service = WasteGuideService()
    started_at = monotonic()
    clarification_items = [item.model_dump() for item in request.clarifications]
    result = await _run_step(
        lambda: service.query(
                query=request.query,
                municipality_id=request.municipality_id,
                district_id=request.district_id,
                clarifications=clarification_items,
        )
    )
    return await _build_response_and_log(
        request=request,
        result=result,
        clarification_items=clarification_items,
        started_at=started_at,
    )


async def _build_response_and_log(
    *, request, result, clarification_items: list[dict], started_at: float
) -> WasteGuideResponse:
    """公開レスポンスを組み立て、分析用イベントを保存する。"""

    request_id = str(uuid4())
    log_service = SearchLogService()

    sources = [
        GuideSource(
            title=document.title,
            uri=document.uri,
            snippet=document.text[:240] if document.text else None,
            score=document.score,
        )
        for document in result.sources
    ]
    classification = None
    if result.decision and result.decision.is_resolved:
        classification = WasteClassification(
            item_name=result.decision.item_name,
            category_code=result.decision.category_code,
            category_name=CATEGORY_NAMES[result.decision.category_code],
            disposal_instructions=result.decision.disposal_instructions,
            confidence=result.decision.confidence,
        )
    next_collection = None
    if result.next_collection:
        next_collection = NextCollection(
            date=result.next_collection.date.isoformat(),
            display_date=result.next_collection.display_date,
            collection_type=result.next_collection.collection_type,
        )

    response = WasteGuideResponse(
        status=result.status,
        answer=result.answer,
        follow_up_question=result.follow_up_question,
        rewritten_query=result.rewritten_query,
        classification=classification,
        next_collection=next_collection,
        sources=sources,
        request_id=request_id,
    )
    event = {
        "event_type": "search",
        "request_id": request_id,
        "created_at": datetime.now(UTC).isoformat(),
        "municipality_id": request.municipality_id,
        "district_id": request.district_id,
        "query": request.query,
        "clarifications": clarification_items,
        "rewritten_query": result.rewritten_query,
        "status": result.status,
        "answer": result.answer,
        "follow_up_question": result.follow_up_question,
        "category_code": result.decision.category_code if result.decision else None,
        "category_name": (
            CATEGORY_NAMES.get(result.decision.category_code)
            if result.decision
            else None
        ),
        "confidence": result.decision.confidence if result.decision else None,
        "next_collection_date": (
            result.next_collection.date.isoformat() if result.next_collection else None
        ),
        "rag_scores": [document.score for document in result.sources],
        "duration_ms": round((monotonic() - started_at) * 1000, 1),
    }
    await asyncio.to_thread(log_service.record, event)
    return response


@router.get("/analytics", response_model=SearchAnalyticsSummary)
async def search_analytics(
    x_analytics_key: str | None = Header(default=None, alias="X-Analytics-Key"),
) -> SearchAnalyticsSummary:
    """検索ログの集計と直近履歴を管理キー保護下で返す。"""

    if not config.ANALYTICS_API_KEY:
        raise HTTPException(status_code=404, detail="分析APIは無効です。")
    if x_analytics_key != config.ANALYTICS_API_KEY:
        raise HTTPException(status_code=403, detail="分析キーが正しくありません。")
    summary = await asyncio.to_thread(SearchLogService().summary)
    return SearchAnalyticsSummary(**summary)
