"""回答または追加質問を返す、ごみ分別検索API。"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from .. import config
from ..schemas import (
    GuideSource,
    NextCollection,
    WasteClassification,
    WasteGuideRequest,
    WasteGuideResponse,
)
from ..services.waste_guide_service import (
    CATEGORY_NAMES,
    UnsupportedRegionError,
    WasteGuideError,
    WasteGuideService,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/classify", response_model=WasteGuideResponse)
async def classify_waste(request: WasteGuideRequest) -> WasteGuideResponse:
    """一件の質問を分類し、回答または一つの追加質問を返す。"""

    service = WasteGuideService()
    clarification_items = [item.model_dump() for item in request.clarifications]
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                service.query,
                query=request.query,
                municipality_id=request.municipality_id,
                district_id=request.district_id,
                clarifications=clarification_items,
            ),
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
    if result.decision:
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

    return WasteGuideResponse(
        status=result.status,
        answer=result.answer,
        follow_up_question=result.follow_up_question,
        rewritten_query=result.rewritten_query,
        classification=classification,
        next_collection=next_collection,
        sources=sources,
    )

