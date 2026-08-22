"""アプリケーション設定"""

import os

# JWT設定
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7日間

# データベース設定
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./garbage_app.db")

# RAG設定
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
KNOWLEDGE_BASE_ID = os.getenv("KNOWLEDGE_BASE_ID", "")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tokyo")
AGENTIC_MAX_ITERATIONS = int(os.getenv("AGENTIC_MAX_ITERATIONS", "5"))
AGENTIC_FOUNDATION_MODEL_TYPE = os.getenv("AGENTIC_FOUNDATION_MODEL_TYPE", "MANAGED")
RAG_REQUEST_TIMEOUT_SECONDS = int(os.getenv("RAG_REQUEST_TIMEOUT_SECONDS", "60"))
