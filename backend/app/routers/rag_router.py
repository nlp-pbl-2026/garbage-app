"""RAGクエリルーター

POST /api/rag/query エンドポイントを提供する。
認証不要。boto3は同期SDKのため asyncio.to_thread() で呼び出す。
asyncio.wait_for() でタイムアウトを制御する。
"""

import asyncio

from fastapi import APIRouter, HTTPException

from .. import config
from ..schemas import RAGQueryRequest, RAGQueryResponse, RAGSource
from ..services.bedrock_service import BedrockRAGService, BedrockServiceError

router = APIRouter(prefix="/api/rag", tags=["rag"])


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(request: RAGQueryRequest) -> RAGQueryResponse:
    """RAGクエリエンドポイント（認証不要）

    boto3は同期SDKのため、asyncio.to_thread()でサービス呼び出しを実行し
    FastAPIのイベントループをブロックしない。
    asyncio.wait_for()でタイムアウトを検出する。
    """
    service = BedrockRAGService()

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(
                service.query,
                query=request.query,
                municipality_name=request.municipality_name,
                district_name=request.district_name,
            ),
            timeout=config.RAG_REQUEST_TIMEOUT_SECONDS,
        )
    except BedrockServiceError as e:
        raise HTTPException(
            status_code=503,
            detail=str(e),
        )
    except (TimeoutError, asyncio.TimeoutError):
        raise HTTPException(
            status_code=504,
            detail="リクエストがタイムアウトしました。しばらくしてからお試しください。",
        )
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="AIサービスでエラーが発生しました。しばらくしてからお試しください。",
        )

    # RAGResult → RAGQueryResponse に変換
    sources = [
        RAGSource(
            title=s.get("title"),
            uri=s.get("uri"),
            snippet=s.get("snippet"),
        )
        for s in result.sources
    ]

    return RAGQueryResponse(answer=result.answer, sources=sources)
