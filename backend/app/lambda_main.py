"""AWS Lambda向けの検索専用FastAPIエントリーポイント。"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from .routers.search_router import router as search_router

app = FastAPI(title="ごみ分別あいまい検索 API", version="1.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Analytics-Key"],
)
app.include_router(search_router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


handler = Mangum(app, lifespan="off")
