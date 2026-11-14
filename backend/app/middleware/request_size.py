"""Bound search bodies before JSON/base64 decoding, including streamed bodies."""

from starlette.responses import JSONResponse

MAX_SEARCH_BODY_BYTES = 5 * 1024 * 1024


class SearchBodyLimitMiddleware:
    def __init__(self, app, max_bytes=MAX_SEARCH_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if not (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and scope.get("path", "").startswith("/api/search/")
        ):
            return await self.app(scope, receive, send)

        async def too_large():
            await JSONResponse(
                {"detail": "検索リクエストが大きすぎます。"}, status_code=413
            )(scope, receive, send)

        for key, value in scope.get("headers", []):
            if key.lower() == b"content-length":
                try:
                    if int(value) > self.max_bytes:
                        return await too_large()
                except ValueError:
                    pass  # The actual streamed byte count remains authoritative.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.max_bytes:
                return await too_large()
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
