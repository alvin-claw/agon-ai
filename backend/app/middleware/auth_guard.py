"""Auth failure blocking middleware: blocks IPs after 5 consecutive 401 responses."""

import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Endpoints to track for auth failures
_AUTH_PATHS = ("/api/auth/", "/api/agents")
_REGENERATE_KEY = "/regenerate-key"

MAX_FAILURES = 5
BLOCK_DURATION_SECONDS = 3600  # 1 hour


class AuthFailureTracker:
    """Tracks consecutive auth failures per IP address."""

    def __init__(self):
        self._records: dict[str, dict] = {}
        # {ip: {"fail_count": int, "blocked_until": float | None}}

    def is_blocked(self, ip: str) -> bool:
        record = self._records.get(ip)
        if not record or not record.get("blocked_until"):
            return False
        if time.monotonic() >= record["blocked_until"]:
            # Block expired — lazy cleanup
            del self._records[ip]
            return False
        return True

    def record_failure(self, ip: str):
        record = self._records.get(ip)
        if record is None:
            record = {"fail_count": 0, "blocked_until": None}
            self._records[ip] = record
        record["fail_count"] += 1
        if record["fail_count"] >= MAX_FAILURES:
            record["blocked_until"] = time.monotonic() + BLOCK_DURATION_SECONDS

    def record_success(self, ip: str):
        self._records.pop(ip, None)


_tracker = AuthFailureTracker()


def _is_tracked_path(path: str) -> bool:
    if path.startswith(_AUTH_PATHS):
        return True
    if _REGENERATE_KEY in path:
        return True
    return False


class AuthGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        path = request.url.path

        if _is_tracked_path(path) and _tracker.is_blocked(ip):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many authentication failures. Try again later."},
            )

        response = await call_next(request)

        if _is_tracked_path(path):
            if response.status_code == 401:
                _tracker.record_failure(ip)
            elif 200 <= response.status_code < 300:
                _tracker.record_success(ip)

        return response
