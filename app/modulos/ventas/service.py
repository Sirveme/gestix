"""
Servicio de Ventas — logica de negocio separada del router.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from decimal import Decimal
from datetime import datetime, date
from app.modulos.ventas.models import Pedido, PedidoItem, CajaApertura
from app.modulos.catalogo.kardex import registrar_movimiento
import httpx


def calcular_item(
    cantidad: Decimal,
    precio_unitario: Decimal,
    descuento: Decimal = Decimal("0"),
    afecto_igv: bool = True,
    igv_tasa: Decimal = Decimal("18"),
) -> dict:
    subtotal_bruto = cantidad * precio_unitario
    descuento_monto = subtotal_bruto * (descuento / 100)
    subtotal = subtotal_bruto - descuento_monto

    if afecto_igv:
        factor = igv_tasa / 100
        base = subtotal / (1 + factor)
        igv = subtotal - base
    else:
        base = subtotal
        igv = Decimal("0")

    return {
        "subtotal": round(base, 2),
        "igv": round(igv, 2),
        "total": round(subtotal, 2),
        "descuento": round(descuento_monto, 2),
    }


def calcular_totales_pedido(items: list[dict]) -> dict:
    subtotal = sum(Decimal(str(i.get("subtotal", 0))) for i in items)
    igv = sum(Decimal(str(i.get("igv", 0))) for i in items)
    total = sum(Decimal(str(i.get("total", 0))) for i in items)
    return {
        "subtotal": round(subtotal, 2),
        "igv": round(igv, 2),
        "total": round(total, 2),
    }


async def generar_codigo_pedido(db: AsyncSession) -> str:
    result = await db.execute(
        text("SELECT COUNT(*) FROM ven_pedidos WHERE fecha = CURRENT_DATE")
    )
    n = result.scalar() + 1
    hoy = date.today()
    return f"PED-{hoy.strftime('%Y%m%d')}-{n:05d}"


async def obtener_caja_abierta(
    db: AsyncSession,
    id_punto_venta: int,
    id_usuario: int,
) -> CajaApertura | None:
    result = await db.execute(
        select(CajaApertura).where(
            CajaApertura.id_punto_venta == id_punto_venta,
            CajaApertura.estado == "abierta",
        ).order_by(CajaApertura.hora_apertura.desc()).limit(1)
    )
    return result.scalar_one_or_none()


async def confirmar_pedido(
    db: AsyncSession,
    pedido: Pedido,
    id_almacen: int,
    id_usuario: int,
) -> Pedido:
    for item in pedido.items:
        if item.id_producto:
            await registrar_movimiento(
                db,
                id_producto=item.id_producto,
                id_almacen=id_almacen,
                tipo="VENTA",
                cantidad=Decimal(str(item.cantidad)),
                fecha=pedido.fecha,
                origen_tabla="ven_pedidos",
                origen_id=pedido.id,
                origen_serie=pedido.serie_comprobante,
                origen_numero=pedido.numero_comprobante,
                unidad=item.unidad,
                id_usuario=id_usuario,
            )

    pedido.estado = "confirmado"
    await db.flush()
    return pedido


async def enviar_a_facturalo(
    pedido: Pedido,
    api_url: str,
    api_key: str,
) -> dict:
    tipo_map = {"01": "factura", "03": "boleta"}
    tipo = tipo_map.get(pedido.tipo_comprobante, "boleta")

    payload = {
        "tipo": tipo,
        "serie": pedido.serie_comprobante,
        "cliente": {
            "tipo_doc": "6" if len(pedido.ruc_dni or "") == 11 else "1",
            "num_doc": pedido.ruc_dni or "00000000",
            "nombre": pedido.nombre_cliente or "CLIENTES VARIOS",
            "direccion": pedido.direccion_cliente or "",
        },
        "items": [
            {
                "codigo": item.codigo_producto,
                "descripcion": item.nombre_producto,
                "unidad": item.unidad or "NIU",
                "cantidad": float(item.cantidad),
                "precio_unitario": float(item.precio_unitario),
                "subtotal": float(item.subtotal),
                "igv": float(item.igv),
                "total": float(item.total),
                "afecto_igv": item.afecto_igv,
            }
            for item in pedido.items
        ],
        "totales": {
            "subtotal": float(pedido.subtotal),
            "igv": float(pedido.igv),
            "total": float(pedido.total),
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{api_url}/api/v1/emitir",
                json=payload,
                headers={"Authorization": f"Bearer {api_key}"},
            )
            return response.json()
    except Exception as e:
        return {"error": str(e), "estado": "error_conexion"}
