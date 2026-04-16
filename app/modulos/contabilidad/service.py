"""
Servicio de Contabilidad -- logica de negocio.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from decimal import Decimal
from datetime import date, datetime
from app.modulos.contabilidad.models import (
    AsientoContable, PartidaContable, CuentaContable,
    ConfigContable, DeclaracionTributaria, DiagnosticoEmpresa,
    HallazgoDiagnostico, RegistroSIRE
)
from app.modulos.ventas.models import Pedido, PedidoItem
from app.modulos.compras.models import Compra, CompraItem


# -----------------------------------------
# GENERACION AUTOMATICA DE ASIENTOS
# -----------------------------------------

async def obtener_cuenta(db: AsyncSession, concepto: str) -> CuentaContable | None:
    """Obtiene la cuenta configurada para un concepto."""
    result = await db.execute(
        select(ConfigContable).where(ConfigContable.concepto == concepto))
    config = result.scalar_one_or_none()
    if not config or not config.id_cuenta:
        return None
    result2 = await db.execute(
        select(CuentaContable).where(CuentaContable.id == config.id_cuenta))
    return result2.scalar_one_or_none()


async def generar_asiento_venta(
    db: AsyncSession,
    pedido: Pedido,
    id_usuario: int,
) -> AsientoContable | None:
    """
    Genera asiento contable automatico para una venta.
    Debito: Caja/Clientes
    Credito: Ventas gravadas + IGV ventas
    """
    periodo = pedido.fecha.strftime("%Y-%m")

    r_num = await db.execute(
        select(func.count(AsientoContable.id)).where(
            AsientoContable.periodo == periodo))
    numero = (r_num.scalar() or 0) + 1

    asiento = AsientoContable(
        numero=numero,
        periodo=periodo,
        fecha=pedido.fecha,
        glosa=f"Venta {pedido.codigo} - {pedido.nombre_cliente or 'Clientes varios'}",
        origen="venta",
        origen_tabla="ven_pedidos",
        origen_id=pedido.id,
        origen_codigo=pedido.codigo,
        total_debe=pedido.total,
        total_haber=pedido.total,
        estado="contabilizado",
        id_usuario=id_usuario,
    )
    db.add(asiento)
    await db.flush()

    # Partida 1: Debito Caja (10111)
    cta_caja = await obtener_cuenta(db, "caja")
    db.add(PartidaContable(
        id_asiento=asiento.id,
        codigo_cuenta=cta_caja.codigo if cta_caja else "10111",
        nombre_cuenta=cta_caja.alias or cta_caja.nombre_oficial
            if cta_caja else "Caja",
        debe=pedido.total,
        haber=0,
        glosa_partida=f"Cobro venta {pedido.codigo}",
    ))

    # Partida 2: Credito Ventas (70111)
    cta_ventas = await obtener_cuenta(db, "ventas_gravadas")
    db.add(PartidaContable(
        id_asiento=asiento.id,
        codigo_cuenta=cta_ventas.codigo if cta_ventas else "70111",
        nombre_cuenta=cta_ventas.alias or cta_ventas.nombre_oficial
            if cta_ventas else "Mercaderias - Terceros",
        debe=0,
        haber=pedido.subtotal,
        glosa_partida=f"Venta {pedido.codigo}",
    ))

    # Partida 3: Credito IGV (40111)
    if pedido.igv and pedido.igv > 0:
        cta_igv = await obtener_cuenta(db, "igv_ventas")
        db.add(PartidaContable(
            id_asiento=asiento.id,
            codigo_cuenta=cta_igv.codigo if cta_igv else "40111",
            nombre_cuenta=cta_igv.alias or cta_igv.nombre_oficial
                if cta_igv else "IGV - Cuenta propia",
            debe=0,
            haber=pedido.igv,
            glosa_partida=f"IGV venta {pedido.codigo}",
        ))

    await db.flush()
    return asiento


async def generar_asiento_compra(
    db: AsyncSession,
    compra: Compra,
    id_usuario: int,
) -> AsientoContable | None:
    """Genera asiento contable automatico para una compra."""
    periodo = compra.fecha_emision_doc.strftime("%Y-%m")

    r_num = await db.execute(
        select(func.count(AsientoContable.id)).where(
            AsientoContable.periodo == periodo))
    numero = (r_num.scalar() or 0) + 1

    asiento = AsientoContable(
        numero=numero,
        periodo=periodo,
        fecha=compra.fecha_emision_doc,
        glosa=f"Compra {compra.codigo} - {compra.nombre_proveedor}",
        origen="compra",
        origen_tabla="com_compras",
        origen_id=compra.id,
        origen_codigo=compra.codigo,
        total_debe=compra.total,
        total_haber=compra.total,
        estado="contabilizado",
        id_usuario=id_usuario,
    )
    db.add(asiento)
    await db.flush()

    # Partida 1: Debito Mercaderias (60111)
    cta_compras = await obtener_cuenta(db, "compras")
    db.add(PartidaContable(
        id_asiento=asiento.id,
        codigo_cuenta=cta_compras.codigo if cta_compras else "60111",
        nombre_cuenta=cta_compras.alias or cta_compras.nombre_oficial
            if cta_compras else "Compras - Mercaderias",
        debe=compra.subtotal,
        haber=0,
    ))

    # Partida 2: Debito IGV (40111)
    if compra.igv and compra.igv > 0:
        cta_igv_c = await obtener_cuenta(db, "igv_compras")
        db.add(PartidaContable(
            id_asiento=asiento.id,
            codigo_cuenta=cta_igv_c.codigo if cta_igv_c else "40111",
            nombre_cuenta="IGV - Credito fiscal",
            debe=compra.igv,
            haber=0,
        ))

    # Partida 3: Credito Proveedores (42121)
    cta_prov = await obtener_cuenta(db, "proveedores")
    db.add(PartidaContable(
        id_asiento=asiento.id,
        codigo_cuenta=cta_prov.codigo if cta_prov else "42121",
        nombre_cuenta=cta_prov.alias or cta_prov.nombre_oficial
            if cta_prov else "Emitidas - Terceros",
        debe=0,
        haber=compra.total,
        glosa_partida=f"Por pagar compra {compra.codigo}",
    ))

    await db.flush()
    return asiento


# -----------------------------------------
# CAPA 2: DECLARACION MENSUAL
# -----------------------------------------

async def calcular_declaracion_mensual(
    db: AsyncSession,
    periodo: str,
    id_usuario: int,
) -> DeclaracionTributaria:
    """
    Calcula PDT 621 (IGV + Renta 3ra) del periodo.
    """
    anio, mes = periodo.split("-")
    fecha_desde = date(int(anio), int(mes), 1)
    import calendar
    ultimo_dia = calendar.monthrange(int(anio), int(mes))[1]
    fecha_hasta = date(int(anio), int(mes), ultimo_dia)

    # Ventas del periodo
    r_ventas = await db.execute(
        select(
            func.sum(Pedido.subtotal).label("base"),
            func.sum(Pedido.igv).label("igv"),
            func.sum(Pedido.total).label("total"),
        ).where(
            Pedido.fecha >= fecha_desde,
            Pedido.fecha <= fecha_hasta,
            Pedido.estado.in_(["confirmado", "facturado"]),
            Pedido.anulado == False,
        )
    )
    row_ventas = r_ventas.one()
    base_ventas = Decimal(str(row_ventas.base or 0))
    igv_ventas = Decimal(str(row_ventas.igv or 0))

    # Compras del periodo
    r_compras = await db.execute(
        select(
            func.sum(Compra.subtotal).label("base"),
            func.sum(Compra.igv).label("igv"),
        ).where(
            Compra.fecha_emision_doc >= fecha_desde,
            Compra.fecha_emision_doc <= fecha_hasta,
            Compra.estado == "aprobada",
        )
    )
    row_compras = r_compras.one()
    base_compras = Decimal(str(row_compras.base or 0))
    igv_compras = Decimal(str(row_compras.igv or 0))

    # IGV a pagar = IGV ventas - IGV compras (credito fiscal)
    igv_a_pagar = max(Decimal("0"), igv_ventas - igv_compras)

    # Renta 3ra - pago a cuenta
    from app.modulos.config.models import ConfigImpuestos
    r_imp = await db.execute(select(ConfigImpuestos).limit(1))
    imp = r_imp.scalar_one_or_none()

    if imp and imp.pago_cuenta_metodo == "coef" and imp.pago_cuenta_coeficiente:
        renta = base_ventas * Decimal(str(imp.pago_cuenta_coeficiente))
    elif imp and imp.pago_cuenta_porcentaje:
        renta = base_ventas * Decimal(str(imp.pago_cuenta_porcentaje)) / 100
    else:
        renta = base_ventas * Decimal("0.015")

    renta = round(renta, 2)

    # Fecha de vencimiento (ultimo dia del mes siguiente)
    mes_siguiente = int(mes) + 1 if int(mes) < 12 else 1
    anio_sig = int(anio) if int(mes) < 12 else int(anio) + 1
    ultimo_dia_sig = calendar.monthrange(anio_sig, mes_siguiente)[1]
    vencimiento = date(anio_sig, mes_siguiente, ultimo_dia_sig)

    # Buscar o crear declaracion
    r_decl = await db.execute(
        select(DeclaracionTributaria).where(
            DeclaracionTributaria.periodo == periodo,
            DeclaracionTributaria.tipo == "pdt621",
        )
    )
    decl = r_decl.scalar_one_or_none()
    if not decl:
        decl = DeclaracionTributaria(
            periodo=periodo, tipo="pdt621", id_usuario=id_usuario)
        db.add(decl)

    decl.base_ventas = base_ventas
    decl.igv_ventas = igv_ventas
    decl.base_compras = base_compras
    decl.igv_compras = igv_compras
    decl.igv_a_pagar = igv_a_pagar
    decl.renta_a_pagar = renta
    decl.fecha_vencimiento = vencimiento
    decl.estado = "calculado"
    decl.datos_calculo = {
        "periodo": periodo,
        "ventas_total": float(base_ventas + igv_ventas),
        "compras_total": float(base_compras + igv_compras),
        "credito_fiscal": float(igv_compras),
    }

    await db.flush()
    return decl


# -----------------------------------------
# CAPA 3: SCAN / DIAGNOSTICO
# -----------------------------------------

CHECKS_SCAN = [
    ("VTAS_001", "ventas", "amarillo",
     "Ventas sin comprobante electronico",
     "Comprobantes electronicos pendientes de emision",
     "Ir a Ventas -> revisar pedidos sin CPE",
     "El cajero o vendedor",
     "Responsable del punto de venta",
     "/ventas/pedidos?estado=confirmado"),

    ("VTAS_002", "ventas", "rojo",
     "Stock negativo -- ventas sin sustento de ingreso",
     "Documentos de ingreso de mercaderia (facturas de compra)",
     "Ir a Compras -> Notas de Mercaderia -> regularizar",
     "El proveedor o el area de compras",
     "Encargado de almacen",
     "/compras/notas-mercaderia"),

    ("COMP_001", "compras", "amarillo",
     "Compras por aprobar",
     "Revision y aprobacion de facturas de proveedores",
     "Ir a Compras -> revisar y aprobar",
     "Contador o administrador",
     "Responsable de compras",
     "/compras/lista?estado=por_aprobar"),

    ("COMP_002", "compras", "rojo",
     "Compras sin sustento (facturas sin documento fisico)",
     "Documentos fisicos o digitales de las compras",
     "Solicitar al proveedor la factura fisica o PDF",
     "El proveedor",
     "Area de compras",
     "/compras/lista"),

    ("TRIB_001", "tributario", "rojo",
     "Declaracion mensual pendiente",
     "Declaracion PDT 621 del periodo",
     "Ir a Contabilidad -> Declaraciones -> calcular y presentar",
     "Contador",
     "Contador responsable",
     "/contabilidad/declaraciones"),

    ("TRIB_002", "tributario", "amarillo",
     "Cruce SIRE pendiente",
     "Importar registros de SUNAT SIRE para cruzar",
     "Ir a Contabilidad -> SIRE -> importar periodo",
     "Contador",
     "Contador",
     "/contabilidad/sire"),

    ("BANC_001", "bancario", "amarillo",
     "Movimientos bancarios sin cruzar",
     "Notificaciones bancarias del periodo",
     "Ir a Contabilidad -> Banco -> cruzar movimientos",
     "Administrador o contador",
     "Responsable de tesoreria",
     "/contabilidad/banco"),

    ("INV_001", "inventario", "amarillo",
     "Sin toma de inventario en el periodo",
     "Conteo fisico de inventario",
     "Ir a Inventario -> Tomas -> iniciar conteo",
     "Almacenero",
     "Jefe de almacen",
     "/inventario/tomas"),

    ("INV_002", "inventario", "amarillo",
     "Ajustes de stock pendientes de aprobar",
     "Aprobacion de ajustes por contador o gerente",
     "Ir a Inventario -> Ajustes -> revisar y aprobar",
     "Contador o gerente",
     "Responsable contable",
     "/inventario/ajustes"),
]


async def ejecutar_scan(
    db: AsyncSession,
    periodo: str,
    id_usuario: int,
) -> DiagnosticoEmpresa:
    """
    Ejecuta todos los checks de diagnostico y genera el reporte.
    """
    anio, mes = periodo.split("-")
    import calendar
    fecha_desde = date(int(anio), int(mes), 1)
    ultimo_dia = calendar.monthrange(int(anio), int(mes))[1]
    fecha_hasta = date(int(anio), int(mes), ultimo_dia)

    diagnostico = DiagnosticoEmpresa(
        periodo=periodo,
        fecha_scan=datetime.now(),
        id_usuario=id_usuario,
    )
    db.add(diagnostico)
    await db.flush()

    hallazgos = []
    estados_area = {}

    for check in CHECKS_SCAN:
        codigo, area, severidad, titulo, que_falta, como, quien_da, quien_resp, url = check

        problema = False
        datos = {}

        if codigo == "VTAS_001":
            r = await db.execute(
                select(func.count(Pedido.id)).where(
                    Pedido.fecha >= fecha_desde,
                    Pedido.fecha <= fecha_hasta,
                    Pedido.estado == "confirmado",
                    Pedido.tipo_comprobante.in_(["01", "03"]),
                    Pedido.numero_comprobante == None,
                )
            )
            n = r.scalar() or 0
            if n > 0:
                problema = True
                datos = {"cantidad": n}
                titulo = f"{titulo}: {n} pedido(s)"

        elif codigo == "VTAS_002":
            from app.modulos.compras.models import NotaMercaderia
            r = await db.execute(
                select(func.count(NotaMercaderia.id)).where(
                    NotaMercaderia.estado == "pendiente"))
            n = r.scalar() or 0
            if n > 0:
                problema = True
                datos = {"notas_pendientes": n}

        elif codigo == "COMP_001":
            r = await db.execute(
                select(func.count(Compra.id)).where(
                    Compra.fecha_emision_doc >= fecha_desde,
                    Compra.fecha_emision_doc <= fecha_hasta,
                    Compra.estado == "por_aprobar",
                ))
            n = r.scalar() or 0
            if n > 0:
                problema = True
                datos = {"cantidad": n}
                titulo = f"{titulo}: {n} compra(s)"

        elif codigo == "TRIB_001":
            r = await db.execute(
                select(DeclaracionTributaria).where(
                    DeclaracionTributaria.periodo == periodo,
                    DeclaracionTributaria.tipo == "pdt621",
                    DeclaracionTributaria.estado.in_(
                        ["presentado", "pagado"]),
                ))
            decl = r.scalar_one_or_none()
            if not decl:
                problema = True

        elif codigo == "TRIB_002":
            r = await db.execute(
                select(func.count(RegistroSIRE.id)).where(
                    RegistroSIRE.periodo == periodo,
                ))
            n = r.scalar() or 0
            if n == 0:
                problema = True

        elif codigo == "INV_001":
            from app.modulos.inventario.models import TomaInventario
            r = await db.execute(
                select(func.count(TomaInventario.id)).where(
                    TomaInventario.fecha_inicio >= fecha_desde,
                    TomaInventario.fecha_inicio <= fecha_hasta,
                    TomaInventario.estado == "finalizada",
                ))
            n = r.scalar() or 0
            if n == 0:
                problema = True

        elif codigo == "INV_002":
            from app.modulos.inventario.models import AjusteStock
            r = await db.execute(
                select(func.count(AjusteStock.id)).where(
                    AjusteStock.fecha >= fecha_desde,
                    AjusteStock.fecha <= fecha_hasta,
                    AjusteStock.estado == "pendiente",
                ))
            n = r.scalar() or 0
            if n > 0:
                problema = True
                datos = {"cantidad": n}

        if problema:
            hallazgo = HallazgoDiagnostico(
                id_diagnostico=diagnostico.id,
                area=area,
                severidad=severidad,
                codigo=codigo,
                titulo=titulo,
                que_falta=que_falta,
                como_conseguir=como,
                quien_debe_dar=quien_da,
                quien_es_responsable=quien_resp,
                accion_sugerida=f"Ir a: {url}",
                url_accion=url,
                datos_adicionales=datos,
            )
            db.add(hallazgo)
            hallazgos.append(hallazgo)

            area_actual = estados_area.get(area, "verde")
            if severidad == "rojo" or area_actual == "rojo":
                estados_area[area] = "rojo"
            elif severidad == "amarillo" and area_actual != "rojo":
                estados_area[area] = "amarillo"

    diagnostico.estado_ventas = estados_area.get("ventas", "verde")
    diagnostico.estado_compras = estados_area.get("compras", "verde")
    diagnostico.estado_tributario = estados_area.get("tributario", "verde")
    diagnostico.estado_bancario = estados_area.get("bancario", "verde")
    diagnostico.estado_inventario = estados_area.get("inventario", "verde")

    estados = list(estados_area.values())
    if "rojo" in estados:
        diagnostico.estado_global = "rojo"
    elif "amarillo" in estados:
        diagnostico.estado_global = "amarillo"
    else:
        diagnostico.estado_global = "verde"

    diagnostico.total_alertas_rojas = sum(
        1 for h in hallazgos if h.severidad == "rojo")
    diagnostico.total_alertas_amarillas = sum(
        1 for h in hallazgos if h.severidad == "amarillo")

    await db.flush()
    return diagnostico
