from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from decimal import Decimal
from datetime import datetime, date
import json


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

from app.tenant import get_tenant_session
from app.modulos.ventas.models import Pedido, PedidoItem, CajaApertura
from app.modulos.ventas.service import (
    generar_codigo_pedido, obtener_caja_abierta,
    confirmar_pedido, calcular_item, calcular_totales_pedido,
    enviar_a_facturalo
)
from app.modulos.catalogo.models import (
    Producto, ProductoPrecio, CatClasificador1, StockActual
)
from app.modulos.config.models import (
    ConfigPuntoVenta, ConfigImpuestos, ConfigFacturacion,
    ConfigMedioCobro, ConfigPreferencias
)

router = APIRouter(prefix="/ventas", tags=["ventas"])
templates = Jinja2Templates(directory="templates")


def ctx(request: Request, **kwargs):
    return {
        "request": request,
        "nombre": getattr(request.state, "nombre", ""),
        "empresa_nombre": getattr(request.state, "empresa_nombre", ""),
        **kwargs
    }


# ── Dashboard de ventas ───────────────────────

@router.get("/", response_class=HTMLResponse)
async def ventas_dashboard(request: Request,
                            db: AsyncSession = Depends(get_tenant_session)):
    hoy = date.today()

    r_total = await db.execute(
        select(func.sum(Pedido.total)).where(
            Pedido.fecha == hoy,
            Pedido.estado.in_(["confirmado", "facturado"]),
            Pedido.anulado == False,
        )
    )
    total_hoy = r_total.scalar() or 0

    r_count = await db.execute(
        select(func.count(Pedido.id)).where(
            Pedido.fecha == hoy,
            Pedido.estado.in_(["confirmado", "facturado"]),
            Pedido.anulado == False,
        )
    )
    count_hoy = r_count.scalar() or 0

    r_ultimas = await db.execute(
        select(Pedido).where(Pedido.anulado == False)
        .order_by(Pedido.created_at.desc()).limit(10)
    )
    ultimas = r_ultimas.scalars().all()

    r_pvs = await db.execute(
        select(ConfigPuntoVenta).where(ConfigPuntoVenta.activo == True))
    pvs = r_pvs.scalars().all()

    return templates.TemplateResponse("ventas/dashboard.html", ctx(request,
        total_hoy=total_hoy,
        count_hoy=count_hoy,
        ultimas=ultimas,
        pvs=pvs,
        hoy=hoy,
    ))


# ── Apertura de caja ──────────────────────────

@router.get("/caja/abrir", response_class=HTMLResponse)
async def caja_abrir_get(request: Request,
                          db: AsyncSession = Depends(get_tenant_session)):
    r_pvs = await db.execute(
        select(ConfigPuntoVenta).where(ConfigPuntoVenta.activo == True))
    pvs = r_pvs.scalars().all()
    return templates.TemplateResponse("ventas/caja_abrir.html",
        ctx(request, pvs=pvs))


@router.post("/caja/abrir")
async def caja_abrir_post(request: Request,
                           db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    id_pv = int(form.get("id_punto_venta", 0))

    caja_existente = await obtener_caja_abierta(
        db, id_pv, int(getattr(request.state, "user_id", 0) or 0))
    if caja_existente:
        return templates.TemplateResponse("ventas/caja_abrir.html", ctx(request,
            pvs=[], error="Ya hay una caja abierta para este punto de venta"))

    caja = CajaApertura(
        id_punto_venta=id_pv,
        id_usuario=int(getattr(request.state, "user_id", 0) or 0),
        fecha=date.today(),
        monto_inicial=Decimal(form.get("monto_inicial", "0")),
        nota_apertura=form.get("nota", ""),
    )
    db.add(caja)
    await db.commit()
    return RedirectResponse(url=f"/ventas/pos/{id_pv}", status_code=302)


# ── Cierre de caja ────────────────────────────

@router.get("/caja/{id}/cerrar", response_class=HTMLResponse)
async def caja_cerrar_get(request: Request, id: int,
                           db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(CajaApertura).where(CajaApertura.id == id))
    caja = result.scalar_one_or_none()
    if not caja:
        return RedirectResponse(url="/ventas/", status_code=302)

    r_total = await db.execute(
        select(func.sum(Pedido.total)).where(
            Pedido.id_caja_apertura == id,
            Pedido.anulado == False,
            Pedido.estado.in_(["confirmado", "facturado"]),
        )
    )
    total_ventas = r_total.scalar() or 0
    total_calculado = (caja.monto_inicial or 0) + total_ventas

    return templates.TemplateResponse("ventas/caja_cerrar.html", ctx(request,
        caja=caja,
        total_ventas=total_ventas,
        total_calculado=total_calculado,
    ))


@router.post("/caja/{id}/cerrar")
async def caja_cerrar_post(request: Request, id: int,
                            db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    result = await db.execute(select(CajaApertura).where(CajaApertura.id == id))
    caja = result.scalar_one_or_none()
    if not caja:
        return RedirectResponse(url="/ventas/", status_code=302)

    monto_declarado = Decimal(form.get("monto_declarado", "0"))
    caja.hora_cierre = datetime.now()
    caja.monto_cierre_declarado = monto_declarado
    caja.diferencia = monto_declarado - (caja.monto_cierre_calculado or 0)
    caja.nota_cierre = form.get("nota", "")
    caja.estado = "cerrada"
    await db.commit()
    return RedirectResponse(url="/ventas/", status_code=302)


# ── POS — Pantalla de pedido ──────────────────

@router.get("/pos/{id_pv}", response_class=HTMLResponse)
async def pos_pantalla(request: Request, id_pv: int,
                        db: AsyncSession = Depends(get_tenant_session)):
    caja = await obtener_caja_abierta(
        db, id_pv, int(getattr(request.state, "user_id", 0) or 0))

    r_pv = await db.execute(
        select(ConfigPuntoVenta).where(ConfigPuntoVenta.id == id_pv))
    pv = r_pv.scalar_one_or_none()

    r_clas = await db.execute(
        select(CatClasificador1).where(CatClasificador1.activo == True)
        .order_by(CatClasificador1.orden))
    categorias = r_clas.scalars().all()

    r_imp = await db.execute(select(ConfigImpuestos).limit(1))
    impuestos = r_imp.scalar_one_or_none()
    igv_tasa = float(impuestos.igv) if impuestos else 18.0

    r_medios = await db.execute(
        select(ConfigMedioCobro).where(ConfigMedioCobro.activo == True))
    medios_cobro = r_medios.scalars().all()

    return templates.TemplateResponse("ventas/pos.html", ctx(request,
        pv=pv,
        caja=caja,
        categorias=categorias,
        igv_tasa=igv_tasa,
        medios_cobro=medios_cobro,
        id_pv=id_pv,
    ))


# ── POS — Buscar productos (HTMX + scanner) ──

@router.get("/pos/productos/buscar", response_class=HTMLResponse)
async def pos_buscar_productos(
    request: Request,
    q: str = Query(default=""),
    clas1: int = Query(default=None),
    db: AsyncSession = Depends(get_tenant_session),
):
    from sqlalchemy import or_
    from app.modulos.catalogo.models import ProductoBarra

    schema = getattr(request.state, "tenant_schema", "NO_SCHEMA")
    print(f"[POS BUSCAR] schema={schema}, q={q}")

    if not q and not clas1:
        return HTMLResponse("")

    query = select(Producto).options(
        selectinload(Producto.unidad),
        selectinload(Producto.precios),
    ).where(Producto.activo == True)

    if q:
        query = query.outerjoin(
            ProductoBarra, ProductoBarra.id_producto == Producto.id
        ).where(
            or_(
                Producto.nombre.ilike(f"%{q}%"),
                Producto.codigo.ilike(f"%{q}%"),
                ProductoBarra.codigo == q,
            )
        ).distinct()

    if clas1:
        query = query.where(Producto.id_clas1 == clas1)

    result = await db.execute(query.limit(50))
    productos_list = result.scalars().all()
    print(f"[POS BUSCAR] encontrados={len(productos_list)}")

    productos = []
    for prod in productos_list:
        precios_venta = [p for p in prod.precios if p.activo and p.es_precio_venta]
        productos.append({"producto": prod, "precios": precios_venta})

    return templates.TemplateResponse("ventas/partials/productos_pos.html",
        ctx(request, productos=productos))


@router.get("/pos/categoria/{id_clas1}", response_class=HTMLResponse)
async def pos_productos_categoria(
    request: Request, id_clas1: int,
    db: AsyncSession = Depends(get_tenant_session),
):
    result = await db.execute(
        select(Producto).where(
            Producto.id_clas1 == id_clas1,
            Producto.activo == True,
        ).order_by(Producto.nombre).limit(100)
    )
    productos_raw = result.scalars().all()

    productos = []
    for p in productos_raw:
        r_precio = await db.execute(
            select(ProductoPrecio).where(
                ProductoPrecio.id_producto == p.id,
                ProductoPrecio.activo == True,
                ProductoPrecio.es_precio_venta == True,
            ).order_by(ProductoPrecio.id).limit(1)
        )
        precio = r_precio.scalar_one_or_none()
        productos.append({"producto": p, "precios": [precio] if precio else []})

    return templates.TemplateResponse("ventas/partials/productos_cards.html",
        ctx(request, productos=productos))


# ── Crear pedido ──────────────────────────────

@router.post("/pedido/nuevo")
async def pedido_nuevo(request: Request,
                        db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    id_pv = data.get("id_punto_venta", 1)

    caja = await obtener_caja_abierta(
        db, id_pv, int(getattr(request.state, "user_id", 0) or 0))

    codigo = await generar_codigo_pedido(db)
    pedido = Pedido(
        codigo=codigo,
        id_punto_venta=id_pv,
        id_caja_apertura=caja.id if caja else None,
        id_usuario=int(getattr(request.state, "user_id", 0) or 0),
        estado="borrador",
        fecha=date.today(),
    )
    db.add(pedido)
    await db.commit()
    await db.refresh(pedido)
    return JSONResponse({"id": pedido.id, "codigo": pedido.codigo})


# ── Agregar item al pedido ────────────────────

@router.post("/pedido/{id}/item")
async def pedido_agregar_item(
    request: Request, id: int,
    db: AsyncSession = Depends(get_tenant_session),
):
    data = await request.json()

    r_imp = await db.execute(select(ConfigImpuestos).limit(1))
    imp = r_imp.scalar_one_or_none()
    igv_tasa = Decimal(str(imp.igv)) if imp else Decimal("18")

    cantidad = Decimal(str(data.get("cantidad", 1)))
    precio = Decimal(str(data.get("precio_unitario", 0)))
    afecto_igv = data.get("afecto_igv", True)

    calc = calcular_item(cantidad, precio,
                          afecto_igv=afecto_igv, igv_tasa=igv_tasa)

    item = PedidoItem(
        id_pedido=id,
        id_producto=data.get("id_producto"),
        id_precio=data.get("id_precio"),
        codigo_producto=data.get("codigo_producto", ""),
        nombre_producto=data.get("nombre_producto", ""),
        unidad=data.get("unidad", "UND"),
        equivalente=data.get("equivalente", 1),
        cantidad=cantidad,
        precio_unitario=precio,
        subtotal=calc["subtotal"],
        igv=calc["igv"],
        total=calc["total"],
        afecto_igv=afecto_igv,
    )
    db.add(item)

    result = await db.execute(select(Pedido).where(Pedido.id == id))
    pedido = result.scalar_one()
    await db.flush()

    r_items = await db.execute(
        select(PedidoItem).where(PedidoItem.id_pedido == id))
    todos_items = r_items.scalars().all()
    items_dict = [{"subtotal": i.subtotal, "igv": i.igv, "total": i.total}
                  for i in todos_items]
    totales = calcular_totales_pedido(items_dict)

    pedido.subtotal = totales["subtotal"]
    pedido.igv = totales["igv"]
    pedido.total = totales["total"]

    await db.commit()
    await db.refresh(item)

    return JSONResponse(
        content=json.loads(
            json.dumps({
                "item_id": item.id,
                "totales": totales,
                "items_count": len(todos_items),
            }, cls=DecimalEncoder)
        )
    )


# ── Eliminar item del pedido ──────────────────

@router.delete("/pedido/{id_pedido}/item/{id_item}")
async def pedido_eliminar_item(
    request: Request, id_pedido: int, id_item: int,
    db: AsyncSession = Depends(get_tenant_session),
):
    result = await db.execute(
        select(PedidoItem).where(
            PedidoItem.id == id_item,
            PedidoItem.id_pedido == id_pedido,
        )
    )
    item = result.scalar_one_or_none()
    if item:
        await db.delete(item)

    result = await db.execute(select(Pedido).where(Pedido.id == id_pedido))
    pedido = result.scalar_one()
    await db.flush()

    r_items = await db.execute(
        select(PedidoItem).where(PedidoItem.id_pedido == id_pedido))
    todos_items = r_items.scalars().all()
    items_dict = [{"subtotal": i.subtotal, "igv": i.igv, "total": i.total}
                  for i in todos_items]
    totales = calcular_totales_pedido(items_dict)

    pedido.subtotal = totales["subtotal"]
    pedido.igv = totales["igv"]
    pedido.total = totales["total"]
    await db.commit()

    return JSONResponse({"totales": totales, "items_count": len(todos_items)})


# ── Confirmar y cobrar pedido ─────────────────

@router.post("/pedido/{id}/confirmar")
async def pedido_confirmar(
    request: Request, id: int,
    db: AsyncSession = Depends(get_tenant_session),
):
    data = await request.json()

    result = await db.execute(
        select(Pedido).where(Pedido.id == id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        return JSONResponse({"error": "Pedido no encontrado"}, status_code=404)

    pedido.ruc_dni = data.get("ruc_dni", "")
    pedido.nombre_cliente = data.get("nombre_cliente", "CLIENTES VARIOS")
    pedido.direccion_cliente = data.get("direccion_cliente", "")
    pedido.tipo_comprobante = data.get("tipo_comprobante", "03")
    pedido.medio_pago = data.get("medio_pago", "efectivo")
    pedido.monto_pagado = Decimal(str(data.get("monto_pagado", pedido.total)))
    pedido.vuelto = pedido.monto_pagado - pedido.total

    r_pv = await db.execute(
        select(ConfigPuntoVenta).where(
            ConfigPuntoVenta.id == pedido.id_punto_venta))
    pv = r_pv.scalar_one_or_none()
    id_almacen = pv.id_almacen if pv else 1

    await confirmar_pedido(db, pedido, id_almacen,
                            int(getattr(request.state, "user_id", 0) or 0))

    if data.get("emitir_cpe") and pedido.tipo_comprobante in ["01", "03"]:
        r_fact = await db.execute(select(ConfigFacturacion).limit(1))
        fact = r_fact.scalar_one_or_none()
        if fact and fact.activo and fact.api_url:
            resp = await enviar_a_facturalo(pedido, fact.api_url, fact.api_key)
            pedido.id_comprobante_facturalo = resp.get("id")
            pedido.estado_cpe = resp.get("estado", "pendiente")
            if resp.get("serie"):
                pedido.serie_comprobante = resp["serie"]
            if resp.get("numero"):
                pedido.numero_comprobante = resp["numero"]
            pedido.estado = "facturado"
        else:
            pedido.estado = "confirmado"
    else:
        pedido.estado = "confirmado"

    await db.commit()

    return JSONResponse({
        "ok": True,
        "pedido_id": pedido.id,
        "codigo": pedido.codigo,
        "total": float(pedido.total),
        "vuelto": float(pedido.vuelto),
        "estado": pedido.estado,
        "serie": pedido.serie_comprobante,
        "numero": pedido.numero_comprobante,
    })


# ── Lista de pedidos ──────────────────────────

@router.get("/pedidos", response_class=HTMLResponse)
async def pedidos_lista(
    request: Request,
    fecha: str = Query(default=None),
    estado: str = Query(default=""),
    db: AsyncSession = Depends(get_tenant_session),
):
    fecha_obj = date.fromisoformat(fecha) if fecha else date.today()

    query = select(Pedido).where(
        Pedido.fecha == fecha_obj,
        Pedido.anulado == False,
    )
    if estado:
        query = query.where(Pedido.estado == estado)

    result = await db.execute(query.order_by(Pedido.created_at.desc()))
    pedidos = result.scalars().all()

    total_dia = sum(float(p.total) for p in pedidos
                    if p.estado in ["confirmado", "facturado"])

    return templates.TemplateResponse("ventas/pedidos_lista.html", ctx(request,
        pedidos=pedidos,
        fecha=fecha_obj,
        estado=estado,
        total_dia=total_dia,
    ))


# ── Detalle de pedido ─────────────────────────

@router.get("/pedidos/{id}", response_class=HTMLResponse)
async def pedido_detalle(request: Request, id: int,
                          db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(Pedido).where(Pedido.id == id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        return HTMLResponse("No encontrado", status_code=404)

    r_items = await db.execute(
        select(PedidoItem).where(PedidoItem.id_pedido == id))
    items = r_items.scalars().all()

    return templates.TemplateResponse("ventas/pedido_detalle.html",
        ctx(request, pedido=pedido, items=items))


# ── pagoOK: Validacion de pagos por foto ─────────────────────────────

from app.modulos.contabilidad.ocr_service import extraer_datos_comprobante
from app.modulos.contabilidad.pagook_service import validar_pago_foto


@router.get("/pos/{id_pv}/validar-pago", response_class=HTMLResponse)
async def pagook_get(
    request: Request,
    id_pv: int,
    pedido_id: int = Query(default=None),
    monto: str = Query(default=None),
    db: AsyncSession = Depends(get_tenant_session),
):
    """Pantalla de validacion de pago Yape/Plin con foto."""
    return templates.TemplateResponse("ventas/pagook.html", ctx(request,
        id_punto_venta=id_pv,
        pedido_id=pedido_id,
        monto_esperado=monto or "0",
    ))


@router.post("/pos/validar-pago/foto")
async def pagook_procesar_foto(
    request: Request,
    db: AsyncSession = Depends(get_tenant_session),
):
    """Recibe foto del comprobante, ejecuta OCR y valida el pago."""
    form = await request.form()
    foto = form.get("foto")
    id_pedido = int(form.get("pedido_id") or 0) or None
    id_pv = int(form.get("id_punto_venta") or 0) or None
    monto_esperado = form.get("monto_esperado", "0")
    id_usuario = int(getattr(request.state, "user_id", 0) or 0)

    if not foto:
        return JSONResponse({"ok": False, "error": "Sin foto"}, status_code=400)

    foto_bytes = await foto.read()

    import uuid
    from pathlib import Path
    foto_dir = Path("app/static/pagook_fotos")
    foto_dir.mkdir(parents=True, exist_ok=True)
    foto_nombre = f"{uuid.uuid4().hex}.jpg"
    foto_path = foto_dir / foto_nombre
    foto_path.write_bytes(foto_bytes)
    foto_url = f"/static/pagook_fotos/{foto_nombre}"

    ocr_result = await extraer_datos_comprobante(foto_bytes)
    print(f"[pagoOK] OCR: {ocr_result}")

    monto_validar = ocr_result.get("monto")
    if not monto_validar and monto_esperado:
        try:
            monto_validar = Decimal(monto_esperado)
        except Exception:
            pass

    resultado = await validar_pago_foto(
        db=db,
        numero_operacion=ocr_result.get("numero_operacion"),
        monto=monto_validar,
        banco=ocr_result.get("banco"),
        id_pedido=id_pedido,
        id_punto_venta=id_pv,
        id_usuario=id_usuario,
        foto_url=foto_url,
        texto_ocr=ocr_result.get("texto_completo", "")[:500],
    )

    return JSONResponse(resultado)


@router.post("/pos/validar-pago/manual")
async def pagook_manual(
    request: Request,
    db: AsyncSession = Depends(get_tenant_session),
):
    """Validacion manual ingresando N de operacion a mano."""
    data = await request.json()
    id_usuario = int(getattr(request.state, "user_id", 0) or 0)

    resultado = await validar_pago_foto(
        db=db,
        numero_operacion=data.get("numero_operacion"),
        monto=Decimal(str(data.get("monto", "0"))) if data.get("monto") else None,
        banco=data.get("banco"),
        id_pedido=data.get("pedido_id"),
        id_punto_venta=data.get("id_punto_venta"),
        id_usuario=id_usuario,
    )
    return JSONResponse(resultado)
