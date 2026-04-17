from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from datetime import date, datetime
from app.tenant import get_tenant_session
from app.modulos.contabilidad.models import (
    CuentaContable, AsientoContable, PartidaContable,
    ConfigContable, LibroElectronico, RegistroSIRE,
    MovimientoBancario, DeclaracionTributaria,
    DiagnosticoEmpresa, HallazgoDiagnostico,
)
from app.modulos.contabilidad.service import (
    calcular_declaracion_mensual, ejecutar_scan,
    generar_asiento_venta, generar_asiento_compra,
)

router = APIRouter(prefix="/contabilidad", tags=["contabilidad"])
templates = Jinja2Templates(directory="templates")


def ctx(request: Request, **kwargs):
    return {
        "request": request,
        "nombre": getattr(request.state, "nombre", ""),
        "empresa_nombre": getattr(request.state, "empresa_nombre", ""),
        **kwargs
    }


def periodo_actual() -> str:
    return date.today().strftime("%Y-%m")


# -- Dashboard ----------------------------------------

@router.get("/", response_class=HTMLResponse)
async def cont_dashboard(request: Request,
                          db: AsyncSession = Depends(get_tenant_session)):
    periodo = periodo_actual()

    r_diag = await db.execute(
        select(DiagnosticoEmpresa).where(
            DiagnosticoEmpresa.periodo == periodo
        ).order_by(DiagnosticoEmpresa.fecha_scan.desc()).limit(1)
    )
    diagnostico = r_diag.scalar_one_or_none()

    r_decl = await db.execute(
        select(DeclaracionTributaria).where(
            DeclaracionTributaria.periodo == periodo,
            DeclaracionTributaria.tipo == "pdt621",
        )
    )
    declaracion = r_decl.scalar_one_or_none()

    r_asientos = await db.execute(
        select(AsientoContable).order_by(
            AsientoContable.fecha.desc()).limit(10))
    asientos = r_asientos.scalars().all()

    return templates.TemplateResponse("contabilidad/dashboard.html", ctx(request,
        periodo=periodo,
        diagnostico=diagnostico,
        declaracion=declaracion,
        asientos=asientos,
    ))


# -- SCAN / Diagnostico --------------------------------

@router.get("/scan", response_class=HTMLResponse)
async def cont_scan_get(request: Request,
                         db: AsyncSession = Depends(get_tenant_session)):
    periodo = periodo_actual()

    r_hist = await db.execute(
        select(DiagnosticoEmpresa).order_by(
            DiagnosticoEmpresa.fecha_scan.desc()).limit(6))
    historial = r_hist.scalars().all()

    return templates.TemplateResponse("contabilidad/scan.html", ctx(request,
        periodo=periodo, historial=historial))


@router.post("/scan")
async def cont_scan_post(request: Request,
                          db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    periodo = data.get("periodo", periodo_actual())

    diagnostico = await ejecutar_scan(
        db, periodo,
        int(getattr(request.state, "user_id", 0) or 0)
    )
    await db.commit()

    return JSONResponse({
        "ok": True,
        "diagnostico_id": diagnostico.id,
        "estado_global": diagnostico.estado_global,
        "alertas_rojas": diagnostico.total_alertas_rojas,
        "alertas_amarillas": diagnostico.total_alertas_amarillas,
    })


@router.get("/scan/{id}", response_class=HTMLResponse)
async def cont_scan_detalle(request: Request, id: int,
                             db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(DiagnosticoEmpresa).options(
            selectinload(DiagnosticoEmpresa.hallazgos)
        ).where(DiagnosticoEmpresa.id == id)
    )
    diagnostico = result.scalar_one_or_none()
    if not diagnostico:
        return RedirectResponse(url="/contabilidad/scan")

    hallazgos_por_area = {}
    for h in diagnostico.hallazgos:
        if h.area not in hallazgos_por_area:
            hallazgos_por_area[h.area] = []
        hallazgos_por_area[h.area].append(h)

    return templates.TemplateResponse("contabilidad/scan_detalle.html", ctx(request,
        diagnostico=diagnostico,
        hallazgos_por_area=hallazgos_por_area,
    ))


# -- Plan de Cuentas ------------------------------------

@router.get("/cuentas", response_class=HTMLResponse)
async def cont_cuentas(request: Request,
                        db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(CuentaContable).where(
            CuentaContable.nivel <= 3,
            CuentaContable.activo == True,
        ).order_by(CuentaContable.codigo)
    )
    cuentas = result.scalars().all()
    return templates.TemplateResponse("contabilidad/cuentas.html",
        ctx(request, cuentas=cuentas))


@router.post("/cuentas/{id}/alias")
async def cont_cuenta_alias(request: Request, id: int,
                              db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    result = await db.execute(
        select(CuentaContable).where(CuentaContable.id == id))
    cuenta = result.scalar_one_or_none()
    if not cuenta:
        return JSONResponse({"error": "No encontrado"}, status_code=404)
    cuenta.alias = data.get("alias", "")
    await db.commit()
    return JSONResponse({"ok": True})


# -- Asientos -------------------------------------------

@router.get("/asientos", response_class=HTMLResponse)
async def cont_asientos(
    request: Request,
    periodo: str = Query(default=None),
    db: AsyncSession = Depends(get_tenant_session),
):
    p = periodo or periodo_actual()
    result = await db.execute(
        select(AsientoContable).where(
            AsientoContable.periodo == p
        ).order_by(AsientoContable.fecha, AsientoContable.numero)
    )
    asientos = result.scalars().all()

    total_debe = sum(float(a.total_debe or 0) for a in asientos)
    total_haber = sum(float(a.total_haber or 0) for a in asientos)

    return templates.TemplateResponse("contabilidad/asientos.html", ctx(request,
        asientos=asientos, periodo=p,
        total_debe=total_debe, total_haber=total_haber,
    ))


@router.get("/asientos/{id}", response_class=HTMLResponse)
async def cont_asiento_detalle(request: Request, id: int,
                                db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(AsientoContable).options(
            selectinload(AsientoContable.partidas)
        ).where(AsientoContable.id == id)
    )
    asiento = result.scalar_one_or_none()
    if not asiento:
        return HTMLResponse("No encontrado", status_code=404)
    return templates.TemplateResponse("contabilidad/asiento_detalle.html",
        ctx(request, asiento=asiento))


# -- Declaraciones ---------------------------------------

@router.get("/declaraciones", response_class=HTMLResponse)
async def cont_declaraciones(request: Request,
                              db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(DeclaracionTributaria).order_by(
            DeclaracionTributaria.periodo.desc()).limit(24))
    declaraciones = result.scalars().all()
    return templates.TemplateResponse("contabilidad/declaraciones.html",
        ctx(request, declaraciones=declaraciones,
            periodo_actual=periodo_actual()))


@router.post("/declaraciones/calcular")
async def cont_declaracion_calcular(
    request: Request,
    db: AsyncSession = Depends(get_tenant_session),
):
    data = await request.json()
    periodo = data.get("periodo", periodo_actual())

    decl = await calcular_declaracion_mensual(
        db, periodo,
        int(getattr(request.state, "user_id", 0) or 0)
    )
    await db.commit()

    return JSONResponse({
        "ok": True,
        "periodo": decl.periodo,
        "base_ventas": float(decl.base_ventas),
        "igv_ventas": float(decl.igv_ventas),
        "base_compras": float(decl.base_compras),
        "igv_compras": float(decl.igv_compras),
        "igv_a_pagar": float(decl.igv_a_pagar),
        "renta_a_pagar": float(decl.renta_a_pagar),
        "vencimiento": str(decl.fecha_vencimiento),
    })


# -- SIRE -----------------------------------------------

@router.get("/sire", response_class=HTMLResponse)
async def cont_sire(
    request: Request,
    periodo: str = Query(default=None),
    db: AsyncSession = Depends(get_tenant_session),
):
    p = periodo or periodo_actual()
    result = await db.execute(
        select(RegistroSIRE).where(
            RegistroSIRE.periodo == p
        ).order_by(RegistroSIRE.fecha_emision)
    )
    registros = result.scalars().all()

    diferencias = [r for r in registros if r.estado_cruce == "diferencia"]
    solo_sire = [r for r in registros if r.estado_cruce == "solo_sire"]

    return templates.TemplateResponse("contabilidad/sire.html", ctx(request,
        registros=registros, periodo=p,
        diferencias=diferencias, solo_sire=solo_sire,
    ))


# -- Banco / Conciliacion --------------------------------

@router.get("/banco", response_class=HTMLResponse)
async def cont_banco(
    request: Request,
    db: AsyncSession = Depends(get_tenant_session),
):
    result = await db.execute(
        select(MovimientoBancario).order_by(
            MovimientoBancario.fecha.desc()
        ).limit(100)
    )
    movimientos = result.scalars().all()

    pendientes = sum(1 for m in movimientos if m.estado_cruce == "pendiente")
    cruzados = sum(1 for m in movimientos if m.estado_cruce == "cruzado")
    sin_match = sum(1 for m in movimientos if m.estado_cruce == "sin_match")

    return templates.TemplateResponse("contabilidad/banco.html", ctx(request,
        movimientos=movimientos,
        pendientes=pendientes,
        cruzados=cruzados,
        sin_match=sin_match,
    ))


@router.post("/banco/importar")
async def cont_banco_importar(
    request: Request,
    db: AsyncSession = Depends(get_tenant_session),
):
    """Lee correos del IMAP e importa movimientos nuevos."""
    from app.modulos.contabilidad.imap_service import importar_movimientos_bancarios
    from app.modulos.contabilidad.cruce_service import cruzar_pendientes
    try:
        data = await request.json()
        dias = int(data.get("dias", 7))
        resultado = await importar_movimientos_bancarios(db, dias_atras=dias)
        if resultado["nuevos"] > 0:
            cruce = await cruzar_pendientes(db)
            resultado["cruzados_auto"] = cruce["cruzados"]
        return JSONResponse({"ok": True, **resultado})
    except ConnectionError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/banco/cruzar")
async def cont_banco_cruzar(
    request: Request,
    db: AsyncSession = Depends(get_tenant_session),
):
    """Cruza manualmente todos los movimientos pendientes."""
    from app.modulos.contabilidad.cruce_service import cruzar_pendientes
    resultado = await cruzar_pendientes(db)
    return JSONResponse({"ok": True, **resultado})


@router.post("/banco/movimiento/{id}/ignorar")
async def cont_banco_ignorar(
    request: Request, id: int,
    db: AsyncSession = Depends(get_tenant_session),
):
    """Marca un movimiento como ignorado."""
    result = await db.execute(
        select(MovimientoBancario).where(MovimientoBancario.id == id))
    mov = result.scalar_one_or_none()
    if mov:
        mov.estado_cruce = "ignorado"
        await db.commit()
    return JSONResponse({"ok": True})
