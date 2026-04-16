"""
Servicio de Inventario — logica de negocio.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload
from decimal import Decimal
from datetime import date, datetime
from app.modulos.inventario.models import (
    AjusteStock, AjusteStockItem,
    Transferencia, TransferenciaItem,
    TomaInventario, TomaInventarioItem,
)
from app.modulos.catalogo.kardex import registrar_movimiento
from app.modulos.catalogo.models import StockActual, Producto


async def generar_codigo(db: AsyncSession, prefijo: str, tabla: str) -> str:
    result = await db.execute(
        text(f"SELECT COUNT(*) FROM {tabla} WHERE DATE(created_at) = CURRENT_DATE"))
    n = result.scalar() + 1
    return f"{prefijo}-{date.today().strftime('%Y%m%d')}-{n:05d}"


async def registrar_kardex_ajuste(
    db: AsyncSession, ajuste: AjusteStock, id_usuario: int,
) -> bool:
    for item in ajuste.items:
        tipo_kardex = "AJUSTE+" if ajuste.tipo == "INGRESO" else "AJUSTE-"
        await registrar_movimiento(
            db, id_producto=item.id_producto, id_almacen=ajuste.id_almacen,
            tipo=tipo_kardex, cantidad=Decimal(str(item.cantidad_ajuste)),
            costo_unitario=Decimal(str(item.costo_unitario or 0)),
            fecha=ajuste.fecha, origen_tabla="inv_ajustes", origen_id=ajuste.id,
            unidad=item.unidad, id_usuario=id_usuario, nota=ajuste.sustento,
        )
    ajuste.kardex_registrado = True
    await db.flush()
    return True


async def registrar_kardex_transferencia(
    db: AsyncSession, transferencia: Transferencia, id_usuario: int,
) -> bool:
    for item in transferencia.items:
        await registrar_movimiento(
            db, id_producto=item.id_producto,
            id_almacen=transferencia.id_almacen_origen,
            tipo="TRASLADO_OUT", cantidad=Decimal(str(item.cantidad_enviada)),
            costo_unitario=Decimal(str(item.costo_unitario or 0)),
            fecha=transferencia.fecha, origen_tabla="inv_transferencias",
            origen_id=transferencia.id, unidad=item.unidad, id_usuario=id_usuario,
        )
        await registrar_movimiento(
            db, id_producto=item.id_producto,
            id_almacen=transferencia.id_almacen_destino,
            tipo="TRASLADO_IN",
            cantidad=Decimal(str(item.cantidad_recibida or item.cantidad_enviada)),
            costo_unitario=Decimal(str(item.costo_unitario or 0)),
            fecha=transferencia.fecha, origen_tabla="inv_transferencias",
            origen_id=transferencia.id, unidad=item.unidad, id_usuario=id_usuario,
        )
    transferencia.kardex_registrado = True
    await db.flush()
    return True


async def finalizar_toma_inventario(
    db: AsyncSession, toma: TomaInventario, id_usuario: int,
) -> AjusteStock:
    items_con_diferencia = [
        i for i in toma.items
        if i.cantidad_contada is not None and i.diferencia != 0
    ]

    if not items_con_diferencia:
        toma.estado = "finalizada"
        toma.fecha_fin = datetime.now()
        await db.flush()
        return None

    codigo_aj = await generar_codigo(db, "AJ", "inv_ajustes")
    ajuste = AjusteStock(
        codigo=codigo_aj, id_almacen=toma.id_almacen, fecha=date.today(),
        tipo="INGRESO", motivo="toma_inventario",
        sustento=f"Ajuste automatico generado por toma de inventario {toma.codigo}",
        estado="aprobado", id_usuario=id_usuario,
    )
    db.add(ajuste)
    await db.flush()

    for item in items_con_diferencia:
        aj_item = AjusteStockItem(
            id_ajuste=ajuste.id, id_producto=item.id_producto,
            codigo_producto=item.codigo_producto,
            nombre_producto=item.nombre_producto, unidad=item.unidad,
            cantidad_sistema=item.cantidad_sistema,
            cantidad_ajuste=abs(float(item.diferencia)),
            costo_unitario=item.costo_unitario or 0,
            nota=f"Diferencia toma: sistema={item.cantidad_sistema}, contado={item.cantidad_contada}",
        )
        db.add(aj_item)

    await db.flush()

    result = await db.execute(
        select(AjusteStock).options(
            selectinload(AjusteStock.items)
        ).where(AjusteStock.id == ajuste.id)
    )
    ajuste_completo = result.scalar_one()
    await registrar_kardex_ajuste(db, ajuste_completo, id_usuario)

    toma.estado = "finalizada"
    toma.fecha_fin = datetime.now()
    toma.id_ajuste_generado = ajuste.id
    toma.items_con_diferencia = len(items_con_diferencia)
    toma.valor_diferencia_total = sum(
        abs(float(i.valor_diferencia or 0)) for i in items_con_diferencia)

    await db.flush()
    return ajuste
