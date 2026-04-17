from fastapi import Request
from fastapi.responses import RedirectResponse
from app.auth.utils import decodificar_token

RUTAS_PUBLICAS_EXACTAS = {"/", "/login", "/ping", "/logout", "/seleccionar-empresa"}
RUTAS_PUBLICAS_PREFIJOS = [
    "/static/",
    "/landing",
    "/home",
    "/ping",
    "/api/pixel",
    "/seleccionar-empresa/confirmar",
]


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if path in RUTAS_PUBLICAS_EXACTAS:
        return await call_next(request)
    if any(path.startswith(p) for p in RUTAS_PUBLICAS_PREFIJOS):
        return await call_next(request)

    token = request.cookies.get("session_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    payload = decodificar_token(token)
    if not payload:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("session_token")
        return response

    request.state.user_id = payload.get("sub")
    request.state.tenant_schema = payload.get("schema")
    request.state.nombre = payload.get("nombre")
    request.state.empresa_nombre = payload.get("empresa_nombre", "")
    request.state.empresa_id = payload.get("empresa_id")
    request.state.es_contador = payload.get("es_contador", False)
    request.state.empresas = payload.get("empresas", [])
    request.state.empresas_usuario = payload.get("empresas", [])
    request.state.empresa_id_actual = payload.get("empresa_id")
    request.state.permisos = set(payload.get("permisos", []))

    # Si está autenticado pero no ha seleccionado empresa → selector
    if not payload.get("empresa_id") and path != "/seleccionar-empresa":
        return RedirectResponse(url="/seleccionar-empresa", status_code=302)

    return await call_next(request)
