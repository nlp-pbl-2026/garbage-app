"""FastAPI アプリケーションエントリーポイント"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .middleware.request_size import SearchBodyLimitMiddleware
from .routers.auth_router import router as auth_router
from .routers.bulky_waste_router import router as bulky_waste_router
from .routers.search_router import router as search_router
from .routers.frontend_data_router import router as frontend_data_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動時にDBテーブルを初期化する"""
    await init_db()
    yield


app = FastAPI(
    title="ごみサポ API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS設定
# CORSMiddlewareはスタックの一番外側（最初）に追加することで、
# 500エラー時にも確実にAccess-Control-Allow-Originヘッダーが付く。
app.add_middleware(SearchBodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーター登録
app.include_router(auth_router)
app.include_router(bulky_waste_router)
app.include_router(search_router)
app.include_router(frontend_data_router)


@app.get("/api/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "ok"}
