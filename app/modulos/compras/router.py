from fastapi import APIRouter, Request, Depends, Query, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from decimal import Decimal
from datetime import date, datetime
from app.tenant import get_tenant_session
from app.modulos.compras.models import (
    OrdenCompra, OrdenCompraItem, Compra, CompraItem,
    CompraPago, NotaMercaderia, NotaMercaderiaItem
)
from app.modulos.compras.service import (
    generar_codigo_compra, generar_codigo_orden,
    registrar_kardex_compra, detectar_stock_negativo,
    leer_documento_con_vision,
)
from app.modulos.catalogo.models import Producto, ProductoPrecio
from app.modulos.config.models import (
    ConfigAlmacen, ConfigResponsable, ConfigIntegracion
)
import base64

router = APIRouter(prefix="/compras", tags=["compras"])
templates = Jinja2Templates(directory="templates")


def ctx(request: Request, **kwargs):
    return {
        "request": request,
        "nombre": getattr(request.state, "nombre", ""),
        "empresa_nombre": getattr(request.state, "empresa_nombre", ""),
        **kwargs
    }


# ── Dashboard ─────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def compras_dashboard(request: Request,
                             db: AsyncSession = Depends(get_tenant_session)):
    hoy = date.today()

    r_total = await db.execute(
        select(func.sum(Compra.total)).where(
            Compra.fecha_emision_doc == hoy,
            Compra.estado != "anulada",
        )
    )
    total_hoy = r_total.scalar() or 0

    r_por_aprobar = await db.execute(
        select(func.count(Compra.id)).where(Compra.estado == "por_aprobar"))
    por_aprobar = r_por_aprobar.scalar() or 0

    r_notas = await db.execute(
        select(func.count(NotaMercaderia.id)).where(
            NotaMercaderia.estado == "pendiente"))
    notas_pendientes = r_notas.scalar() or 0

    r_ultimas = await db.execute(
        select(Compra).order_by(Compra.created_at.desc()).limit(10))
    ultimas = r_ultimas.scalars().all()

    return templates.TemplateResponse("compras/dashboard.html", ctx(request,
        total_hoy=total_hoy,
        por_aprobar=por_aprobar,
        notas_pendientes=notas_pendientes,
        ultimas=ultimas,
        hoy=hoy,
    ))


# ── Lista de compras ──────────────────────────

@router.get("/lista", response_class=HTMLResponse)
async def compras_lista(
    request: Request,
    fecha_desde: str = Query(default=None),
    fecha_hasta: str = Query(default=None),
    estado: str = Query(default=""),
    db: AsyncSession = Depends(get_tenant_session),
):
    hoy = date.today()
    desde = date.fromisoformat(fecha_desde) if fecha_desde else hoy.replace(day=1)
    hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else hoy

    query = select(Compra).where(
        Compra.fecha_emision_doc >= desde,
        Compra.fecha_emision_doc <= hasta,
    )
    if estado:
        query = query.where(Compra.estado == estado)

    result = await db.execute(query.order_by(Compra.created_at.desc()))
    compras = result.scalars().all()

    total_periodo = sum(float(c.total) for c in compras if c.estado != "anulada")

    return templates.TemplateResponse("compras/lista.html", ctx(request,
        compras=compras,
        desde=desde, hasta=hasta,
        estado=estado,
        total_periodo=total_periodo,
    ))


# ── Nueva compra ─────────────────────────────

@router.get("/nueva", response_class=HTMLResponse)
async def compra_nueva_get(request: Request,
                            db: AsyncSession = Depends(get_tenant_session)):
    almacenes = (await db.execute(
        select(ConfigAlmacen).where(ConfigAlmacen.activo == True)
    )).scalars().all()

    responsables = (await db.execute(
        select(ConfigResponsable).where(ConfigResponsable.activo == True)
    )).scalars().all()

    return templates.TemplateResponse("compras/form.html", ctx(request,
        compra=None,
        almacenes=almacenes,
        responsables=responsables,
    ))


@router.post("/nueva")
async def compra_nueva_post(request: Request,
                             db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    codigo = await generar_codigo_compra(db)

    compra = Compra(
        codigo=codigo,
        nombre_proveedor=form.get("nombre_proveedor"),
        ruc_proveedor=form.get("ruc_proveedor") or None,
        tipo_doc_sunat=form.get("tipo_doc_sunat", "01"),
        serie_doc=form.get("serie_doc"),
        numero_doc=form.get("numero_doc"),
        fecha_emision_doc=date.fromisoformat(form.get("fecha_emision_doc",
                                                        str(date.today()))),
        id_almacen=int(form["id_almacen"]) if form.get("id_almacen") else None,
        moneda=form.get("moneda", "PEN"),
        tipo_cambio=Decimal(form.get("tipo_cambio") or "1"),
        nota=form.get("nota"),
        estado="por_aprobar",
        id_usuario=int(getattr(request.state, "user_id", 0) or 0),
    )
    db.add(compra)
    await db.commit()
    await db.refresh(compra)
    return RedirectResponse(url=f"/compras/{compra.id}", status_code=302)


# ── Ordenes de compra ────────────────────────

@router.get("/ordenes", response_class=HTMLResponse)
async def ordenes_lista(request: Request,
                         db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(OrdenCompra).order_by(OrdenCompra.created_at.desc()).limit(50))
    ordenes = result.scalars().all()
    return templates.TemplateResponse("compras/ordenes.html",
        ctx(request, ordenes=ordenes))


@router.post("/ordenes/nueva")
async def orden_nueva(request: Request,
                       db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    codigo = await generar_codigo_orden(db)
    orden = OrdenCompra(
        codigo=codigo,
        nombre_proveedor=data.get("nombre_proveedor"),
        ruc_proveedor=data.get("ruc_proveedor"),
        fecha_emision=date.today(),
        fecha_entrega_esperada=data.get("fecha_entrega"),
        id_almacen_destino=data.get("id_almacen"),
        nota=data.get("nota"),
        id_usuario=int(getattr(request.state, "user_id", 0) or 0),
    )
    db.add(orden)
    await db.commit()
    await db.refresh(orden)
    return JSONResponse({"id": orden.id, "codigo": orden.codigo})


# ── Notas de Mercaderia ──────────────────────

@router.get("/notas-mercaderia", response_class=HTMLResponse)
async def notas_mercaderia_lista(request: Request,
                                  db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(NotaMercaderia).options(
            selectinload(NotaMercaderia.items)
        ).order_by(NotaMercaderia.created_at.desc())
    )
    notas = result.scalars().all()

    return templates.TemplateResponse("compras/notas_mercaderia.html",
        ctx(request, notas=notas))


@router.get("/notas-mercaderia/{id}", response_class=HTMLResponse)
async def nota_mercaderia_detalle(request: Request, id: int,
                                   db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(NotaMercaderia).options(
            selectinload(NotaMercaderia.items)
        ).where(NotaMercaderia.id == id)
    )
    nota = result.scalar_one_or_none()
    if not nota:
        return HTMLResponse("No encontrado", status_code=404)

    compras = (await db.execute(
        select(Compra).where(Compra.estado != "anulada")
        .order_by(Compra.fecha_emision_doc.desc()).limit(20)
    )).scalars().all()

    return templates.TemplateResponse("compras/nota_mercaderia_detalle.html",
        ctx(request, nota=nota, compras=compras))


@router.post("/notas-mercaderia/{id}/regularizar")
async def nota_mercaderia_regularizar(request: Request, id: int,
                                       db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    result = await db.execute(
        select(NotaMercaderia).where(NotaMercaderia.id == id))
    nota = result.scalar_one_or_none()
    if not nota:
        return JSONResponse({"error": "No encontrado"}, status_code=404)

    nota.id_compra_regularizacion = data.get("id_compra")
    nota.estado = "regularizada"
    nota.fecha_cierre = date.today()
    await db.commit()
    return JSONResponse({"ok": True})


# ── Leer documento con Vision API ────────────

@router.post("/leer-documento")
async def leer_documento(
    request: Request,
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_tenant_session),
):
    r_integ = await db.execute(
        select(ConfigIntegracion).where(
            ConfigIntegracion.servicio == "openai",
            ConfigIntegracion.activo == True,
        )
    )
    integ = r_integ.scalar_one_or_none()

    if not integ or not integ.api_key:
        return JSONResponse({
            "error": "OpenAI no configurado. Ve a Configuracion > Integraciones."
        }, status_code=400)

    contenido = await archivo.read()
    imagen_b64 = base64.b64encode(contenido).decode()

    datos = await leer_documento_con_vision(imagen_b64, integ.api_key)
    return JSONResponse(datos)


# ── Detalle de compra (SIEMPRE al final) ─────

@router.get("/{id}", response_class=HTMLResponse)
async def compra_detalle(request: Request, id: int,
                          db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(Compra).options(
            selectinload(Compra.items),
            selectinload(Compra.pagos),
        ).where(Compra.id == id)
    )
    compra = result.scalar_one_or_none()
    if not compra:
        return HTMLResponse("No encontrado", status_code=404)

    almacenes = (await db.execute(
        select(ConfigAlmacen).where(ConfigAlmacen.activo == True)
    )).scalars().all()

    responsables = (await db.execute(
        select(ConfigResponsable).where(ConfigResponsable.activo == True)
    )).scalars().all()

    total_pagado = sum(float(p.monto) for p in compra.pagos)
    saldo = float(compra.total) - total_pagado

    return templates.TemplateResponse("compras/detalle.html", ctx(request,
        compra=compra,
        almacenes=almacenes,
        responsables=responsables,
        total_pagado=total_pagado,
        saldo=saldo,
    ))


@router.post("/{id}/item")
async def compra_agregar_item(request: Request, id: int,
                               db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()

    cantidad = Decimal(str(data.get("cantidad", 1)))
    precio = Decimal(str(data.get("precio_unitario", 0)))
    igv_tasa = Decimal("18")
    subtotal_bruto = cantidad * precio
    igv = round(subtotal_bruto * igv_tasa / (100 + igv_tasa), 2)
    subtotal = round(subtotal_bruto - igv, 2)

    item = CompraItem(
        id_compra=id,
        id_producto=data.get("id_producto"),
        codigo_producto=data.get("codigo_producto", ""),
        nombre_producto=data.get("nombre_producto", ""),
        unidad=data.get("unidad", "UND"),
        cantidad=cantidad,
        precio_unitario=precio,
        subtotal=subtotal,
        igv=igv,
        total=subtotal_bruto,
        costo_unitario_kardex=precio,
        lote=data.get("lote"),
        fecha_vencimiento=data.get("fecha_vencimiento") or None,
    )
    db.add(item)

    result = await db.execute(select(Compra).where(Compra.id == id))
    compra = result.scalar_one()
    await db.flush()

    r_items = await db.execute(
        select(CompraItem).where(CompraItem.id_compra == id))
    todos = r_items.scalars().all()

    compra.subtotal = sum(i.subtotal for i in todos)
    compra.igv = sum(i.igv for i in todos)
    compra.total = sum(i.total for i in todos)

    await db.commit()
    return JSONResponse({
        "item_id": item.id,
        "subtotal": float(compra.subtotal),
        "igv": float(compra.igv),
        "total": float(compra.total),
    })


@router.post("/{id}/aprobar")
async def compra_aprobar(request: Request, id: int,
                          db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    result = await db.execute(select(Compra).where(Compra.id == id))
    compra = result.scalar_one_or_none()
    if not compra:
        return JSONResponse({"error": "No encontrado"}, status_code=404)

    compra.estado = "aprobada"
    compra.id_aprobador = data.get("id_aprobador")
    compra.nombre_aprobador = data.get("nombre_aprobador", "")
    compra.fecha_aprobacion = datetime.now()
    compra.observacion_aprobacion = data.get("observacion", "")

    result2 = await db.execute(
        select(Compra).options(selectinload(Compra.items)).where(Compra.id == id))
    compra_con_items = result2.scalar_one()

    await registrar_kardex_compra(
        db, compra_con_items,
        int(getattr(request.state, "user_id", 0) or 0)
    )

    await db.commit()
    return JSONResponse({"ok": True, "estado": "aprobada"})


@router.post("/{id}/observar")
async def compra_observar(request: Request, id: int,
                           db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    result = await db.execute(select(Compra).where(Compra.id == id))
    compra = result.scalar_one_or_none()
    if not compra:
        return JSONResponse({"error": "No encontrado"}, status_code=404)

    compra.estado = "observada"
    compra.observacion_aprobacion = data.get("observacion", "")
    await db.commit()
    return JSONResponse({"ok": True, "estado": "observada"})
