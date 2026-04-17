"""
Cruce automatico de movimientos bancarios con ventas de Gestix.
Detecta pagos Yape/Plin/Transferencia y los vincula con pedidos.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal
from datetime import datetime, timedelta
from app.modulos.contabilidad.models import MovimientoBancario
from app.modulos.ventas.models import Pedido


async def cruzar_movimiento(
    db: AsyncSession,
    movimiento: MovimientoBancario,
    tolerancia_dias: int = 2,
    tolerancia_monto: Decimal = Decimal("0.01"),
) -> dict:
    """
    Intenta cruzar un movimiento bancario con una venta.
    Criterios:
    1. Mismo monto (tolerancia S/0.01)
    2. Fecha cercana (+/-2 dias)
    3. Medio de pago coincide (yape, plin, transferencia)
    4. Estado del pedido: confirmado o borrador
    """
    if movimiento.tipo != "abono":
        return {"cruzado": False, "motivo": "No es abono"}

    fecha_desde = movimiento.fecha - timedelta(days=tolerancia_dias)
    fecha_hasta = movimiento.fecha + timedelta(days=tolerancia_dias)

    medios_map = {
        "yape": ["yape"],
        "plin": ["plin"],
        "transferencia": ["transferencia", "deposito"],
        "bcp": ["transferencia", "deposito"],
        "bbva": ["transferencia", "deposito"],
        "interbank": ["transferencia", "deposito"],
    }
    medios = medios_map.get(movimiento.tipo_operacion or movimiento.banco, [])

    query = select(Pedido).where(
        Pedido.fecha >= fecha_desde,
        Pedido.fecha <= fecha_hasta,
        Pedido.total >= movimiento.monto - tolerancia_monto,
        Pedido.total <= movimiento.monto + tolerancia_monto,
        Pedido.anulado == False,
        Pedido.estado.in_(["confirmado", "facturado", "borrador"]),
    )

    if medios:
        query = query.where(Pedido.medio_pago.in_(medios))

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
        return {
            "cruzado": False,
            "motivo": f"Multiples matches ({len(pedidos)})",
            "candidatos": [p.codigo for p in pedidos[:5]],
        }
    else:
        movimiento.estado_cruce = "sin_match"
        movimiento.nota_cruce = "Sin pedido que coincida"
        return {"cruzado": False, "motivo": "Sin match"}


async def cruzar_pendientes(db: AsyncSession) -> dict:
    """Cruza todos los movimientos pendientes."""
    result = await db.execute(
        select(MovimientoBancario).where(
            MovimientoBancario.estado_cruce == "pendiente",
            MovimientoBancario.tipo == "abono",
        )
    )
    movimientos = result.scalars().all()

    cruzados = 0
    sin_match = 0

    for mov in movimientos:
        resultado = await cruzar_movimiento(db, mov)
        if resultado["cruzado"]:
            cruzados += 1
        else:
            sin_match += 1

    await db.commit()
    return {"cruzados": cruzados, "sin_match": sin_match,
            "total": len(movimientos)}
