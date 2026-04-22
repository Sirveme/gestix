from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, FileResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from app.config import settings

BASE_DIR = Path(__file__).parent  # apunta a app/
from app.database import init_db
from app.migrations.runner import ejecutar_migraciones_pendientes
from app.auth.middleware import auth_middleware
from app.auth.router import router as auth_router
from app.modulos.config.router import router as config_router
from app.modulos.catalogo.router import router as catalogo_router
from app.modulos.ventas.router import router as ventas_router, public_router as ventas_public_router
from app.modulos.auth.router import router as auth_op_router
from app.modulos.compras.router import router as compras_router
from app.modulos.inventario.router import router as inventario_router
from app.modulos.contabilidad.router import router as contabilidad_router
from app.modulos.pagook.router import router as pagook_router

# Importar todos los modelos para create_all
from app.core import models as core_models                      # noqa
from app.modulos.auth import models as auth_models              # noqa
from app.modulos.config import models as config_models          # noqa
from app.modulos.catalogo import models as catalogo_models      # noqa
from app.modulos.clientes import models as clientes_models      # noqa
from app.modulos.compras import models as compras_models        # noqa
from app.modulos.almacen import models as almacen_models        # noqa
from app.modulos.tesoreria import models as tesoreria_models    # noqa
from app.modulos.rrhh import models as rrhh_models              # noqa
from app.modulos.ventas import models as ventas_models          # noqa
from app.modulos.inventario import models as inventario_models  # noqa
from app.modulos.contabilidad import models as contabilidad_models  # noqa
from app.modulos.pagook import models as pagook_models              # noqa

templates = Jinja2Templates(directory="templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[Gestix] Iniciando en modo: {settings.MODO_DEPLOY}")
    await init_db()
    await ejecutar_migraciones_pendientes()
    yield
    print("[Gestix] Cerrando...")


app = FastAPI(
    title="Gestix",
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.ENTORNO == "development" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(BaseHTTPMiddleware, dispatch=auth_middleware)

# -- Routers --
app.include_router(auth_router)
app.include_router(config_router)
app.include_router(catalogo_router)
app.include_router(ventas_router)
app.include_router(ventas_public_router)
app.include_router(auth_op_router)
app.include_router(compras_router)
app.include_router(inventario_router)
app.include_router(contabilidad_router)
app.include_router(pagook_router)


@app.get("/", response_class=FileResponse)
async def home():
    return FileResponse(str(BASE_DIR / "static" / "home" / "index.html"))


@app.get("/ping")
async def ping():
    return {"status": "ok", "version": settings.APP_VERSION, "producto": "Gestix"}


# -- Static mounts (al final, después de routers y rutas) --
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/landing", StaticFiles(
    directory=str(BASE_DIR / "static" / "landing"),
    html=True
), name="landing")