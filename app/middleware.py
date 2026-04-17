from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from app.auth.utils import decodificar_token

# Rutas exactas que NO requieren autenticación
RUTAS_PUBLICAS_EXACTAS = {"/", "/login", "/ping", "/logout", "/walter"}
# Prefijos públicos (archivos estáticos, etc.)
PREFIJOS_PUBLICOS = ("/static/",)


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Permitir rutas públicas exactas y prefijos (estáticos)
    if path in RUTAS_PUBLICAS_EXACTAS or path.startswith(PREFIJOS_PUBLICOS):
        return await call_next(request)

    token = request.cookies.get("session_token")
    if not token:
        return RedirectResponse(url="/login", status_code=302)

    payload = decodificar_token(token)
    if not payload:
        response = RedirectResponse(url="/login", status_code=302)
        response.delete_cookie("session_token")
        return response

    # Inyectar datos del usuario en el request
    request.state.user_id = payload.get("sub")
    request.state.tenant_schema = payload.get("schema")
    request.state.nombre = payload.get("nombre")

    return await call_next(request)
