import jwt
from datetime import datetime, timezone, timedelta
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.developer import Developer

security = HTTPBearer(auto_error=False)


def create_access_token(developer_id: UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(developer_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def get_current_developer(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Developer:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        developer_id = UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(Developer).where(Developer.id == developer_id))
    developer = result.scalar_one_or_none()
    if not developer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Developer not found")
    return developer


async def optional_developer(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Developer | None:
    if not credentials:
        return None
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        developer_id = UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        return None
    result = await db.execute(select(Developer).where(Developer.id == developer_id))
    return result.scalar_one_or_none()
