"""
Manejo de multi-tenancy por schema PostgreSQL.
Cada empresa tiene su propio schema: empresa_{ruc}
El schema 'public' contiene solo las tablas del sistema (licencias, empresas, usuarios master).
"""
from fastapi import Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.database import AsyncSessionLocal
import re


def schema_nombre(ruc: str) -> str:
    """Genera nombre de schema seguro a partir del RUC."""
    ruc_limpio = re.sub(r'[^0-9]', '', ruc)
    if len(ruc_limpio) not in (8, 11):
        raise ValueError(f"RUC/DNI inválido: {ruc}")
    return f"emp_{ruc_limpio}"


async def get_tenant_session(request: Request) -> AsyncSession:
    """
    Obtiene una sesión de DB con el search_path apuntando al schema del tenant.
    El tenant se identifica por el JWT en la cookie de sesión.
    """
    schema = getattr(request.state, "tenant_schema", None)
    if not schema:
        raise HTTPException(status_code=401, detail="Sesión sin tenant identificado")

    session = AsyncSessionLocal()
    try:
        await session.execute(text(f'SET search_path TO "{schema}", public'))
        yield session
    finally:
        await session.close()


def set_tenant(request: Request, schema: str):
    """Guarda el schema del tenant en el estado del request (llamado desde middleware JWT)."""
    request.state.tenant_schema = schema
