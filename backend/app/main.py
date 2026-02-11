from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agents import router as agents_router
from app.api.analysis import router as analysis_router
from app.api.debates import router as debates_router
from app.api.reactions import router as reactions_router
from app.api.turns import router as turns_router

app = FastAPI(
    title="AgonAI",
    description="AI Autonomous Debate Platform",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents_router)
app.include_router(debates_router)
app.include_router(turns_router)
app.include_router(reactions_router)
app.include_router(analysis_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
