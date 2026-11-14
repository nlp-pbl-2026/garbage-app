"""認証ユーティリティ（パスワードハッシュ化・JWT生成・検証）"""

from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import config
from .database import get_db
from .models import User
from .password_policy import validate_password_bytes

# パスワードハッシュ化
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer トークン
security = HTTPBearer()


def require_auth_config() -> str:
    # Validate at the auth boundary, not at module import: Lambda's search-only
    # app must remain usable without a JWT key or auth/database dependencies.
    key = config.SECRET_KEY
    if not key or len(key.encode("utf-8")) < 32:
        raise HTTPException(status_code=503, detail="認証機能が設定されていません。")
    return key


def hash_password(password: str) -> str:
    """パスワードをbcryptでハッシュ化する"""
    return pwd_context.hash(validate_password_bytes(password))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """パスワードを検証する"""
    try:
        validate_password_bytes(plain_password)
    except ValueError:
        return False
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: int, username: str) -> str:
    """JWTアクセストークンを生成する"""
    key = require_auth_config()
    expire = datetime.utcnow() + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, key, algorithm=config.ALGORITHM)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """現在のログインユーザーを取得する（JWT検証）"""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="認証情報が無効です",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            require_auth_config(),
            algorithms=[config.ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
        user_id: str | None = payload.get("sub")
        if (
            not isinstance(user_id, str)
            or not user_id.isascii()
            or not user_id.isdecimal()
            or len(user_id) > 19
        ):
            raise credentials_exception
        if not 0 < int(user_id) <= 2**63 - 1:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user
