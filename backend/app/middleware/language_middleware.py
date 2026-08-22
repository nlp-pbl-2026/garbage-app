"""Accept-Language ヘッダー解析ミドルウェア

RFC 9110 準拠の Accept-Language ヘッダーパースを行い、
サポート言語の中から最適な言語を決定して request.state.language に設定する。
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from .language_resolver import SUPPORTED_LANGUAGES, resolve_language

# Re-export for backwards compatibility
__all__ = ["LanguageMiddleware", "resolve_language", "SUPPORTED_LANGUAGES"]


class LanguageMiddleware(BaseHTTPMiddleware):
    """Accept-Language ヘッダーを解析し、request.state.language に解決結果を設定するミドルウェア"""

    async def dispatch(self, request: Request, call_next):
        language = resolve_language(request.headers.get("accept-language"))
        request.state.language = language
        response = await call_next(request)
        return response
