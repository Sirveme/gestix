"""
Servicio de cola de caja con WebSocket.
Gestiona pedidos en tiempo real entre vendedor, caja y cliente.
"""
import asyncio
from typing import Dict, Set
from fastapi import WebSocket
from datetime import datetime
from decimal import Decimal


class ColaWebSocketManager:
    """
    Gestiona conexiones WebSocket por schema de tenant.
    Cada empresa tiene su propio canal de cola.
    """
    def __init__(self):
        self.conexiones: Dict[str, Set[WebSocket]] = {}

    async def conectar(self, websocket: WebSocket, schema: str):
        await websocket.accept()
        if schema not in self.conexiones:
            self.conexiones[schema] = set()
        self.conexiones[schema].add(websocket)

    def desconectar(self, websocket: WebSocket, schema: str):
        if schema in self.conexiones:
            self.conexiones[schema].discard(websocket)

    async def broadcast(self, schema: str, mensaje: dict):
        if schema not in self.conexiones:
            return
        muertos = set()
        for ws in self.conexiones[schema].copy():
            try:
                await ws.send_json(mensaje)
            except Exception:
                muertos.add(ws)
        for ws in muertos:
            self.conexiones[schema].discard(ws)

    async def notificar_pago(self, schema: str, id_cola: int,
                              monto: float, medio: str):
        await self.broadcast(schema, {
            "tipo": "pago_confirmado",
            "id_cola": id_cola,
            "monto": monto,
            "medio": medio,
            "ts": datetime.now().isoformat(),
        })

    async def notificar_nuevo_pedido(self, schema: str, pedido_data: dict):
        await self.broadcast(schema, {
            "tipo": "nuevo_pedido",
            "pedido": pedido_data,
            "ts": datetime.now().isoformat(),
        })

    async def notificar_entregado(self, schema: str, id_cola: int):
        await self.broadcast(schema, {
            "tipo": "entregado",
            "id_cola": id_cola,
            "ts": datetime.now().isoformat(),
        })


cola_manager = ColaWebSocketManager()


async def generar_codigo_cliente(db) -> str:
    """Genera código único para el papelito del cliente."""
    from sqlalchemy import select, func
    from app.modulos.ventas.models import PedidoCola
    from datetime import date

    hoy = date.today()
    result = await db.execute(
        select(func.count(PedidoCola.id)).where(
            PedidoCola.created_at >= datetime.combine(hoy, datetime.min.time())
        )
    )
    n = (result.scalar() or 0) + 1
    return f"{hoy.strftime('%d%m')}-{n:03d}"


async def get_cola_actual(db) -> dict:
    """Retorna el estado actual de la cola para la pantalla de caja."""
    from sqlalchemy import select
    from app.modulos.ventas.models import PedidoCola, Pedido

    result = await db.execute(
        select(PedidoCola).where(
            PedidoCola.estado.in_(["en_cola", "pagado"])
        ).order_by(PedidoCola.created_at)
    )
    colas = result.scalars().all()

    en_cola = []
    pagados = []

    for c in colas:
        r_ped = await db.execute(
            select(Pedido).where(Pedido.id == c.id_pedido))
        pedido = r_ped.scalar_one_or_none()

        datos = {
            "id": c.id,
            "id_pedido": c.id_pedido,
            "codigo_cliente": c.codigo_cliente,
            "nombre_cliente": c.nombre_cliente or "",
            "medio_pago": c.medio_pago_anticipado or "efectivo",
            "estado": c.estado,
            "total": float(pedido.total) if pedido else 0,
            "monto_pagado": float(c.monto_pagado) if c.monto_pagado else 0,
            "created_at": c.created_at.strftime("%H:%M"),
            "pagado_en": c.pagado_en.strftime("%H:%M") if c.pagado_en else None,
        }

        if c.estado == "en_cola":
            en_cola.append(datos)
        else:
            pagados.append(datos)

    return {"en_cola": en_cola, "pagados": pagados}
