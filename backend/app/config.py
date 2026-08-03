"""アプリケーション設定"""

import os

# JWT設定
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7日間

# データベース設定
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./garbage_app.db")
