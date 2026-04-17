"""
Servicio pagoOK: cruza datos OCR de foto con notificaciones bancarias.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal
from datetime import date, timedelta, datetime
from app.modulos.contabilidad.models import (
    MovimientoBancario, ValidacionPago
)


async def validar_pago_foto(
    db: AsyncSession,
    numero_operacion: str | None,
    monto: Decimal | None,
    banco: str | None,
    id_pedido: int | None,
    id_punto_venta: int | None,
    id_usuario: int,
    foto_url: str | None = None,
    texto_ocr: str | None = None,
) -> dict:
    """
    Cruza datos del OCR con movimientos bancarios recibidos.
    Retorna resultado de la validacion.
    """
    inicio = datetime.now()

    validacion = ValidacionPago(
        id_pedido=id_pedido,
        id_punto_venta=id_punto_venta,
        id_usuario=id_usuario,
        foto_url=foto_url,
        numero_operacion_ocr=numero_operacion,
        monto_ocr=monto,
        banco_ocr=banco,
        texto_ocr_completo=texto_ocr,
        estado="pendiente",
    )
    db.add(validacion)
    await db.flush()

    # ESTRATEGIA 1: Match por N de operacion (mas confiable)
    if numero_operacion:
        result = await db.execute(
            select(MovimientoBancario).where(
                MovimientoBancario.numero_operacion == numero_operacion,
                MovimientoBancario.tipo == "abono",
            ).limit(1)
        )
        mov = result.scalar_one_or_none()

        if mov:
            return await _confirmar_match(
                db, validacion, mov, inicio, "numero_operacion")

    # ESTRATEGIA 2: Match por monto + banco + fecha reciente
    if monto and monto > 0:
        tolerancia = Decimal("0.50")
        fecha_desde = date.today() - timedelta(days=1)

        query = select(MovimientoBancario).where(
            MovimientoBancario.tipo == "abono",
            MovimientoBancario.fecha >= fecha_desde,
            MovimientoBancario.monto >= monto - tolerancia,
            MovimientoBancario.monto <= monto + tolerancia,
            MovimientoBancario.estado_cruce == "pendiente",
        )
        if banco:
            query = query.where(MovimientoBancario.banco == banco)

        result = await db.execute(query)
        movimientos = result.scalars().all()

        if len(movimientos) == 1:
            return await _confirmar_match(
                db, validacion, movimientos[0], inicio, "monto_banco")
        elif len(movimientos) > 1:
            validacion.estado = "pendiente"
            validacion.nota = f"Multiples matches posibles: {len(movimientos)}"
            await db.commit()
            return {
                "ok": False,
                "estado": "multiple_match",
                "mensaje": f"Hay {len(movimientos)} pagos con ese monto recientes. Puedes confirmar el N de operacion?",
                "candidatos": [
                    {
                        "id": m.id,
                        "monto": float(m.monto),
                        "fecha": str(m.fecha),
                        "hora": m.hora,
                        "banco": m.banco,
                    }
                    for m in movimientos[:5]
                ],
            }

    # Sin match
    validacion.estado = "no_encontrado"
    validacion.nota = "Sin notificacion bancaria que coincida"
    tiempo = int((datetime.now() - inicio).total_seconds())
    validacion.tiempo_respuesta_seg = tiempo
    await db.commit()

    return {
        "ok": False,
        "estado": "no_encontrado",
        "mensaje": "No encontramos la notificacion de este pago. Ya llego el dinero?",
        "validacion_id": validacion.id,
    }


async def _confirmar_match(
    db, validacion, movimiento, inicio, metodo: str
) -> dict:
    """Registra el match y actualiza estados."""
    validacion.estado = "confirmado"
    validacion.id_movimiento_bancario = movimiento.id
    validacion.diferencia_monto = abs(
        (validacion.monto_ocr or Decimal("0")) - movimiento.monto)
    validacion.confirmado_en = datetime.now()
    validacion.tiempo_respuesta_seg = int(
        (datetime.now() - inicio).total_seconds())
    validacion.nota = f"Match por {metodo}"

    movimiento.estado_cruce = "cruzado"
    if validacion.id_pedido:
        movimiento.id_venta = validacion.id_pedido
    movimiento.cruzado_en = datetime.now()

    await db.commit()

    return {
        "ok": True,
        "estado": "confirmado",
        "mensaje": f"Pago confirmado S/{movimiento.monto}",
        "monto": float(movimiento.monto),
        "banco": movimiento.banco,
        "numero_operacion": movimiento.numero_operacion,
        "nombre_pagador": movimiento.nombre_contraparte,
        "validacion_id": validacion.id,
        "tiempo_seg": validacion.tiempo_respuesta_seg,
    }
