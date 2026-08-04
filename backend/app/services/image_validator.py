"""画像バリデーションサービス"""

from fastapi import HTTPException, UploadFile, status

SUPPORTED_CONTENT_TYPES = {"image/jpeg", "image/png"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


async def validate_image(file: UploadFile) -> None:
    """画像ファイルのバリデーション。不正な場合はHTTPExceptionをraise。

    Args:
        file: アップロードされたファイル

    Raises:
        HTTPException: Content-Typeが非対応（400）またはサイズ超過（413）
    """
    # Content-Type チェック
    if file.content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="サポートされていない画像形式です。JPEG または PNG を使用してください",
        )

    # ファイルサイズチェック
    content = await file.read()
    file_size = len(content)
    # ファイルポインタを先頭に戻す（後続処理で再読み込み可能に）
    await file.seek(0)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="ファイルサイズが上限（10MB）を超えています",
        )
