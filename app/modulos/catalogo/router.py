from decimal import Decimal
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from sqlalchemy.orm import selectinload
from app.tenant import get_tenant_session
from app.modulos.catalogo.models import (
    Producto, ProductoPrecio, ProductoBarra, ProductoCombo,
    ProductoStock, Kardex,
    CatClasificador1, CatClasificador2, CatClasificador3,
    CatMarca, CatUnidad, CatColor, CatTalla
)

router = APIRouter(prefix="/catalogo", tags=["catalogo"])
templates = Jinja2Templates(directory="templates")


def ctx(request: Request, **kwargs):
    return {
        "request": request,
        "nombre": getattr(request.state, "nombre", ""),
        "empresa_nombre": getattr(request.state, "empresa_nombre", ""),
        **kwargs
    }


# ── Lista de productos ────────────────────────

@router.get("/", response_class=HTMLResponse)
async def catalogo_lista(
    request: Request,
    q: str = Query(default=""),
    vista: str = Query(default="tabla"),
    id_clas1: int = Query(default=None),
    db: AsyncSession = Depends(get_tenant_session)
):
    query = select(Producto).options(
        selectinload(Producto.unidad),
        selectinload(Producto.marca),
        selectinload(Producto.clasificador1),
        selectinload(Producto.barras),
    ).where(Producto.activo == True)

    if q:
        query = query.where(
            or_(
                Producto.nombre.ilike(f"%{q}%"),
                Producto.codigo.ilike(f"%{q}%"),
            )
        )
    if id_clas1:
        query = query.where(Producto.id_clasificador1 == id_clas1)

    query = query.order_by(Producto.nombre).limit(100)
    result = await db.execute(query)
    productos = result.scalars().all()

    r_clas = await db.execute(
        select(CatClasificador1).where(CatClasificador1.activo == True)
        .order_by(CatClasificador1.nombre)
    )
    clasificadores = r_clas.scalars().all()

    stocks = {}
    if productos:
        ids = [p.id for p in productos]
        r_stock = await db.execute(
            select(ProductoStock).where(ProductoStock.id_producto.in_(ids))
        )
        for s in r_stock.scalars().all():
            if s.id_producto not in stocks:
                stocks[s.id_producto] = s

    return templates.TemplateResponse("catalogo/lista.html", ctx(request,
        productos=productos,
        stocks=stocks,
        clasificadores=clasificadores,
        q=q,
        vista=vista,
        id_clas1=id_clas1,
        total=len(productos),
    ))


# ── Búsqueda por código de barra (HTMX) ──────

@router.get("/buscar-barra", response_class=HTMLResponse)
async def buscar_barra(
    request: Request,
    codigo: str = Query(...),
    db: AsyncSession = Depends(get_tenant_session)
):
    result = await db.execute(
        select(ProductoBarra).where(ProductoBarra.codigo == codigo.strip())
    )
    barra = result.scalar_one_or_none()

    if not barra:
        return HTMLResponse(f'<div class="search-noresult">Código {codigo} no encontrado</div>')

    r_prod = await db.execute(
        select(Producto).options(
            selectinload(Producto.unidad),
            selectinload(Producto.marca),
            selectinload(Producto.clasificador1),
        ).where(Producto.id == barra.id_producto)
    )
    prod = r_prod.scalar_one_or_none()
    return templates.TemplateResponse("catalogo/partials/producto_barra_result.html",
        ctx(request, producto=prod, barra=barra))


# ── Guardar producto ─────────────────────────

@router.post("/guardar", response_class=HTMLResponse)
async def producto_guardar(
    request: Request,
    db: AsyncSession = Depends(get_tenant_session)
):
    form = await request.form()
    prod_id = form.get("id")

    if prod_id:
        producto = await db.get(Producto, int(prod_id))
    else:
        producto = Producto()
        db.add(producto)

    for campo in ["codigo", "nombre", "descripcion", "imagen_url",
                  "cod_sunat", "cod_diremid", "reg_sanitario",
                  "ubicacion", "tipo"]:
        val = form.get(campo)
        if val is not None:
            setattr(producto, campo, val or None)

    for campo in ["id_clasificador1", "id_clasificador2", "id_clasificador3",
                  "id_marca", "id_unidad"]:
        val = form.get(campo)
        setattr(producto, campo, int(val) if val else None)

    for campo in ["precio_costo", "precio_venta", "stock_minimo", "stock_maximo"]:
        val = form.get(campo)
        setattr(producto, campo, Decimal(val) if val else Decimal("0"))

    for bool_campo in [
        "activo", "inventariado", "tiene_vencimiento", "tiene_lote",
        "tiene_talla", "tiene_color", "tiene_serie",
        "afecto_igv", "afecto_isc", "afecto_icbper", "destacado"
    ]:
        setattr(producto, bool_campo, form.get(bool_campo) == "on")

    from datetime import datetime as _dt
    producto.updated_at = _dt.now()
    producto.created_by = int(getattr(request.state, "user_id", 0) or 0)
    await db.commit()
    await db.refresh(producto)

    return HTMLResponse(
        f'<div class="toast toast-ok">✓ Producto guardado</div>'
        f'<script>setTimeout(()=>window.location="/catalogo/{producto.id}",800)</script>'
    )


# ── Búsqueda HTMX (texto) ─────────────────────

@router.get("/buscar", response_class=HTMLResponse)
async def catalogo_buscar(
    request: Request,
    q: str = Query(default=""),
    db: AsyncSession = Depends(get_tenant_session)
):
    productos = []
    if q and len(q) >= 2:
        result = await db.execute(
            select(Producto).options(
                selectinload(Producto.unidad),
                selectinload(Producto.marca),
                selectinload(Producto.clasificador1),
                selectinload(Producto.barras),
            ).where(
                Producto.activo == True,
                or_(
                    Producto.nombre.ilike(f"%{q}%"),
                    Producto.codigo.ilike(f"%{q}%"),
                )
            ).order_by(Producto.nombre).limit(20)
        )
        productos = result.scalars().all()
    return templates.TemplateResponse("catalogo/partials/buscar_result.html",
        ctx(request, productos=productos, q=q))


# ── Corte de inventario ─────────────────────

@router.get("/corte", response_class=HTMLResponse)
async def corte_inventario_view(
    request: Request,
    fecha: str = Query(default=None),
    id_almacen: int = Query(default=None),
    db: AsyncSession = Depends(get_tenant_session)
):
    from app.modulos.catalogo.kardex import corte_inventario
    from datetime import date

    fecha_corte = date.fromisoformat(fecha) if fecha else date.today()
    resultados = []

    if id_almacen:
        resultados = await corte_inventario(db, id_almacen, fecha_corte)

    return templates.TemplateResponse("catalogo/corte.html", ctx(request,
        fecha_corte=fecha_corte,
        id_almacen=id_almacen,
        resultados=resultados,
        total_valor=sum(r["valor_total"] for r in resultados),
    ))


# ── Maestros (unidad, marca, clasificador) ───

@router.get("/maestros", response_class=HTMLResponse)
async def maestros_index(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    n_unidades = (await db.execute(
        select(func.count(CatUnidad.id)).where(CatUnidad.activo == True)
    )).scalar()
    n_marcas = (await db.execute(
        select(func.count(CatMarca.id)).where(CatMarca.activo == True)
    )).scalar()
    n_clas1 = (await db.execute(
        select(func.count(CatClasificador1.id)).where(CatClasificador1.activo == True)
    )).scalar()
    return templates.TemplateResponse("catalogo/maestros.html", ctx(request,
        n_unidades=n_unidades, n_marcas=n_marcas, n_clas1=n_clas1,
    ))


@router.get("/maestros/unidad", response_class=HTMLResponse)
async def maestros_unidad_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(CatUnidad).order_by(CatUnidad.nombre))
    return templates.TemplateResponse("catalogo/maestros_unidad.html",
        ctx(request, unidades=result.scalars().all()))


@router.post("/maestros/unidad", response_class=HTMLResponse)
async def maestros_unidad_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    uid = form.get("id")
    if uid:
        r = await db.execute(select(CatUnidad).where(CatUnidad.id == int(uid)))
        unidad = r.scalar_one_or_none() or CatUnidad()
    else:
        unidad = CatUnidad()
        db.add(unidad)
    unidad.nombre = (form.get("nombre") or "").strip()
    unidad.abreviado = (form.get("abreviado") or "").strip()
    unidad.codigo_sunat = form.get("codigo_sunat") or None
    unidad.activo = form.get("activo") != "off"
    await db.commit()
    result = await db.execute(select(CatUnidad).order_by(CatUnidad.nombre))
    return templates.TemplateResponse("catalogo/maestros_unidad.html",
        ctx(request, unidades=result.scalars().all(), toast="Unidad guardada"))


@router.get("/maestros/marca", response_class=HTMLResponse)
async def maestros_marca_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(CatMarca).order_by(CatMarca.nombre))
    return templates.TemplateResponse("catalogo/maestros_marca.html",
        ctx(request, marcas=result.scalars().all()))


@router.post("/maestros/marca", response_class=HTMLResponse)
async def maestros_marca_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    mid = form.get("id")
    if mid:
        r = await db.execute(select(CatMarca).where(CatMarca.id == int(mid)))
        marca = r.scalar_one_or_none() or CatMarca()
    else:
        marca = CatMarca()
        db.add(marca)
    marca.nombre = (form.get("nombre") or "").strip()
    marca.activo = form.get("activo") != "off"
    await db.commit()
    result = await db.execute(select(CatMarca).order_by(CatMarca.nombre))
    return templates.TemplateResponse("catalogo/maestros_marca.html",
        ctx(request, marcas=result.scalars().all(), toast="Marca guardada"))


@router.get("/maestros/clas1", response_class=HTMLResponse)
async def maestros_clas1_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(CatClasificador1).order_by(CatClasificador1.nombre))
    return templates.TemplateResponse("catalogo/maestros_clas1.html",
        ctx(request, items=result.scalars().all()))


@router.post("/maestros/clas1", response_class=HTMLResponse)
async def maestros_clas1_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    cid = form.get("id")
    if cid:
        r = await db.execute(select(CatClasificador1).where(CatClasificador1.id == int(cid)))
        item = r.scalar_one_or_none() or CatClasificador1()
    else:
        item = CatClasificador1()
        db.add(item)
    item.nombre = (form.get("nombre") or "").strip()
    item.codigo = form.get("codigo") or None
    item.activo = form.get("activo") != "off"
    await db.commit()
    result = await db.execute(select(CatClasificador1).order_by(CatClasificador1.nombre))
    return templates.TemplateResponse("catalogo/maestros_clas1.html",
        ctx(request, items=result.scalars().all(), toast="Clasificador guardado"))


# ── AJAX: Clasificador 2 dependiente ─────────

@router.get("/ajax/clas2")
async def ajax_clas2(
    id_clas1: int = Query(...),
    db: AsyncSession = Depends(get_tenant_session)
):
    result = await db.execute(
        select(CatClasificador2)
        .where(CatClasificador2.id_nivel1 == id_clas1, CatClasificador2.activo == True)
        .order_by(CatClasificador2.nombre)
    )
    return [{"id": c.id, "nombre": c.nombre} for c in result.scalars().all()]


# ── Detalle / Editar producto ─────────────────

@router.get("/nuevo", response_class=HTMLResponse)
async def producto_nuevo(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    return await _form_producto(request, db, None)


@router.get("/{producto_id}", response_class=HTMLResponse)
async def producto_detalle(
    request: Request,
    producto_id: int,
    db: AsyncSession = Depends(get_tenant_session)
):
    return await _form_producto(request, db, producto_id)


async def _form_producto(request, db, producto_id):
    producto = None
    precios = []
    barras = []
    stocks = []

    if producto_id:
        r_prod = await db.execute(
            select(Producto).options(
                selectinload(Producto.unidad),
                selectinload(Producto.marca),
                selectinload(Producto.clasificador1),
                selectinload(Producto.clasificador2),
                selectinload(Producto.clasificador3),
            ).where(Producto.id == producto_id)
        )
        producto = r_prod.scalar_one_or_none()
        if not producto:
            return HTMLResponse("Producto no encontrado", status_code=404)

        r = await db.execute(
            select(ProductoPrecio).where(
                ProductoPrecio.id_producto == producto_id,
                ProductoPrecio.activo == True
            ).order_by(ProductoPrecio.id)
        )
        precios = r.scalars().all()

        r2 = await db.execute(
            select(ProductoBarra).where(ProductoBarra.id_producto == producto_id)
        )
        barras = r2.scalars().all()

        r3 = await db.execute(
            select(ProductoStock).where(ProductoStock.id_producto == producto_id)
        )
        stocks = r3.scalars().all()

    r_c1 = await db.execute(select(CatClasificador1).where(CatClasificador1.activo==True).order_by(CatClasificador1.nombre))
    r_marc = await db.execute(select(CatMarca).where(CatMarca.activo==True).order_by(CatMarca.nombre))
    r_unid = await db.execute(select(CatUnidad).where(CatUnidad.activo==True).order_by(CatUnidad.nombre))

    return templates.TemplateResponse("catalogo/form.html", {
        "request": request,
        "nombre": getattr(request.state, "nombre", ""),
        "empresa_nombre": getattr(request.state, "empresa_nombre", ""),
        "producto": producto,
        "precios": precios,
        "barras": barras,
        "stocks": stocks,
        "clasificadores1": r_c1.scalars().all(),
        "marcas": r_marc.scalars().all(),
        "unidades": r_unid.scalars().all(),
    })


# ── Precios (HTMX) ────────────────────────────

@router.post("/{producto_id}/precio", response_class=HTMLResponse)
async def agregar_precio(
    request: Request,
    producto_id: int,
    db: AsyncSession = Depends(get_tenant_session)
):
    form = await request.form()
    precio = ProductoPrecio(
        id_producto=producto_id,
        nombre=form.get("nombre"),
        unidad_venta=form.get("unidad_venta"),
        equivalente=Decimal(form.get("equivalente") or "1"),
        precio_costo=Decimal(form.get("precio_costo") or "0"),
        margen=Decimal(form.get("margen") or "0"),
        precio_venta=Decimal(form.get("precio_venta") or "0"),
        activo=True,
    )
    db.add(precio)
    await db.commit()

    r = await db.execute(
        select(ProductoPrecio).where(
            ProductoPrecio.id_producto == producto_id,
            ProductoPrecio.activo == True
        ).order_by(ProductoPrecio.id)
    )
    precios = r.scalars().all()
    return templates.TemplateResponse("catalogo/partials/precios_list.html",
        ctx(request, precios=precios, producto_id=producto_id))


# ── Kardex ────────────────────────────────────

@router.get("/{producto_id}/kardex", response_class=HTMLResponse)
async def ver_kardex(
    request: Request,
    producto_id: int,
    id_almacen: int = Query(default=None),
    db: AsyncSession = Depends(get_tenant_session)
):
    query = select(Kardex).where(Kardex.id_producto == producto_id)
    if id_almacen:
        query = query.where(Kardex.id_almacen == id_almacen)
    query = query.order_by(Kardex.fecha_hora.desc()).limit(200)

    result = await db.execute(query)
    movimientos = result.scalars().all()
    r_prod = await db.execute(
        select(Producto).options(
            selectinload(Producto.unidad),
        ).where(Producto.id == producto_id)
    )
    producto = r_prod.scalar_one_or_none()

    return templates.TemplateResponse("catalogo/kardex.html", ctx(request,
        producto=producto,
        movimientos=movimientos,
        id_almacen=id_almacen,
    ))


# ── Editar producto (HTMX inline) ────────────

@router.post("/{producto_id}/editar", response_class=HTMLResponse)
async def producto_editar(
    request: Request,
    producto_id: int,
    db: AsyncSession = Depends(get_tenant_session)
):
    r_prod = await db.execute(
        select(Producto).options(
            selectinload(Producto.unidad),
            selectinload(Producto.marca),
            selectinload(Producto.clasificador1),
        ).where(Producto.id == producto_id)
    )
    producto = r_prod.scalar_one_or_none()
    if not producto:
        return HTMLResponse("Producto no encontrado", status_code=404)

    form = await request.form()
    for campo in [
        "codigo", "nombre", "descripcion", "imagen_url",
        "id_clasificador1", "id_clasificador2", "id_clasificador3",
        "id_marca", "id_unidad", "cod_sunat",
        "cod_diremid", "reg_sanitario", "ubicacion",
        "stock_minimo", "stock_maximo",
        "precio_costo", "precio_venta", "tipo",
    ]:
        val = form.get(campo)
        if val is not None:
            setattr(producto, campo, val or None)

    for bool_campo in [
        "activo", "inventariado", "tiene_vencimiento", "tiene_lote",
        "tiene_talla", "tiene_color", "tiene_serie",
        "afecto_igv", "afecto_isc", "afecto_icbper", "destacado"
    ]:
        setattr(producto, bool_campo, form.get(bool_campo) == "on")

    from datetime import datetime as _dt
    producto.updated_at = _dt.now()
    producto.created_by = getattr(request.state, "user_id", None)
    await db.commit()

    return HTMLResponse(
        f'<div class="toast toast-ok">✓ Cambios guardados</div>'
        f'<script>setTimeout(()=>window.location="/catalogo/{producto_id}",800)</script>'
    )


# ── Agregar código de barra ───────────────────

@router.post("/{producto_id}/barra", response_class=HTMLResponse)
async def agregar_barra(
    request: Request,
    producto_id: int,
    db: AsyncSession = Depends(get_tenant_session)
):
    form = await request.form()
    codigo = (form.get("codigo") or "").strip()
    if not codigo:
        return HTMLResponse('<div class="toast toast-err">El código no puede estar vacío</div>')

    r = await db.execute(select(ProductoBarra).where(ProductoBarra.codigo == codigo))
    if r.scalar_one_or_none():
        return HTMLResponse('<div class="toast toast-err">Código ya registrado</div>')

    barra = ProductoBarra(
        id_producto=producto_id,
        codigo=codigo,
        tipo=form.get("tipo") or "EAN13",
    )
    db.add(barra)
    await db.commit()

    r2 = await db.execute(
        select(ProductoBarra).where(ProductoBarra.id_producto == producto_id)
    )
    barras = r2.scalars().all()
    return templates.TemplateResponse("catalogo/partials/barras_list.html",
        ctx(request, barras=barras, producto_id=producto_id))
