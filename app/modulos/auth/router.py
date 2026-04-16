from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.tenant import get_tenant_session
from app.modulos.auth.models import Usuario, Rol, Accion, UsuarioPermiso, RolPermiso
from app.modulos.auth.permisos import get_permisos_usuario, ACCIONES_SISTEMA
import bcrypt

router = APIRouter(prefix="/usuarios", tags=["usuarios"])
templates = Jinja2Templates(directory="templates")


def ctx(request: Request, **kwargs):
    return {
        "request": request,
        "nombre": getattr(request.state, "nombre", ""),
        "empresa_nombre": getattr(request.state, "empresa_nombre", ""),
        **kwargs
    }


@router.get("/", response_class=HTMLResponse)
async def usuarios_lista(request: Request,
                          db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(Usuario).order_by(Usuario.nombre_completo))
    usuarios = result.scalars().all()
    return templates.TemplateResponse("usuarios/lista.html",
        ctx(request, usuarios=usuarios))


@router.get("/nuevo", response_class=HTMLResponse)
async def usuario_nuevo_get(request: Request,
                             db: AsyncSession = Depends(get_tenant_session)):
    roles = (await db.execute(
        select(Rol).where(Rol.activo == True).order_by(Rol.orden)
    )).scalars().all()
    return templates.TemplateResponse("usuarios/form.html",
        ctx(request, usuario=None, roles=roles))


@router.post("/nuevo")
async def usuario_nuevo_post(request: Request,
                              db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    clave = form.get("clave", "Gestix2024!")
    clave_hash = bcrypt.hashpw(
        clave.encode()[:72], bcrypt.gensalt(rounds=12)).decode()

    usuario = Usuario(
        usuario=form.get("usuario"),
        dni=form.get("dni") or None,
        nombre_completo=form.get("nombre_completo"),
        correo=form.get("correo") or None,
        celular=form.get("celular") or None,
        id_rol=int(form["id_rol"]) if form.get("id_rol") else None,
        clave_hash=clave_hash,
        activo=form.get("activo") == "on",
        debe_cambiar_clave=True,
        created_by=int(getattr(request.state, "user_id", 0) or 0),
    )
    db.add(usuario)
    await db.commit()
    return RedirectResponse(url="/usuarios/", status_code=302)


@router.get("/{id}/permisos", response_class=HTMLResponse)
async def usuario_permisos_get(request: Request, id: int,
                                db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(Usuario).where(Usuario.id == id))
    usuario = result.scalar_one_or_none()
    if not usuario:
        return RedirectResponse(url="/usuarios/", status_code=302)

    permisos_actuales = await get_permisos_usuario(db, id)

    permisos_rol = set()
    if usuario.id_rol:
        r = await db.execute(
            select(Accion.codigo)
            .join(RolPermiso, RolPermiso.id_accion == Accion.id)
            .where(RolPermiso.id_rol == usuario.id_rol)
        )
        permisos_rol = {row[0] for row in r.fetchall()}

    r_extra = await db.execute(
        select(UsuarioPermiso).where(UsuarioPermiso.id_usuario == id))
    extras = {e.id_accion: e.permitido for e in r_extra.scalars().all()}

    r_acciones = await db.execute(
        select(Accion).where(Accion.activo == True).order_by(
            Accion.modulo, Accion.codigo))
    acciones = r_acciones.scalars().all()

    modulos = {}
    for acc in acciones:
        if acc.modulo not in modulos:
            modulos[acc.modulo] = []
        modulos[acc.modulo].append({
            "accion": acc,
            "en_rol": acc.codigo in permisos_rol,
            "activo": acc.codigo in permisos_actuales,
            "es_extra": acc.id in extras,
        })

    return templates.TemplateResponse("usuarios/permisos.html", ctx(request,
        usuario=usuario,
        modulos=modulos,
        permisos_actuales=permisos_actuales,
    ))


@router.post("/{id}/permisos")
async def usuario_permisos_post(request: Request, id: int,
                                 db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()

    r_acciones = await db.execute(select(Accion).where(Accion.activo == True))
    acciones = r_acciones.scalars().all()

    result = await db.execute(select(Usuario).where(Usuario.id == id))
    usuario = result.scalar_one_or_none()
    permisos_rol = set()
    if usuario and usuario.id_rol:
        r = await db.execute(
            select(Accion.codigo)
            .join(RolPermiso, RolPermiso.id_accion == Accion.id)
            .where(RolPermiso.id_rol == usuario.id_rol)
        )
        permisos_rol = {row[0] for row in r.fetchall()}

    await db.execute(
        delete(UsuarioPermiso).where(UsuarioPermiso.id_usuario == id))

    for accion in acciones:
        en_form = form.get(f"perm_{accion.id}") == "on"
        en_rol = accion.codigo in permisos_rol

        if en_form and not en_rol:
            db.add(UsuarioPermiso(
                id_usuario=id, id_accion=accion.id, permitido=True))
        elif not en_form and en_rol:
            db.add(UsuarioPermiso(
                id_usuario=id, id_accion=accion.id, permitido=False))

    await db.commit()
    return RedirectResponse(url=f"/usuarios/{id}/permisos", status_code=302)


@router.get("/roles", response_class=HTMLResponse)
async def roles_lista(request: Request,
                       db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(Rol).order_by(Rol.orden))
    roles = result.scalars().all()
    return templates.TemplateResponse("usuarios/roles.html",
        ctx(request, roles=roles))
