"""アプリケーション設定"""

import os

# JWT設定
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7日間

# データベース設定
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./garbage_app.db")

# ごみ検索/RAG設定
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
BEDROCK_KNOWLEDGE_BASE_ID = os.getenv(
    "BEDROCK_KNOWLEDGE_BASE_ID", os.getenv("KNOWLEDGE_BASE_ID", "")
)
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "8"))
CLASSIFICATION_CONFIDENCE_THRESHOLD = float(
    os.getenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.75")
)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tokyo")
RAG_REQUEST_TIMEOUT_SECONDS = int(os.getenv("RAG_REQUEST_TIMEOUT_SECONDS", "60"))
