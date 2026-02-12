"""Raw ASGI middleware to enforce request body size limit (10KB)."""

import json

MAX_BODY_BYTES = 10240  # 10KB
_SKIP_METHODS = {b"GET", b"HEAD", b"OPTIONS"}
_ERROR_BODY = json.dumps({"detail": "Request body too large. Maximum size is 10KB."}).encode("utf-8")


class BodyLimitMiddleware:
    """ASGI middleware that rejects request bodies larger than 10KB."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").encode("utf-8") if isinstance(scope.get("method"), str) else scope.get("method", b"GET")
        if method in _SKIP_METHODS:
            await self.app(scope, receive, send)
            return

        # Check content-length header if present
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                if int(content_length) > MAX_BODY_BYTES:
                    await self._send_413(send)
                    return
            except (ValueError, TypeError):
                pass

        # Wrap receive to track streamed bytes (handles chunked encoding)
        bytes_received = 0
        rejected = False

        async def limited_receive():
            nonlocal bytes_received, rejected
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                bytes_received += len(body)
                if bytes_received > MAX_BODY_BYTES:
                    rejected = True
                    raise _BodyTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await self._send_413(send)

    @staticmethod
    async def _send_413(send):
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                [b"content-type", b"application/json"],
                [b"content-length", str(len(_ERROR_BODY)).encode("utf-8")],
            ],
        })
        await send({
            "type": "http.response.body",
            "body": _ERROR_BODY,
        })


class _BodyTooLarge(Exception):
    pass
