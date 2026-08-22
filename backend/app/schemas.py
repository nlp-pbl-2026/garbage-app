"""リクエスト/レスポンススキーマ"""

from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    """ユーザー登録リクエスト"""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=100)
    age: int | None = Field(default=None, ge=1, le=150)
    gender: str | None = Field(default=None, pattern=r"^(male|female|other)$")
    district_id: str | None = Field(default=None, max_length=20)


class UserLogin(BaseModel):
    """ログインリクエスト"""

    username: str
    password: str


class TokenResponse(BaseModel):
    """トークンレスポンス"""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """ユーザー情報レスポンス"""

    id: int
    username: str
    age: int | None = None
    gender: str | None = None
    district_id: str | None = None
    settings: dict | None = None

    class Config:
        from_attributes = True


class UserSettingsUpdate(BaseModel):
    """ユーザー設定更新リクエスト"""

    settings: dict


class ImageUploadResponse(BaseModel):
    """画像アップロードレスポンス"""

    id: str
    filename: str
    file_size: int
    content_type: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ImageErrorResponse(BaseModel):
    """画像エラーレスポンス"""

    detail: str


class ChangePassword(BaseModel):
    """パスワード変更リクエスト"""

    current_password: str
    new_password: str = Field(min_length=6, max_length=100)


# --- RAG スキーマ ---

from pydantic import field_validator


class RAGQueryRequest(BaseModel):
    """RAGクエリリクエスト"""

    query: str = Field(min_length=1)
    municipality_id: str | None = None
    municipality_name: str | None = None
    district_id: str | None = None
    district_name: str | None = None

    @field_validator("query")
    @classmethod
    def query_not_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be empty or whitespace only")
        return v


class RAGSource(BaseModel):
    """RAGソース情報"""

    title: str | None = None
    uri: str | None = None
    snippet: str | None = None


class RAGQueryResponse(BaseModel):
    """RAGクエリレスポンス"""

    answer: str
    sources: list[RAGSource] = []
