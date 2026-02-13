from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.agents import router as agents_router
from app.middleware.auth_guard import AuthGuardMiddleware
from app.middleware.body_limit import BodyLimitMiddleware
from app.api.analysis import router as analysis_router
from app.api.auth import router as auth_router
from app.api.debates import router as debates_router
from app.api.factcheck import router as factcheck_router
from app.api.live import router as live_router
from app.api.reactions import router as reactions_router
from app.api.sandbox import router as sandbox_router
from app.api.topics import router as topics_router
from app.api.turns import router as turns_router
from app.config import settings
from app.engine.factcheck_worker import factcheck_worker


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="AgonAI",
    description="AI Autonomous Debate Platform",
    version="0.1.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(BodyLimitMiddleware)
app.add_middleware(AuthGuardMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(sandbox_router)
app.include_router(debates_router)
app.include_router(turns_router)
app.include_router(reactions_router)
app.include_router(analysis_router)
app.include_router(factcheck_router)
app.include_router(topics_router)
app.include_router(live_router)


@app.on_event("startup")
async def startup_factcheck_worker():
    await factcheck_worker.recover_pending()
    factcheck_worker.start()


@app.get("/health")
async def health():
    return {"status": "ok"}
