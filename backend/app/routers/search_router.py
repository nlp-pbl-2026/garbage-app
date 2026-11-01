"""回答または追加質問を返す、ごみ分別検索API。"""

import asyncio
import logging
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query

from .. import config
from ..schemas import (
    BulkyWasteItemListResponse,
    BulkyWasteItemResponse,
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
from ..services.item_search_service import ItemSearchService
from ..services.nakajima_search_service import NakajimaSearchService
from ..services.region_registry_service import (
    RegionResolutionError, RegionalDataError, UnsupportedMunicipalityError, get_registry,
)
from ..services.search_log_service import SearchLogService
from ..services.waste_guide_service import (
    CATEGORY_NAMES,
    ImageInput,
    RetrievedDocument,
    UnsupportedRegionError,
    WasteGuideError,
    WasteGuideService,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


def _image_input(request: WasteGuideRequest) -> ImageInput | None:
    if request.image is None:
        return None
    return ImageInput(
        format=request.image.bedrock_format,
        data=request.image.decoded_bytes(),
    )


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
            image=_image_input(request),
        )
    )
    return SearchRewriteResponse(rewritten_query=rewritten)


@router.post("/retrieve", response_model=SearchRetrieveResponse)
async def retrieve_regional_documents(
    request: SearchRetrieveRequest,
) -> SearchRetrieveResponse:
    """選択した自治体・分別設定の根拠を取得する。"""

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
            image=_image_input(request),
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
            image=_image_input(request),
        )
    )
    return await _build_response_and_log(
        request=request,
        result=result,
        clarification_items=clarification_items,
        started_at=started_at,
    )


@router.get(
    "/items/{municipality_id}", response_model=BulkyWasteItemListResponse
)
async def list_waste_items(
    municipality_id: str,
    category: str = Query(default="粗大", max_length=20),
    search: str | None = Query(default=None, max_length=100),
    district_id: str | None = Query(default=None, max_length=20),
) -> BulkyWasteItemListResponse:
    """あいまい検索と同じ品目辞典から、分類別の品目一覧を返す。"""

    try:
        region = get_registry().resolve(
            municipality_id, district_id or ("38201-08" if municipality_id == "38201" else ""))
    except UnsupportedMunicipalityError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RegionResolutionError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except RegionalDataError as error:
        raise HTTPException(status_code=503, detail="自治体のデータを確認できません。") from error
    if municipality_id != "38201" and category not in region.category_codes:
        raise HTTPException(status_code=422, detail="指定された分別区分は未対応です。")
    if region.is_nakajima:
        try:
            rows = [row for row in NakajimaSearchService().rows
                    if row["category"] == category and row["item_id"].startswith("nk-item-")
                    and (not search or search in row["item"])]
        except FileNotFoundError as error:
            raise HTTPException(status_code=503, detail="中島地域の品目資料がありません。") from error
        return BulkyWasteItemListResponse(
            items=[BulkyWasteItemResponse(id=index, item_name=row["item"],
                    category=row["category_display"], fee_amount=0, notes=row["note"])
                   for index, row in enumerate(rows, start=1)],
            total_count=len(rows), municipality_name="松山市・中島地域",
        )

    try:
        item_search = (ItemSearchService() if municipality_id == "38201" else
                       ItemSearchService(items_path=region.asset_path("items_path"), municipality_id=municipality_id))
        matches = item_search.list_items(category=category, query=search, limit=None)
    except (OSError, ValueError, KeyError) as error:
        raise HTTPException(status_code=503, detail="自治体の品目資料を確認できません。") from error
    return BulkyWasteItemListResponse(
        items=[
            BulkyWasteItemResponse(
                id=index,
                item_name=match.item,
                category=(
                    match.category_display
                    or region.category_names.get(match.category, match.category)
                ),
                fee_amount=0,
                notes=match.note or None,
            )
            for index, match in enumerate(matches, start=1)
        ],
        total_count=len(matches),
        municipality_name=region.municipality_label,
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
            category_name=result.category_name or CATEGORY_NAMES[result.decision.category_code],
            disposal_instructions=result.decision.disposal_instructions,
            confidence=result.decision.confidence,
        )
    collection_status = vars(result.collection_status) if result.collection_status else None
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
        collection_status=collection_status,
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
        "has_image": request.image is not None,
        "image_media_type": (
            request.image.media_type if request.image is not None else None
        ),
        "image_size_bytes": (
            len(request.image.decoded_bytes()) if request.image is not None else 0
        ),
        "clarifications": clarification_items,
        "rewritten_query": result.rewritten_query,
        "status": result.status,
        "answer": result.answer,
        "follow_up_question": result.follow_up_question,
        "category_code": result.decision.category_code if result.decision else None,
        "category_name": (
            result.category_name or CATEGORY_NAMES.get(result.decision.category_code)
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
