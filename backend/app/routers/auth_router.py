"""認証関連のAPIエンドポイント"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import hash_password, verify_password, create_access_token, get_current_user
from ..database import get_db
from ..models import User
from ..schemas import UserCreate, UserLogin, TokenResponse, UserResponse, UserSettingsUpdate, ChangePassword

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, db: AsyncSession = Depends(get_db)):
    """新規ユーザー登録"""
    # ユーザー名の重複チェック
    result = await db.execute(select(User).where(User.username == body.username))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="このユーザー名は既に使用されています",
        )

    # ユーザー作成
    user = User(
        username=body.username,
        hashed_password=hash_password(body.password),
        age=body.age,
        gender=body.gender,
        district_id=body.district_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # トークン発行
    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    """ログイン"""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ユーザー名またはパスワードが正しくありません",
        )

    token = create_access_token(user.id, user.username)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """現在のログインユーザー情報を取得"""
    return current_user


@router.put("/settings", response_model=UserResponse)
async def update_settings(
    body: UserSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """ユーザー設定を更新（地域設定等を保存）"""
    current_user.settings = body.settings
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.put("/change-password")
async def change_password(
    body: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """パスワード変更"""
    # 現在のパスワードを検証
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="現在のパスワードが正しくありません",
        )

    # 新しいパスワードをハッシュ化して保存
    current_user.hashed_password = hash_password(body.new_password)
    await db.commit()

    return {"message": "パスワードを変更しました"}
