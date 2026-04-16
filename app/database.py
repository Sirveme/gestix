from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import text
from pathlib import Path
from app.config import settings

TENANT_INIT_SQL = Path(__file__).parent / "migrations" / "tenant_init.sql"

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENTORNO == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Crea tablas del schema público (sistema base) si no existen."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def crear_schema_tenant(schema: str):
    """Crea un schema PostgreSQL para un nuevo tenant, crea sus tablas
    y ejecuta tenant_init.sql con los datos iniciales (regímenes, medios de cobro)."""
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.execute(text(f'SET search_path TO "{schema}"'))
        await conn.run_sync(Base.metadata.create_all)

        if TENANT_INIT_SQL.exists():
            sql = TENANT_INIT_SQL.read_text(encoding="utf-8")
            sentencias = [
                s.strip() for s in sql.split(";")
                if s.strip() and not all(
                    line.startswith("--") for line in s.strip().splitlines() if line.strip()
                )
            ]
            for sentencia in sentencias:
                await conn.execute(text(sentencia))

        await conn.execute(text('SET search_path TO public'))


async def eliminar_schema_tenant(schema: str):
    """Elimina el schema de un tenant (con confirmación explícita)."""
    async with engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
