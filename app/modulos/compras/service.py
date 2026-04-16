"""
Servicio de Compras — logica de negocio.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, extract
from decimal import Decimal
from datetime import date, datetime
from app.modulos.compras.models import (
    Compra, CompraItem, OrdenCompra, NotaMercaderia, NotaMercaderiaItem
)
from app.modulos.catalogo.kardex import registrar_movimiento
from app.modulos.catalogo.models import StockActual


async def generar_codigo_compra(db: AsyncSession) -> str:
    result = await db.execute(
        text("SELECT COUNT(*) FROM com_compras WHERE fecha_emision_doc = CURRENT_DATE"))
    n = result.scalar() + 1
    return f"COM-{date.today().strftime('%Y%m%d')}-{n:05d}"


async def generar_codigo_orden(db: AsyncSession) -> str:
    result = await db.execute(
        text("SELECT COUNT(*) FROM com_ordenes WHERE DATE(created_at) = CURRENT_DATE"))
    n = result.scalar() + 1
    return f"OC-{date.today().strftime('%Y%m%d')}-{n:05d}"


async def registrar_kardex_compra(
    db: AsyncSession,
    compra: Compra,
    id_usuario: int,
) -> bool:
    id_almacen = compra.id_almacen or 1

    for item in compra.items:
        if not item.id_producto:
            continue
        costo = item.costo_unitario_kardex or item.precio_unitario

        await registrar_movimiento(
            db,
            id_producto=item.id_producto,
            id_almacen=id_almacen,
            tipo="COMPRA",
            cantidad=Decimal(str(item.cantidad)),
            costo_unitario=Decimal(str(costo)),
            fecha=compra.fecha_emision_doc,
            origen_tabla="com_compras",
            origen_id=compra.id,
            origen_serie=compra.serie_doc,
            origen_numero=compra.numero_doc,
            unidad=item.unidad,
            id_usuario=id_usuario,
        )

    compra.kardex_registrado = True
    await db.flush()
    return True


async def detectar_stock_negativo(
    db: AsyncSession,
    id_almacen: int,
) -> list[dict]:
    result = await db.execute(
        select(StockActual).where(
            StockActual.id_almacen == id_almacen,
            StockActual.cantidad < 0,
        )
    )
    stocks_negativos = result.scalars().all()
    return [
        {
            "id_producto": s.id_producto,
            "id_almacen": s.id_almacen,
            "cantidad_negativa": abs(float(s.cantidad)),
        }
        for s in stocks_negativos
    ]


async def acumular_en_nota_mercaderia(
    db: AsyncSession,
    id_almacen: int,
    id_producto: int,
    cantidad: Decimal,
    id_pedido: int,
    nombre_producto: str,
    codigo_producto: str,
    unidad: str,
    id_usuario: int,
) -> NotaMercaderia:
    hoy = date.today()
    result = await db.execute(
        select(NotaMercaderia).where(
            NotaMercaderia.id_almacen == id_almacen,
            NotaMercaderia.estado == "pendiente",
            extract("year", NotaMercaderia.fecha_generacion) == hoy.year,
            extract("month", NotaMercaderia.fecha_generacion) == hoy.month,
        ).limit(1)
    )
    nota = result.scalar_one_or_none()

    if not nota:
        codigo = f"NM-{hoy.strftime('%Y%m')}-{id_almacen:02d}"
        nota = NotaMercaderia(
            codigo=codigo,
            id_almacen=id_almacen,
            fecha_generacion=hoy,
            estado="pendiente",
            id_usuario=id_usuario,
        )
        db.add(nota)
        await db.flush()

    result2 = await db.execute(
        select(NotaMercaderiaItem).where(
            NotaMercaderiaItem.id_nota == nota.id,
            NotaMercaderiaItem.id_producto == id_producto,
        )
    )
    item = result2.scalar_one_or_none()

    if not item:
        item = NotaMercaderiaItem(
            id_nota=nota.id,
            id_producto=id_producto,
            codigo_producto=codigo_producto,
            nombre_producto=nombre_producto,
            unidad=unidad,
            cantidad_acumulada=cantidad,
            pedidos_origen=[id_pedido],
        )
        db.add(item)
    else:
        item.cantidad_acumulada += cantidad
        pedidos = item.pedidos_origen or []
        if id_pedido not in pedidos:
            pedidos.append(id_pedido)
        item.pedidos_origen = pedidos

    nota.total_items = nota.total_items + (1 if not item.id else 0)
    await db.flush()
    return nota


async def leer_documento_con_vision(
    imagen_base64: str,
    api_key: str,
    tipo_documento: str = "factura",
) -> dict:
    import httpx
    import json

    prompt = f"""Analiza esta imagen de un {tipo_documento} comercial peruano.
Extrae EXACTAMENTE los siguientes datos en formato JSON:
{{
  "ruc_proveedor": "RUC del emisor (11 digitos)",
  "nombre_proveedor": "Razon social del emisor",
  "tipo_doc": "01 para factura, 03 para boleta",
  "serie": "Serie del comprobante (ej: F001)",
  "numero": "Numero correlativo",
  "fecha_emision": "Fecha en formato YYYY-MM-DD",
  "moneda": "PEN o USD",
  "subtotal": numero,
  "igv": numero,
  "total": numero,
  "items": [
    {{
      "descripcion": "descripcion del producto/servicio",
      "cantidad": numero,
      "unidad": "UND, KG, etc",
      "precio_unitario": numero,
      "subtotal": numero
    }}
  ]
}}
Si no puedes leer algun dato, usa null. Solo responde con el JSON, sin texto adicional."""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{imagen_base64}",
                                        "detail": "high",
                                    },
                                },
                            ],
                        }
                    ],
                    "max_tokens": 2000,
                },
            )
            data = response.json()
            contenido = data["choices"][0]["message"]["content"]
            contenido = contenido.replace("```json", "").replace("```", "").strip()
            return json.loads(contenido)
    except Exception as e:
        return {"error": str(e)}
