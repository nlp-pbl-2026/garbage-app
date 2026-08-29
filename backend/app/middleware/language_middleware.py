"""言語ミドルウェア - Accept-Language ヘッダーを解析し request.state.language を設定する。"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# サポートする言語コード
SUPPORTED_LANGUAGES = ("ja", "en", "pt", "zh", "vi")
DEFAULT_LANGUAGE = "ja"


class LanguageMiddleware(BaseHTTPMiddleware):
    """Accept-Language ヘッダーから言語を判定し request.state.language に設定する。

    サポート外の言語やヘッダーが無い場合は日本語（ja）にフォールバックする。
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        language = self._parse_language(request)
        request.state.language = language
        response = await call_next(request)
        return response

    @staticmethod
    def _parse_language(request: Request) -> str:
        """Accept-Language ヘッダーから最優先の対応言語を返す。"""
        accept_language = request.headers.get("accept-language", "")

        if not accept_language:
            return DEFAULT_LANGUAGE

        # Accept-Language を解析（例: "ja,en;q=0.9,pt;q=0.8"）
        languages_with_quality = []
        for part in accept_language.split(","):
            part = part.strip()
            if ";q=" in part:
                lang, quality = part.split(";q=", 1)
                try:
                    q = float(quality)
                except ValueError:
                    q = 0.0
            else:
                lang = part
                q = 1.0
            # 言語コードの先頭2文字だけ使用（例: "ja-JP" → "ja"）
            lang_code = lang.strip().split("-")[0].lower()
            languages_with_quality.append((lang_code, q))

        # 品質値の降順でソート
        languages_with_quality.sort(key=lambda x: -x[1])

        # サポート言語から最優先のものを返す
        for lang_code, _ in languages_with_quality:
            if lang_code in SUPPORTED_LANGUAGES:
                return lang_code

        return DEFAULT_LANGUAGE
