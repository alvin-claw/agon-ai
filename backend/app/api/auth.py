from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_access_token, get_current_developer
from app.config import settings
from app.database import get_db
from app.models.developer import Developer
from app.schemas.developer import DeveloperResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


@router.get("/github")
async def github_login():
    params = urlencode({
        "client_id": settings.github_client_id,
        "redirect_uri": "http://localhost:8000/api/auth/github/callback",
        "scope": "read:user user:email",
    })
    return {"url": f"{GITHUB_AUTHORIZE_URL}?{params}"}


@router.get("/github/callback")
async def github_callback(code: str = Query(...), db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to exchange code for token")
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=502, detail="No access token received from GitHub")

        user_resp = await client.get(
            GITHUB_USER_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to fetch GitHub user info")
        user_data = user_resp.json()

    github_id = user_data["id"]
    result = await db.execute(select(Developer).where(Developer.github_id == github_id))
    developer = result.scalar_one_or_none()

    if developer:
        developer.github_login = user_data["login"]
        developer.github_avatar_url = user_data.get("avatar_url")
        developer.email = user_data.get("email")
    else:
        developer = Developer(
            github_id=github_id,
            github_login=user_data["login"],
            github_avatar_url=user_data.get("avatar_url"),
            email=user_data.get("email"),
        )
        db.add(developer)

    await db.commit()
    await db.refresh(developer)

    jwt_token = create_access_token(developer.id)
    return RedirectResponse(url=f"http://localhost:3000/register?token={jwt_token}")


@router.get("/me", response_model=DeveloperResponse)
async def get_me(developer: Developer = Depends(get_current_developer)):
    return developer
