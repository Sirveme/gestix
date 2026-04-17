"""Cruce de movimientos bancarios con ventas de Gestix."""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal
from datetime import timedelta, datetime
from app.modulos.contabilidad.models import MovimientoBancario
from app.modulos.ventas.models import Pedido


async def cruzar_movimiento(
    db: AsyncSession,
    movimiento: MovimientoBancario,
    tolerancia_dias: int = 2,
    tolerancia_monto: Decimal = Decimal("0.50"),
) -> dict:
    """Cruza un movimiento bancario con una venta."""
    if movimiento.tipo != "abono":
        return {"cruzado": False, "motivo": "No es abono"}

    if movimiento.confianza == "baja":
        return {"cruzado": False, "motivo": "Confianza baja -- revisar manualmente"}

    fecha_desde = movimiento.fecha - timedelta(days=tolerancia_dias)
    fecha_hasta = movimiento.fecha + timedelta(days=tolerancia_dias)

    medios_map = {
        "yape": ["yape"],
        "plin": ["plin"],
        "interbank": ["transferencia", "deposito", "plin"],
        "bcp": ["transferencia", "deposito", "yape"],
        "bbva": ["transferencia", "deposito", "plin"],
        "scotiabank": ["transferencia", "deposito"],
        "banbif": ["transferencia", "deposito"],
    }
    medios = medios_map.get(movimiento.banco, ["transferencia"])

    query = select(Pedido).where(
        Pedido.fecha >= fecha_desde,
        Pedido.fecha <= fecha_hasta,
        Pedido.total >= movimiento.monto - tolerancia_monto,
        Pedido.total <= movimiento.monto + tolerancia_monto,
        Pedido.anulado == False,
        Pedido.estado.in_(["confirmado", "facturado", "borrador"]),
        Pedido.medio_pago.in_(medios),
    )

    result = await db.execute(query)
    pedidos = result.scalars().all()

    if len(pedidos) == 1:
        pedido = pedidos[0]
        movimiento.estado_cruce = "cruzado"
        movimiento.id_venta = pedido.id
        movimiento.diferencia_monto = abs(
            Decimal(str(pedido.total)) - movimiento.monto)
        movimiento.cruzado_en = datetime.now()
        await db.flush()
        return {
            "cruzado": True,
            "pedido_id": pedido.id,
            "pedido_codigo": pedido.codigo,
            "diferencia": float(movimiento.diferencia_monto),
        }
    elif len(pedidos) > 1:
        movimiento.estado_cruce = "sin_match"
        movimiento.nota_cruce = f"Multiples pedidos posibles: {len(pedidos)}"
        return {"cruzado": False, "motivo": f"Multiples matches ({len(pedidos)})"}
    else:
        movimiento.estado_cruce = "sin_match"
        movimiento.nota_cruce = "Sin pedido que coincida en monto/fecha/medio"
        return {"cruzado": False, "motivo": "Sin match"}


async def cruzar_pendientes(db: AsyncSession) -> dict:
    result = await db.execute(
        select(MovimientoBancario).where(
            MovimientoBancario.estado_cruce == "pendiente",
            MovimientoBancario.tipo == "abono",
        )
    )
    movimientos = result.scalars().all()
    cruzados = sin_match = 0
    for mov in movimientos:
        r = await cruzar_movimiento(db, mov)
        if r["cruzado"]:
            cruzados += 1
        else:
            sin_match += 1
    await db.commit()
    return {"cruzados": cruzados, "sin_match": sin_match, "total": len(movimientos)}
