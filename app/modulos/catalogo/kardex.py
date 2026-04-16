"""
Servicio de Kardex — Gestix.
Registra movimientos y recalcula stock y costo promedio.
Permite cortes de inventario a cualquier fecha.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import date, datetime
from decimal import Decimal
from app.modulos.catalogo.models import Kardex, ProductoStock


async def registrar_movimiento(
    db: AsyncSession,
    id_producto: int,
    id_almacen: int,
    tipo: str,
    cantidad: Decimal,
    costo_unitario: Decimal = Decimal(0),
    precio_venta: Decimal = Decimal(0),
    fecha: date = None,
    origen_tipo: str = None,
    origen_serie: str = None,
    origen_numero: str = None,
    origen_id: int = None,
    lote: str = None,
    fecha_vencimiento: date = None,
    observacion: str = None,
    id_usuario: int = None,
) -> Kardex:
    """
    Registra un movimiento en el kardex y actualiza el stock del almacén.
    Usa costo promedio ponderado para entradas.
    """
    if fecha is None:
        fecha = date.today()

    # Obtener stock actual
    result = await db.execute(
        select(ProductoStock).where(
            and_(
                ProductoStock.id_producto == id_producto,
                ProductoStock.id_almacen == id_almacen,
            )
        )
    )
    stock = result.scalar_one_or_none()

    if not stock:
        stock = ProductoStock(
            id_producto=id_producto,
            id_almacen=id_almacen,
            stock_actual=Decimal(0),
            stock_reservado=Decimal(0),
            stock_disponible=Decimal(0),
            costo_promedio=Decimal(0),
        )
        db.add(stock)
        await db.flush()

    es_entrada = tipo in (
        "COMPRA", "DEVOLUCION_VENTA", "AJUSTE_ENTRADA",
        "TRASLADO_ENTRADA", "PRODUCCION_ENTRADA", "INVENTARIO_INICIAL"
    )

    # Calcular costo promedio ponderado (solo en entradas)
    if es_entrada and cantidad > 0:
        stock_anterior = stock.stock_actual or Decimal(0)
        costo_anterior = stock.costo_promedio or Decimal(0)
        nuevo_costo_total = (stock_anterior * costo_anterior) + (cantidad * costo_unitario)
        nuevo_stock = stock_anterior + cantidad
        nuevo_costo_prom = nuevo_costo_total / nuevo_stock if nuevo_stock > 0 else costo_unitario
        stock.costo_promedio = round(nuevo_costo_prom, 4)
        stock.stock_actual = nuevo_stock
        stock.ultima_entrada = datetime.now()
    else:
        costo_unitario = stock.costo_promedio or Decimal(0)
        stock.stock_actual = (stock.stock_actual or Decimal(0)) - cantidad
        stock.ultima_salida = datetime.now()

    stock.stock_disponible = stock.stock_actual - (stock.stock_reservado or Decimal(0))

    # Calcular saldo en kardex
    saldo = stock.stock_actual

    # Registrar línea de kardex
    movimiento = Kardex(
        fecha=fecha,
        fecha_hora=datetime.now(),
        id_producto=id_producto,
        id_almacen=id_almacen,
        tipo=tipo,
        origen_tipo=origen_tipo,
        origen_serie=origen_serie,
        origen_numero=origen_numero,
        origen_id=origen_id,
        cantidad_entrada=cantidad if es_entrada else Decimal(0),
        cantidad_salida=Decimal(0) if es_entrada else cantidad,
        saldo=saldo,
        costo_unitario=costo_unitario,
        costo_total_entrada=cantidad * costo_unitario if es_entrada else Decimal(0),
        costo_total_salida=Decimal(0) if es_entrada else cantidad * costo_unitario,
        costo_saldo=saldo * (stock.costo_promedio or Decimal(0)),
        precio_venta=precio_venta,
        lote=lote,
        fecha_vencimiento=fecha_vencimiento,
        observacion=observacion,
        id_usuario=id_usuario,
    )
    db.add(movimiento)
    await db.commit()
    return movimiento


async def corte_inventario(
    db: AsyncSession,
    id_almacen: int,
    fecha_corte: date,
    id_producto: int = None,
) -> list[dict]:
    """
    Corte de inventario valorizado a una fecha específica.
    Retorna el stock y valor de cada producto a esa fecha.
    Esto es lo que Hernán necesita — instantáneo, a cualquier fecha.
    """
    filtros = [
        Kardex.id_almacen == id_almacen,
        Kardex.fecha <= fecha_corte,
    ]
    if id_producto:
        filtros.append(Kardex.id_producto == id_producto)

    # Subconsulta: último movimiento por producto hasta la fecha de corte
    subq = (
        select(
            Kardex.id_producto,
            func.max(Kardex.id).label("ultimo_id")
        )
        .where(and_(*filtros))
        .group_by(Kardex.id_producto)
        .subquery()
    )

    result = await db.execute(
        select(Kardex)
        .join(subq, and_(
            Kardex.id_producto == subq.c.id_producto,
            Kardex.id == subq.c.ultimo_id
        ))
        .order_by(Kardex.id_producto)
    )
    movimientos = result.scalars().all()

    corte = []
    for m in movimientos:
        if m.saldo > 0:
            corte.append({
                "id_producto": m.id_producto,
                "id_almacen": m.id_almacen,
                "fecha_corte": fecha_corte,
                "stock": float(m.saldo),
                "costo_unitario": float(m.costo_unitario),
                "valor_total": float(m.costo_saldo),
            })

    return corte
