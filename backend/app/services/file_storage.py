"""ファイルストレージサービス - 画像ファイルの保存・削除を管理する"""

import os
import uuid

import aiofiles
from fastapi import UploadFile


class FileStorageService:
    """ファイルシステムへの非同期ファイル保存・削除を提供するサービス"""

    def __init__(self, upload_dir: str = "uploads"):
        self.upload_dir = upload_dir
        os.makedirs(self.upload_dir, exist_ok=True)

    def _generate_filename(self, original_filename: str) -> str:
        """UUIDベースのユニークなファイル名を生成する"""
        ext = os.path.splitext(original_filename)[1]
        return f"{uuid.uuid4().hex}{ext}"

    async def save(self, file: UploadFile, filename: str) -> str:
        """ファイルを保存し、保存パスを返す

        Args:
            file: アップロードされたファイル
            filename: 保存時のファイル名（UUIDベース）

        Returns:
            保存先の相対パス
        """
        filepath = os.path.join(self.upload_dir, filename)

        async with aiofiles.open(filepath, "wb") as f:
            content = await file.read()
            await f.write(content)

        return filepath

    async def delete(self, filepath: str) -> None:
        """ファイルを削除する

        Args:
            filepath: 削除するファイルのパス
        """
        if os.path.exists(filepath):
            os.remove(filepath)
