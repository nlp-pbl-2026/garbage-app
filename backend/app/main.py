"""FastAPI アプリケーションエントリーポイント"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .middleware.language_middleware import LanguageMiddleware
from .routers.auth_router import router as auth_router
from .routers.bulky_waste_router import router as bulky_waste_router
from .routers.image_router import router as image_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーション起動時にDBテーブルを初期化する"""
    await init_db()
    yield


app = FastAPI(
    title="愛媛ゴミ出しアプリ API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS設定（開発時は全許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 言語解析ミドルウェア（Accept-Language ヘッダーから言語を決定）
app.add_middleware(LanguageMiddleware)

# ルーター登録
app.include_router(auth_router)
app.include_router(bulky_waste_router)
app.include_router(image_router)


@app.get("/api/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "ok"}
