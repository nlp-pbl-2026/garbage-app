"""画像アップロードルーター"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..database import get_db
from ..models import UploadedImage, User
from ..schemas import ImageUploadResponse
from ..services.file_storage import FileStorageService
from ..services.image_validator import validate_image

router = APIRouter(prefix="/api/images", tags=["images"])

# FileStorageService インスタンス
_storage_service = FileStorageService()


@router.post("/upload", response_model=ImageUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImageUploadResponse:
    """画像ファイルをアップロードする

    1. ImageValidator でバリデーション（フォーマット・サイズ）
    2. FileStorageService でファイル保存
    3. DB にメタデータ保存
    4. ImageUploadResponse を返却
    """
    # 1. バリデーション（不正な場合は HTTPException が raise される）
    await validate_image(file)

    # 2. ファイル保存
    # ファイルサイズを取得するため内容を読み込み
    content = await file.read()
    file_size = len(content)
    await file.seek(0)

    # UUID ベースのファイル名を生成して保存
    stored_filename = _storage_service._generate_filename(file.filename or "image.png")
    try:
        storage_path = await _storage_service.save(file, stored_filename)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ファイルの保存に失敗しました",
        )

    # 3. DB にメタデータ保存
    image_id = str(uuid.uuid4())
    uploaded_image = UploadedImage(
        id=image_id,
        user_id=current_user.id,
        filename=stored_filename,
        original_filename=file.filename or "unknown",
        file_size=file_size,
        content_type=file.content_type or "application/octet-stream",
        storage_path=storage_path,
        uploaded_at=datetime.utcnow(),
    )

    db.add(uploaded_image)
    await db.commit()
    await db.refresh(uploaded_image)

    # 4. レスポンス返却
    return ImageUploadResponse(
        id=uploaded_image.id,
        filename=uploaded_image.original_filename,
        file_size=uploaded_image.file_size,
        content_type=uploaded_image.content_type,
        uploaded_at=uploaded_image.uploaded_at,
    )
