from fastapi import Depends, HTTPException, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from app.config import settings
from app.database import get_db
from app.tenant import get_tenant_session
from typing import Optional


async def get_current_user(
    session_token: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Valida JWT y retorna el usuario actual. Para rutas del sistema (schema public)."""
    if not session_token:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        payload = jwt.decode(session_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("sub")
        schema: str = payload.get("schema")
        if not user_id or not schema:
            raise HTTPException(status_code=401, detail="Token inválido")
        return {"id": user_id, "schema": schema, "payload": payload}
    except JWTError:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
