from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from decimal import Decimal
from datetime import date, datetime
from app.tenant import get_tenant_session
from app.modulos.inventario.models import (
    AjusteStock, AjusteStockItem, Transferencia, TransferenciaItem,
    TomaInventario, TomaInventarioItem, ActivoFijo, InventarioActivo,
    InventarioActivoItem, PedidoSustento, PedidoSustentoItem,
)
from app.modulos.inventario.service import (
    generar_codigo, registrar_kardex_ajuste,
    registrar_kardex_transferencia, finalizar_toma_inventario,
)
from app.modulos.catalogo.models import Producto, StockActual, Kardex, CatClasificador1
from app.modulos.config.models import ConfigAlmacen, ConfigResponsable

router = APIRouter(prefix="/inventario", tags=["inventario"])
templates = Jinja2Templates(directory="templates")


def ctx(request: Request, **kwargs):
    return {
        "request": request,
        "nombre": getattr(request.state, "nombre", ""),
        "empresa_nombre": getattr(request.state, "empresa_nombre", ""),
        **kwargs
    }


@router.get("/", response_class=HTMLResponse)
async def inventario_dashboard(request: Request,
                                db: AsyncSession = Depends(get_tenant_session)):
    r_total_prods = await db.execute(
        select(func.count(Producto.id)).where(
            Producto.activo == True, Producto.inventariado == True))
    total_productos = r_total_prods.scalar() or 0

    r_stock_negativo = await db.execute(
        select(func.count(StockActual.id)).where(StockActual.cantidad < 0))
    stock_negativo = r_stock_negativo.scalar() or 0

    r_ajustes_pendientes = await db.execute(
        select(func.count(AjusteStock.id)).where(AjusteStock.estado == "pendiente"))
    ajustes_pendientes = r_ajustes_pendientes.scalar() or 0

    r_sustento_pendientes = await db.execute(
        select(func.count(PedidoSustento.id)).where(
            PedidoSustento.estado.in_(["pendiente", "enviado"])))
    sustento_pendientes = r_sustento_pendientes.scalar() or 0

    hoy = date.today()
    almacenes = (await db.execute(
        select(ConfigAlmacen).where(ConfigAlmacen.activo == True)
    )).scalars().all()

    return templates.TemplateResponse("inventario/dashboard.html", ctx(request,
        total_productos=total_productos, stock_negativo=stock_negativo,
        ajustes_pendientes=ajustes_pendientes, sustento_pendientes=sustento_pendientes,
        almacenes=almacenes, hoy=hoy,
    ))


@router.get("/stock", response_class=HTMLResponse)
async def inventario_stock(
    request: Request, id_almacen: int = Query(default=None),
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_tenant_session),
):
    from sqlalchemy import or_
    almacenes = (await db.execute(
        select(ConfigAlmacen).where(ConfigAlmacen.activo == True)
    )).scalars().all()

    query = select(StockActual, Producto).join(
        Producto, Producto.id == StockActual.id_producto
    ).where(Producto.activo == True)

    if id_almacen:
        query = query.where(StockActual.id_almacen == id_almacen)
    if q:
        query = query.where(
            or_(Producto.nombre.ilike(f"%{q}%"), Producto.codigo.ilike(f"%{q}%")))

    result = await db.execute(query.order_by(Producto.nombre).limit(200))
    rows = result.all()

    stocks = [{"stock": s, "producto": p} for s, p in rows]
    valor_total = sum(float(s.costo_total or 0) for s, p in rows)

    return templates.TemplateResponse("inventario/stock.html", ctx(request,
        stocks=stocks, almacenes=almacenes, id_almacen_sel=id_almacen,
        q=q, valor_total=valor_total,
    ))


@router.get("/corte", response_class=HTMLResponse)
async def inventario_corte(
    request: Request,
    fecha: str = Query(default=None),
    id_almacen: int = Query(default=None),
    db: AsyncSession = Depends(get_tenant_session),
):
    from app.modulos.catalogo.kardex import corte_inventario

    fecha_corte = date.fromisoformat(fecha) if fecha else date.today()
    resultados = []

    if id_almacen:
        resultados = await corte_inventario(db, id_almacen, fecha_corte)

    almacenes = (await db.execute(
        select(ConfigAlmacen).where(ConfigAlmacen.activo == True)
    )).scalars().all()

    return templates.TemplateResponse("inventario/corte.html", ctx(request,
        fecha_corte=fecha_corte,
        id_almacen=id_almacen,
        almacenes=almacenes,
        resultados=resultados,
        total_valor=sum(r["valor_total"] for r in resultados),
    ))


@router.get("/kardex/{id_producto}", response_class=HTMLResponse)
async def inventario_kardex(
    request: Request, id_producto: int,
    id_almacen: int = Query(default=None),
    fecha_desde: str = Query(default=None),
    fecha_hasta: str = Query(default=None),
    db: AsyncSession = Depends(get_tenant_session),
):
    result_prod = await db.execute(select(Producto).where(Producto.id == id_producto))
    producto = result_prod.scalar_one_or_none()

    hoy = date.today()
    desde = date.fromisoformat(fecha_desde) if fecha_desde else hoy.replace(day=1)
    hasta = date.fromisoformat(fecha_hasta) if fecha_hasta else hoy

    query = select(Kardex).where(
        Kardex.id_producto == id_producto,
        Kardex.fecha >= desde, Kardex.fecha <= hasta,
    )
    if id_almacen:
        query = query.where(Kardex.id_almacen == id_almacen)

    result = await db.execute(query.order_by(Kardex.fecha, Kardex.id))
    movimientos = result.scalars().all()

    almacenes = (await db.execute(
        select(ConfigAlmacen).where(ConfigAlmacen.activo == True)
    )).scalars().all()

    return templates.TemplateResponse("inventario/kardex.html", ctx(request,
        producto=producto, movimientos=movimientos, almacenes=almacenes,
        id_almacen_sel=id_almacen, desde=desde, hasta=hasta,
    ))


@router.get("/ajustes", response_class=HTMLResponse)
async def ajustes_lista(request: Request,
                         db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(AjusteStock).order_by(AjusteStock.created_at.desc()).limit(50))
    ajustes = result.scalars().all()
    ajustes_pendientes = [a for a in ajustes if a.estado == "pendiente"]
    return templates.TemplateResponse("inventario/ajustes.html", ctx(request,
        ajustes=ajustes, ajustes_pendientes=len(ajustes_pendientes),
    ))


@router.get("/ajustes/nuevo", response_class=HTMLResponse)
async def ajuste_nuevo_get(request: Request,
                            db: AsyncSession = Depends(get_tenant_session)):
    almacenes = (await db.execute(
        select(ConfigAlmacen).where(ConfigAlmacen.activo == True)
    )).scalars().all()
    responsables = (await db.execute(
        select(ConfigResponsable).where(ConfigResponsable.activo == True)
    )).scalars().all()
    return templates.TemplateResponse("inventario/ajuste_form.html", ctx(request,
        almacenes=almacenes, responsables=responsables))


@router.post("/ajustes/nuevo")
async def ajuste_nuevo_post(request: Request,
                             db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    codigo = await generar_codigo(db, "AJ", "inv_ajustes")
    ajuste = AjusteStock(
        codigo=codigo, id_almacen=int(form["id_almacen"]),
        fecha=date.fromisoformat(form.get("fecha", str(date.today()))),
        tipo=form.get("tipo", "INGRESO"), motivo=form.get("motivo", "otro"),
        sustento=form.get("sustento", ""), estado="pendiente",
        id_usuario=int(getattr(request.state, "user_id", 0) or 0),
    )
    db.add(ajuste)
    await db.commit()
    await db.refresh(ajuste)
    return RedirectResponse(url=f"/inventario/ajustes/{ajuste.id}", status_code=302)


@router.get("/ajustes/{id}", response_class=HTMLResponse)
async def ajuste_detalle(request: Request, id: int,
                          db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(AjusteStock).options(selectinload(AjusteStock.items)).where(AjusteStock.id == id))
    ajuste = result.scalar_one_or_none()
    if not ajuste:
        return HTMLResponse("No encontrado", status_code=404)
    responsables = (await db.execute(
        select(ConfigResponsable).where(ConfigResponsable.activo == True)
    )).scalars().all()
    return templates.TemplateResponse("inventario/ajuste_detalle.html", ctx(request,
        ajuste=ajuste, responsables=responsables))


@router.post("/ajustes/{id}/item")
async def ajuste_agregar_item(request: Request, id: int,
                               db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    r_stock = await db.execute(
        select(StockActual).where(
            StockActual.id_producto == data.get("id_producto"),
            StockActual.id_almacen == data.get("id_almacen"),
        ))
    stock = r_stock.scalar_one_or_none()
    cantidad_sistema = float(stock.cantidad) if stock else 0

    item = AjusteStockItem(
        id_ajuste=id, id_producto=data.get("id_producto"),
        codigo_producto=data.get("codigo_producto", ""),
        nombre_producto=data.get("nombre_producto", ""),
        unidad=data.get("unidad", "UND"), cantidad_sistema=cantidad_sistema,
        cantidad_ajuste=Decimal(str(data.get("cantidad", 0))),
        costo_unitario=Decimal(str(data.get("costo_unitario", 0))),
        nota=data.get("nota", ""),
    )
    db.add(item)
    await db.commit()
    return JSONResponse({"ok": True, "item_id": item.id, "cantidad_sistema": cantidad_sistema})


@router.post("/ajustes/{id}/aprobar")
async def ajuste_aprobar(request: Request, id: int,
                          db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    result = await db.execute(
        select(AjusteStock).options(selectinload(AjusteStock.items)).where(AjusteStock.id == id))
    ajuste = result.scalar_one_or_none()
    if not ajuste:
        return JSONResponse({"error": "No encontrado"}, status_code=404)

    ajuste.estado = "aprobado"
    ajuste.id_aprobador = data.get("id_aprobador")
    ajuste.nombre_aprobador = data.get("nombre_aprobador", "")
    ajuste.fecha_aprobacion = datetime.now()
    ajuste.observacion_aprobacion = data.get("observacion", "")

    await registrar_kardex_ajuste(db, ajuste, int(getattr(request.state, "user_id", 0) or 0))
    await db.commit()
    return JSONResponse({"ok": True})


@router.get("/transferencias", response_class=HTMLResponse)
async def transferencias_lista(request: Request,
                                db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(Transferencia).order_by(Transferencia.created_at.desc()).limit(50))
    transferencias = result.scalars().all()
    almacenes = (await db.execute(
        select(ConfigAlmacen).where(ConfigAlmacen.activo == True)
    )).scalars().all()
    return templates.TemplateResponse("inventario/transferencias.html", ctx(request,
        transferencias=transferencias, almacenes=almacenes))


@router.post("/transferencias/nueva")
async def transferencia_nueva(request: Request,
                               db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    codigo = await generar_codigo(db, "TRF", "inv_transferencias")
    trf = Transferencia(
        codigo=codigo,
        id_almacen_origen=int(data["id_almacen_origen"]),
        id_almacen_destino=int(data["id_almacen_destino"]),
        fecha=date.today(), motivo=data.get("motivo", ""),
        estado="pendiente",
        id_usuario_envia=int(getattr(request.state, "user_id", 0) or 0),
        id_usuario=int(getattr(request.state, "user_id", 0) or 0),
    )
    db.add(trf)
    await db.commit()
    await db.refresh(trf)
    return JSONResponse({"id": trf.id, "codigo": trf.codigo})


@router.post("/transferencias/{id}/enviar")
async def transferencia_enviar(request: Request, id: int,
                                db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(Transferencia).options(selectinload(Transferencia.items)).where(Transferencia.id == id))
    trf = result.scalar_one_or_none()
    if not trf:
        return JSONResponse({"error": "No encontrado"}, status_code=404)
    trf.estado = "en_transito"
    trf.fecha_envio = datetime.now()
    await registrar_kardex_transferencia(db, trf, int(getattr(request.state, "user_id", 0) or 0))
    await db.commit()
    return JSONResponse({"ok": True, "estado": "en_transito"})


@router.get("/tomas", response_class=HTMLResponse)
async def tomas_lista(request: Request,
                       db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(TomaInventario).order_by(TomaInventario.created_at.desc()).limit(20))
    tomas = result.scalars().all()
    almacenes = (await db.execute(
        select(ConfigAlmacen).where(ConfigAlmacen.activo == True)
    )).scalars().all()
    return templates.TemplateResponse("inventario/tomas.html", ctx(request,
        tomas=tomas, almacenes=almacenes))


@router.post("/tomas/nueva")
async def toma_nueva(request: Request,
                      db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    codigo = await generar_codigo(db, "TI", "inv_tomas")
    id_almacen = int(data["id_almacen"])

    toma = TomaInventario(
        codigo=codigo, nombre=data.get("nombre", f"Toma {codigo}"),
        id_almacen=id_almacen, tipo=data.get("tipo", "total"),
        id_usuario=int(getattr(request.state, "user_id", 0) or 0),
    )
    db.add(toma)
    await db.flush()

    query = select(StockActual, Producto).join(
        Producto, Producto.id == StockActual.id_producto
    ).where(StockActual.id_almacen == id_almacen, Producto.activo == True, Producto.inventariado == True)

    if data.get("id_clas1"):
        query = query.where(Producto.id_clasificador1 == int(data["id_clas1"]))

    result = await db.execute(query.order_by(Producto.nombre))
    rows = result.all()

    for stock, prod in rows:
        item = TomaInventarioItem(
            id_toma=toma.id, id_producto=prod.id,
            codigo_producto=prod.codigo or "", nombre_producto=prod.nombre,
            unidad="UND", cantidad_sistema=stock.cantidad,
            costo_unitario=stock.costo_promedio or 0,
        )
        db.add(item)

    toma.total_items_contados = len(rows)
    await db.commit()
    await db.refresh(toma)
    return JSONResponse({"id": toma.id, "codigo": toma.codigo, "total_items": len(rows)})


@router.get("/tomas/{id}", response_class=HTMLResponse)
async def toma_detalle(request: Request, id: int,
                        db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(TomaInventario).options(selectinload(TomaInventario.items)).where(TomaInventario.id == id))
    toma = result.scalar_one_or_none()
    if not toma:
        return HTMLResponse("No encontrado", status_code=404)
    contados = sum(1 for i in toma.items if i.cantidad_contada is not None)
    con_diferencia = sum(1 for i in toma.items if i.cantidad_contada is not None and i.diferencia != 0)
    return templates.TemplateResponse("inventario/toma_detalle.html", ctx(request,
        toma=toma, contados=contados, con_diferencia=con_diferencia,
    ))


@router.post("/tomas/{id}/item/{id_item}/contar")
async def toma_registrar_conteo(
    request: Request, id: int, id_item: int,
    db: AsyncSession = Depends(get_tenant_session),
):
    data = await request.json()
    result = await db.execute(
        select(TomaInventarioItem).where(TomaInventarioItem.id == id_item, TomaInventarioItem.id_toma == id))
    item = result.scalar_one_or_none()
    if not item:
        return JSONResponse({"error": "No encontrado"}, status_code=404)

    cantidad_contada = Decimal(str(data.get("cantidad_contada", 0)))
    item.cantidad_contada = cantidad_contada
    item.diferencia = cantidad_contada - (item.cantidad_sistema or 0)
    item.valor_diferencia = item.diferencia * (item.costo_unitario or 0)
    item.contado_por = data.get("contado_por", "")
    item.fecha_conteo = datetime.now()
    item.nota = data.get("nota", "")
    await db.commit()
    return JSONResponse({"ok": True, "diferencia": float(item.diferencia), "valor_diferencia": float(item.valor_diferencia)})


@router.post("/tomas/{id}/finalizar")
async def toma_finalizar(request: Request, id: int,
                          db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(TomaInventario).options(selectinload(TomaInventario.items)).where(TomaInventario.id == id))
    toma = result.scalar_one_or_none()
    if not toma:
        return JSONResponse({"error": "No encontrado"}, status_code=404)
    ajuste = await finalizar_toma_inventario(db, toma, int(getattr(request.state, "user_id", 0) or 0))
    await db.commit()
    return JSONResponse({"ok": True, "ajuste_id": ajuste.id if ajuste else None,
        "items_con_diferencia": toma.items_con_diferencia,
        "valor_diferencia": float(toma.valor_diferencia_total),
    })


@router.get("/activos", response_class=HTMLResponse)
async def activos_lista(request: Request,
                         db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(ActivoFijo).where(ActivoFijo.activo == True).order_by(ActivoFijo.nombre))
    activos = result.scalars().all()
    return templates.TemplateResponse("inventario/activos.html", ctx(request, activos=activos))


@router.get("/activos/nuevo", response_class=HTMLResponse)
async def activo_nuevo_get(request: Request,
                            db: AsyncSession = Depends(get_tenant_session)):
    almacenes = (await db.execute(
        select(ConfigAlmacen).where(ConfigAlmacen.activo == True)
    )).scalars().all()
    responsables = (await db.execute(
        select(ConfigResponsable).where(ConfigResponsable.activo == True)
    )).scalars().all()
    return templates.TemplateResponse("inventario/activo_form.html", ctx(request,
        activo=None, almacenes=almacenes, responsables=responsables))


@router.post("/activos/nuevo")
async def activo_nuevo_post(request: Request,
                             db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    result = await db.execute(select(func.count(ActivoFijo.id)))
    n = result.scalar() + 1
    codigo = f"AF-{n:04d}"

    activo = ActivoFijo(
        codigo=codigo, nombre=form.get("nombre"),
        descripcion=form.get("descripcion"), categoria=form.get("categoria"),
        marca=form.get("marca"), modelo=form.get("modelo"),
        serie=form.get("serie"), color=form.get("color"),
        id_almacen=int(form["id_almacen"]) if form.get("id_almacen") else None,
        ubicacion_descripcion=form.get("ubicacion_descripcion"),
        fecha_adquisicion=date.fromisoformat(form["fecha_adquisicion"]) if form.get("fecha_adquisicion") else None,
        valor_adquisicion=Decimal(form.get("valor_adquisicion") or "0"),
        vida_util_anios=int(form.get("vida_util_anios") or 5),
        tasa_depreciacion=Decimal(form.get("tasa_depreciacion") or "20"),
        valor_libro_actual=Decimal(form.get("valor_adquisicion") or "0"),
        id_responsable=int(form["id_responsable"]) if form.get("id_responsable") else None,
        id_usuario=int(getattr(request.state, "user_id", 0) or 0),
    )
    db.add(activo)
    await db.commit()
    return RedirectResponse(url="/inventario/activos", status_code=302)


@router.get("/sustento", response_class=HTMLResponse)
async def sustento_lista(request: Request,
                          db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(PedidoSustento).order_by(PedidoSustento.created_at.desc()).limit(30))
    pedidos = result.scalars().all()
    return templates.TemplateResponse("inventario/sustento_lista.html",
        ctx(request, pedidos=pedidos))


@router.post("/sustento/agregar-item")
async def sustento_agregar_item(request: Request,
                                 db: AsyncSession = Depends(get_tenant_session)):
    data = await request.json()
    result = await db.execute(
        select(PedidoSustento).where(
            PedidoSustento.estado == "pendiente",
            PedidoSustento.id_usuario == int(getattr(request.state, "user_id", 0) or 0),
        ).order_by(PedidoSustento.created_at.desc()).limit(1)
    )
    pedido = result.scalar_one_or_none()

    if not pedido:
        codigo = await generar_codigo(db, "PS", "inv_pedidos_sustento")
        pedido = PedidoSustento(
            codigo=codigo, titulo=f"Pedido de Sustento {codigo}",
            estado="pendiente",
            id_usuario=int(getattr(request.state, "user_id", 0) or 0),
        )
        db.add(pedido)
        await db.flush()

    item = PedidoSustentoItem(
        id_pedido=pedido.id, modulo=data.get("modulo"),
        id_operacion=data.get("id_operacion"),
        codigo_operacion=data.get("codigo_operacion"),
        descripcion_operacion=data.get("descripcion"),
        monto_operacion=data.get("monto"), fecha_operacion=data.get("fecha"),
        motivo_consulta=data.get("motivo_consulta", "Se requiere sustento"),
    )
    db.add(item)
    await db.commit()
    return JSONResponse({"ok": True, "pedido_id": pedido.id, "pedido_codigo": pedido.codigo,
        "mensaje": f"Operacion agregada al Pedido de Sustento {pedido.codigo}",
    })


@router.get("/sustento/{id}", response_class=HTMLResponse)
async def sustento_detalle(request: Request, id: int,
                            db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(PedidoSustento).options(selectinload(PedidoSustento.items)).where(PedidoSustento.id == id))
    pedido = result.scalar_one_or_none()
    if not pedido:
        return HTMLResponse("No encontrado", status_code=404)
    responsables = (await db.execute(
        select(ConfigResponsable).where(ConfigResponsable.activo == True)
    )).scalars().all()
    return templates.TemplateResponse("inventario/sustento_detalle.html",
        ctx(request, pedido=pedido, responsables=responsables))
