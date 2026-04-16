from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.auth.utils import verify_password, crear_token
import bcrypt

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    token = request.cookies.get("session_token")
    if token:
        return RedirectResponse(url="/seleccionar-empresa", status_code=302)
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
async def login_post(
    request: Request,
    usuario: str = Form(...),
    clave: str = Form(...),
):
    async with AsyncSessionLocal() as db:
        # Buscar usuario master
        result = await db.execute(
            text("""
                SELECT m.id, m.clave_hash, m.nombre, m.id_empresa, m.es_superadmin
                FROM erp_usuarios_master m
                WHERE (m.email = :u) AND m.activo = true
            """),
            {"u": usuario}
        )
        user = result.fetchone()

        if not user or not verify_password(clave, user.clave_hash):
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Usuario o clave incorrectos"},
                status_code=401
            )

        # Obtener empresas asociadas al usuario
        result2 = await db.execute(
            text("""
                SELECT e.id, e.ruc, e.razon_social, e.nombre_comercial, e.schema_db, e.plan
                FROM erp_empresas e
                JOIN erp_usuarios_master m ON m.id_empresa = e.id
                WHERE m.id = :uid AND e.activo = true
                UNION
                -- superadmin ve todas
                SELECT e.id, e.ruc, e.razon_social, e.nombre_comercial, e.schema_db, e.plan
                FROM erp_empresas e
                WHERE :superadmin = true AND e.activo = true
                ORDER BY razon_social
            """),
            {"uid": user.id, "superadmin": user.es_superadmin}
        )
        empresas = [dict(r._mapping) for r in result2.fetchall()]

    # Token sin empresa_id todavía — fuerza al selector
    token = crear_token({
        "sub": str(user.id),
        "nombre": user.nombre,
        "es_superadmin": user.es_superadmin,
        "empresa_id": None,
        "schema": None,
        "empresas": empresas,
    })

    response = RedirectResponse(url="/seleccionar-empresa", status_code=302)
    response.set_cookie(
        key="session_token", value=token,
        httponly=True, max_age=3600 * 8, samesite="lax"
    )
    return response


@router.get("/seleccionar-empresa", response_class=HTMLResponse)
async def seleccionar_empresa_get(request: Request):
    token = request.cookies.get("session_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    from app.auth.utils import decodificar_token
    payload = decodificar_token(token)
    if not payload:
        return RedirectResponse(url="/login", status_code=302)

    empresas = payload.get("empresas", [])
    nombre = payload.get("nombre", "")

    # Si solo tiene una empresa, seleccionar automáticamente
    if len(empresas) == 1:
        return RedirectResponse(
            url=f"/seleccionar-empresa/confirmar/{empresas[0]['id']}",
            status_code=302
        )

    return templates.TemplateResponse("seleccionar_empresa.html", {
        "request": request,
        "empresas": empresas,
        "nombre": nombre,
    })


@router.get("/seleccionar-empresa/confirmar/{empresa_id}")
async def confirmar_empresa(request: Request, empresa_id: int):
    token = request.cookies.get("session_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)
    from app.auth.utils import decodificar_token, crear_token
    payload = decodificar_token(token)
    if not payload:
        return RedirectResponse(url="/login", status_code=302)

    empresas = payload.get("empresas", [])
    empresa = next((e for e in empresas if e["id"] == empresa_id), None)
    if not empresa:
        return RedirectResponse(url="/seleccionar-empresa", status_code=302)

    schema = empresa["schema_db"]
    permisos = []

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text(f'SET search_path TO "{schema}", public'))
            permisos = ["sistema.acceso_total"]
    except Exception:
        permisos = ["sistema.acceso_total"]

    nuevo_token = crear_token({
        "sub": payload["sub"],
        "nombre": payload["nombre"],
        "es_superadmin": payload.get("es_superadmin", False),
        "empresa_id": empresa["id"],
        "empresa_nombre": empresa.get("nombre_comercial") or empresa["razon_social"],
        "schema": schema,
        "empresas": empresas,
        "permisos": permisos,
    })

    response = RedirectResponse(url="/dashboard", status_code=302)
    response.set_cookie(
        key="session_token", value=nuevo_token,
        httponly=True, max_age=3600 * 8, samesite="lax"
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie("session_token")
    return response


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "nombre": getattr(request.state, "nombre", "Usuario"),
        "empresa_nombre": getattr(request.state, "empresa_nombre", ""),
        "empresas": getattr(request.state, "empresas", []),
    })
