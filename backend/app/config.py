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
LEXICAL_SEARCH_TOP_K = int(os.getenv("LEXICAL_SEARCH_TOP_K", "5"))
LEXICAL_SEARCH_MIN_SCORE = float(os.getenv("LEXICAL_SEARCH_MIN_SCORE", "0.18"))
# AWS本番はTitan Embedding単体を採用。比較実験では環境変数をtrueにして
# 表層一致とのハイブリッドへ切り替えられる。
LEXICAL_SEARCH_ENABLED = os.getenv("LEXICAL_SEARCH_ENABLED", "false").lower() == "true"
KNOWLEDGE_ITEMS_PATH = os.getenv("KNOWLEDGE_ITEMS_PATH", "")
# 自前Embedding検索（マネージドKnowledge Baseのチャンク分割に依存しない）。
BEDROCK_EMBEDDING_MODEL_ID = os.getenv(
    "BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
)
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
EMBEDDING_SEARCH_TOP_K = int(os.getenv("EMBEDDING_SEARCH_TOP_K", "8"))
# 検索器は再現率を優先し、低い候補もLLM判定へ渡す（最終確定はclassifyが担う）。
EMBEDDING_SEARCH_MIN_SCORE = float(os.getenv("EMBEDDING_SEARCH_MIN_SCORE", "0.15"))
EMBEDDING_INDEX_PATH = os.getenv("EMBEDDING_INDEX_PATH", "")
# Knowledge Base連携を使うか。AWS本番はTitanを直接呼び出すためFalse。
# 既存Knowledge Baseとの比較実験では環境変数をtrueにして切り替えられる。
USE_BEDROCK_KNOWLEDGE_BASE = (
    os.getenv("USE_BEDROCK_KNOWLEDGE_BASE", "false").lower() == "true"
)
MAX_CLARIFICATION_TURNS = int(os.getenv("MAX_CLARIFICATION_TURNS", "2"))
CLASSIFICATION_CONFIDENCE_THRESHOLD = float(
    os.getenv("CLASSIFICATION_CONFIDENCE_THRESHOLD", "0.75")
)
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tokyo")
RAG_REQUEST_TIMEOUT_SECONDS = int(os.getenv("RAG_REQUEST_TIMEOUT_SECONDS", "60"))
_collection_cutoff_hour = os.getenv("COLLECTION_CUTOFF_HOUR")
COLLECTION_CUTOFF_HOUR = (
    int(_collection_cutoff_hour) if _collection_cutoff_hour else None
)
CALENDAR_PATH = os.getenv("CALENDAR_PATH", "")

# 検索分析ログ。AWSではDynamoDB、ローカルではJSON Linesを使う。
SEARCH_LOG_TABLE = os.getenv("SEARCH_LOG_TABLE", "")
SEARCH_LOG_FILE = os.getenv("SEARCH_LOG_FILE", "search_logs.jsonl")
SEARCH_LOG_RETENTION_DAYS = int(os.getenv("SEARCH_LOG_RETENTION_DAYS", "90"))
ANALYTICS_API_KEY = os.getenv("ANALYTICS_API_KEY", "")
