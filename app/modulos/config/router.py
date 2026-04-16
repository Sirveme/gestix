from decimal import Decimal
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.tenant import get_tenant_session
from app.modulos.config.models import (
    ConfigEmpresa, ConfigFacturacion, ConfigSerie, ConfigImpuestos,
    ConfigPuntoVenta, ConfigAlmacen, ConfigPreferencias,
    ConfigCuentaBancaria, ConfigBilleteraDigital,
    ConfigMedioCobro, ConfigIntegracion, ConfigTrabajador,
    ConfigRegimen, ConfigListaPrecio, ConfigResponsable, ConfigTipoCliente
)

router = APIRouter(prefix="/config", tags=["config"])
templates = Jinja2Templates(directory="templates")


def ctx(request: Request, **kwargs):
    """Context base para todos los templates de config."""
    return {
        "request": request,
        "nombre": getattr(request.state, "nombre", ""),
        "empresa_nombre": getattr(request.state, "empresa_nombre", ""),
        **kwargs
    }


@router.get("/", response_class=HTMLResponse)
async def config_home(request: Request):
    return templates.TemplateResponse("config/index.html", ctx(request))


# ── Empresa ──────────────────────────────────

@router.get("/empresa", response_class=HTMLResponse)
async def config_empresa_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(ConfigEmpresa).limit(1))
    empresa = result.scalar_one_or_none()
    return templates.TemplateResponse("config/empresa.html", ctx(request, empresa=empresa))


@router.post("/empresa", response_class=HTMLResponse)
async def config_empresa_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    result = await db.execute(select(ConfigEmpresa).limit(1))
    empresa = result.scalar_one_or_none()

    if not empresa:
        empresa = ConfigEmpresa()
        db.add(empresa)

    for campo in [
        "ruc", "razon_social", "nombre_comercial", "direccion", "ubigeo",
        "ubigeo_nombre", "telefono", "correo", "web",
        "rep_legal_nombre", "rep_legal_dni", "rep_legal_cargo",
        "contador_nombre", "contador_dni", "contador_colegiatura",
        "contador_correo", "contador_celular",
        "actividad_economica", "ciiu",
        "gps_lat", "gps_lon", "gps_radio_metros",
    ]:
        val = form.get(campo)
        if val is not None:
            setattr(empresa, campo, val or None)

    empresa.updated_by = getattr(request.state, "user_id", None)
    await db.commit()

    return templates.TemplateResponse(
        "config/empresa.html",
        ctx(request, empresa=empresa, toast="Datos de empresa guardados", toast_tipo="ok")
    )


# ── Impuestos ─────────────────────────────────

@router.get("/impuestos", response_class=HTMLResponse)
async def config_impuestos_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(ConfigImpuestos).limit(1))
    impuestos = result.scalar_one_or_none()
    return templates.TemplateResponse("config/impuestos.html", ctx(request, impuestos=impuestos))


@router.post("/impuestos", response_class=HTMLResponse)
async def config_impuestos_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    result = await db.execute(select(ConfigImpuestos).limit(1))
    imp = result.scalar_one_or_none()
    if not imp:
        imp = ConfigImpuestos()
        db.add(imp)

    for campo in ["igv", "icbper", "percepcion_tasa", "retencion_tasa",
                  "renta_4ta", "renta_5ta", "renta_liqcom",
                  "pago_cuenta_metodo", "pago_cuenta_coeficiente",
                  "pago_cuenta_porcentaje", "uit",
                  "isc_tasa_default", "tasa_interes_moratorio",
                  "multa_no_declarar", "multa_declarar_cero",
                  "multa_omision_igv", "multa_omision_renta",
                  "multa_no_emitir_cpe",
                  "gradualidad_subsanacion_voluntaria",
                  "gradualidad_con_requerimiento"]:
        val = form.get(campo)
        if val is not None:
            setattr(imp, campo, val or None)

    for bool_campo in ["isc_activo", "percepcion_activo", "retencion_activo"]:
        setattr(imp, bool_campo, form.get(bool_campo) == "on")

    await db.commit()
    return templates.TemplateResponse(
        "config/impuestos.html",
        ctx(request, impuestos=imp, toast="Impuestos actualizados", toast_tipo="ok")
    )


# ── Preferencias ──────────────────────────────

@router.get("/preferencias", response_class=HTMLResponse)
async def config_prefs_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(ConfigPreferencias).limit(1))
    prefs = result.scalar_one_or_none()
    return templates.TemplateResponse("config/preferencias.html", ctx(request, prefs=prefs))


@router.post("/preferencias", response_class=HTMLResponse)
async def config_prefs_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    result = await db.execute(select(ConfigPreferencias).limit(1))
    prefs = result.scalar_one_or_none()
    if not prefs:
        prefs = ConfigPreferencias()
        db.add(prefs)

    for campo in ["tema", "zona_horaria", "formato_fecha", "moneda_principal",
                  "decimales_precio", "decimales_cantidad", "toast_posicion",
                  "dias_alerta_vencimiento"]:
        val = form.get(campo)
        if val is not None:
            setattr(prefs, campo, val)

    for bool_campo in ["push_activo", "whatsapp_activo", "email_activo",
                       "sonidos_activo", "confirmar_antes_anular",
                       "requiere_motivo_descuento", "mostrar_costo_en_venta"]:
        setattr(prefs, bool_campo, form.get(bool_campo) == "on")

    await db.commit()
    return templates.TemplateResponse(
        "config/preferencias.html",
        ctx(request, prefs=prefs, toast="Preferencias guardadas", toast_tipo="ok")
    )


# ── Facturación ───────────────────────────────

@router.get("/facturacion", response_class=HTMLResponse)
async def config_facturacion_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(ConfigFacturacion).limit(1))
    fact = result.scalar_one_or_none()
    result2 = await db.execute(select(ConfigSerie).order_by(ConfigSerie.tipo_doc))
    series = result2.scalars().all()
    return templates.TemplateResponse("config/facturacion.html",
        ctx(request, fact=fact, series=series))


@router.post("/facturacion", response_class=HTMLResponse)
async def config_facturacion_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    result = await db.execute(select(ConfigFacturacion).limit(1))
    fact = result.scalar_one_or_none()
    if not fact:
        fact = ConfigFacturacion()
        db.add(fact)

    for campo in ["proveedor", "api_url", "api_key", "api_secret",
                  "sol_usuario", "sol_clave", "sol_ruc",
                  "cert_password", "entorno"]:
        val = form.get(campo)
        if val is not None:
            setattr(fact, campo, val or None)

    fact.activo = form.get("activo") == "on"
    fact.updated_by = getattr(request.state, "user_id", None)
    await db.commit()

    result2 = await db.execute(select(ConfigSerie).order_by(ConfigSerie.tipo_doc))
    series = result2.scalars().all()
    return templates.TemplateResponse("config/facturacion.html",
        ctx(request, fact=fact, series=series,
            toast="Configuración de facturación guardada", toast_tipo="ok"))


@router.post("/facturacion/serie", response_class=HTMLResponse)
async def config_serie_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    result = await db.execute(select(ConfigFacturacion).limit(1))
    fact = result.scalar_one_or_none()
    if not fact:
        fact = ConfigFacturacion()
        db.add(fact)
        await db.flush()

    serie = ConfigSerie(
        id_facturacion=fact.id,
        tipo_doc=form.get("tipo_doc"),
        tipo_doc_nombre=form.get("tipo_doc_nombre"),
        serie=form.get("serie"),
        correlativo=int(form.get("correlativo", 0)),
        activo=True,
    )
    db.add(serie)
    await db.commit()

    result2 = await db.execute(select(ConfigSerie).order_by(ConfigSerie.tipo_doc))
    series = result2.scalars().all()
    return templates.TemplateResponse("config/partials/series_list.html",
        ctx(request, series=series))


# ── Puntos de Venta ──────────────────────────

@router.get("/puntos-venta", response_class=HTMLResponse)
async def config_pv_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(ConfigPuntoVenta).order_by(ConfigPuntoVenta.nombre))
    pvs = result.scalars().all()
    return templates.TemplateResponse("config/puntos_venta.html", ctx(request, pvs=pvs))


@router.post("/puntos-venta", response_class=HTMLResponse)
async def config_pv_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    pv_id = form.get("id", "").strip()

    if pv_id:
        result = await db.execute(select(ConfigPuntoVenta).where(ConfigPuntoVenta.id == int(pv_id)))
        pv = result.scalar_one_or_none()
    else:
        pv = ConfigPuntoVenta()
        db.add(pv)

    for campo in ["nombre", "codigo", "modo", "serie_factura", "serie_boleta",
                  "serie_nota_credito", "serie_guia",
                  "impresora_tipo", "impresora_ip", "gps_accion"]:
        val = form.get(campo)
        if val is not None:
            setattr(pv, campo, val or None)

    for campo in ["minutos_max_anulacion", "impresora_puerto",
                  "impresora_ancho", "gps_radio_metros", "id_almacen"]:
        val = form.get(campo)
        if val is not None and val != '':
            setattr(pv, campo, int(val))
        else:
            setattr(pv, campo, None)

    for campo in ["descuento_max", "gps_lat", "gps_lon"]:
        val = form.get(campo)
        if val is not None and val != '':
            setattr(pv, campo, Decimal(val))
        else:
            setattr(pv, campo, None)

    for bool_campo in ["activo", "requiere_apertura_caja", "pin_por_venta",
                       "venta_sin_stock", "permite_descuento", "permite_credito",
                       "permite_anular_venta", "permite_anular_pedido",
                       "requiere_motivo_anulacion"]:
        setattr(pv, bool_campo, form.get(bool_campo) == "on")

    user_id = getattr(request.state, "user_id", None)
    pv.updated_by = int(user_id) if user_id else None
    await db.commit()

    return RedirectResponse(url="/config/puntos-venta", status_code=302)


# ── Listas de Precio ─────────────────────────

@router.get("/listas-precio", response_class=HTMLResponse)
async def config_listas_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(ConfigListaPrecio).order_by(ConfigListaPrecio.orden))
    listas = result.scalars().all()
    return templates.TemplateResponse("config/listas_precio.html", ctx(request, listas=listas))


@router.post("/listas-precio", response_class=HTMLResponse)
async def config_listas_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    lista_id = form.get("id", "").strip()

    if lista_id:
        result = await db.execute(select(ConfigListaPrecio).where(ConfigListaPrecio.id == int(lista_id)))
        lista = result.scalar_one_or_none()
    else:
        lista = ConfigListaPrecio()
        db.add(lista)

    for campo in ["nombre", "codigo", "descripcion", "orden", "monto_minimo"]:
        val = form.get(campo)
        if val is not None:
            setattr(lista, campo, val or None)

    for bool_campo in ["activo", "es_default", "requiere_aprobacion"]:
        setattr(lista, bool_campo, form.get(bool_campo) == "on")

    await db.commit()

    result = await db.execute(select(ConfigListaPrecio).order_by(ConfigListaPrecio.orden))
    listas = result.scalars().all()
    return templates.TemplateResponse("config/listas_precio.html",
        ctx(request, listas=listas, toast="Lista de precio guardada", toast_tipo="ok"))


# ── Medios de Cobro ───────────────────────────

@router.get("/cobros", response_class=HTMLResponse)
async def config_cobros_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    r1 = await db.execute(select(ConfigCuentaBancaria).order_by(ConfigCuentaBancaria.banco))
    r2 = await db.execute(select(ConfigBilleteraDigital).order_by(ConfigBilleteraDigital.tipo))
    r3 = await db.execute(select(ConfigMedioCobro).order_by(ConfigMedioCobro.nombre))
    return templates.TemplateResponse("config/cobros.html", ctx(request,
        cuentas=r1.scalars().all(),
        billeteras=r2.scalars().all(),
        medios=r3.scalars().all()))


@router.post("/cobros/cuenta", response_class=HTMLResponse)
async def config_cuenta_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    cuenta_id = form.get("id", "").strip()

    if cuenta_id:
        result = await db.execute(select(ConfigCuentaBancaria).where(ConfigCuentaBancaria.id == int(cuenta_id)))
        cuenta = result.scalar_one_or_none()
    else:
        cuenta = ConfigCuentaBancaria()
        db.add(cuenta)

    for campo in ["banco", "codigo_sunat", "numero_cuenta", "cci", "moneda", "titular",
                  "correo_notificaciones", "correo_notificaciones2"]:
        val = form.get(campo)
        if val is not None:
            setattr(cuenta, campo, val or None)

    for bool_campo in ["activo", "mostrar_en_comprobante", "notificaciones_activo"]:
        setattr(cuenta, bool_campo, form.get(bool_campo) == "on")

    await db.commit()

    r1 = await db.execute(select(ConfigCuentaBancaria).order_by(ConfigCuentaBancaria.banco))
    r2 = await db.execute(select(ConfigBilleteraDigital).order_by(ConfigBilleteraDigital.tipo))
    r3 = await db.execute(select(ConfigMedioCobro).order_by(ConfigMedioCobro.nombre))
    return templates.TemplateResponse("config/cobros.html", ctx(request,
        cuentas=r1.scalars().all(),
        billeteras=r2.scalars().all(),
        medios=r3.scalars().all(),
        toast="Cuenta bancaria guardada", toast_tipo="ok"))


@router.post("/cobros/billetera", response_class=HTMLResponse)
async def config_billetera_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    bill_id = form.get("id", "").strip()

    if bill_id:
        result = await db.execute(select(ConfigBilleteraDigital).where(ConfigBilleteraDigital.id == int(bill_id)))
        bill = result.scalar_one_or_none()
    else:
        bill = ConfigBilleteraDigital()
        db.add(bill)

    for campo in ["tipo", "nombre", "numero", "titular"]:
        val = form.get(campo)
        if val is not None:
            setattr(bill, campo, val or None)

    for bool_campo in ["activo", "mostrar_en_comprobante"]:
        setattr(bill, bool_campo, form.get(bool_campo) == "on")

    await db.commit()

    r1 = await db.execute(select(ConfigCuentaBancaria).order_by(ConfigCuentaBancaria.banco))
    r2 = await db.execute(select(ConfigBilleteraDigital).order_by(ConfigBilleteraDigital.tipo))
    r3 = await db.execute(select(ConfigMedioCobro).order_by(ConfigMedioCobro.nombre))
    return templates.TemplateResponse("config/cobros.html", ctx(request,
        cuentas=r1.scalars().all(),
        billeteras=r2.scalars().all(),
        medios=r3.scalars().all(),
        toast="Billetera digital guardada", toast_tipo="ok"))


# ── Almacenes ─────────────────────────────────

@router.get("/almacenes", response_class=HTMLResponse)
async def config_almacenes_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(ConfigAlmacen).order_by(ConfigAlmacen.nombre))
    almacenes = result.scalars().all()
    return templates.TemplateResponse("config/almacenes.html", ctx(request, almacenes=almacenes))


@router.post("/almacenes", response_class=HTMLResponse)
async def config_almacen_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    alm_id = form.get("id", "").strip()

    if alm_id:
        result = await db.execute(select(ConfigAlmacen).where(ConfigAlmacen.id == int(alm_id)))
        alm = result.scalar_one_or_none()
    else:
        alm = ConfigAlmacen()
        db.add(alm)

    for campo in ["codigo", "nombre", "direccion", "ubigeo", "responsable",
                  "tipo", "gps_lat", "gps_lon",
                  "gps_lat_op", "gps_lon_op", "gps_radio_op_metros"]:
        val = form.get(campo)
        if val is not None:
            setattr(alm, campo, val or None)

    for bool_campo in ["activo", "controla_stock"]:
        setattr(alm, bool_campo, form.get(bool_campo) == "on")

    await db.commit()

    result = await db.execute(select(ConfigAlmacen).order_by(ConfigAlmacen.nombre))
    almacenes = result.scalars().all()
    return templates.TemplateResponse("config/almacenes.html",
        ctx(request, almacenes=almacenes, toast="Almacén guardado", toast_tipo="ok"))


# ── Personal ──────────────────────────────────

@router.get("/personal", response_class=HTMLResponse)
async def config_personal_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    r1 = await db.execute(select(ConfigTrabajador).order_by(ConfigTrabajador.apellidos))
    r2 = await db.execute(select(ConfigRegimen).where(ConfigRegimen.activo == True))
    return templates.TemplateResponse("config/personal.html", ctx(request,
        trabajadores=r1.scalars().all(),
        regimenes=r2.scalars().all()))


@router.post("/personal", response_class=HTMLResponse)
async def config_personal_post(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    trab_id = form.get("id", "").strip()

    if trab_id:
        result = await db.execute(select(ConfigTrabajador).where(ConfigTrabajador.id == int(trab_id)))
        trab = result.scalar_one_or_none()
    else:
        trab = ConfigTrabajador()
        db.add(trab)

    for campo in ["dni", "nombres", "apellidos", "cargo", "area",
                  "id_regimen", "tipo_contrato", "fecha_ingreso", "fecha_cese",
                  "sueldo_base", "movilidad",
                  "sistema_pension", "afp_nombre", "afp_cuspp", "afp_tasa"]:
        val = form.get(campo)
        if val is not None:
            setattr(trab, campo, val or None)

    for bool_campo in ["activo", "asignacion_familiar",
                       "es_vendedor", "es_cajero", "es_repartidor"]:
        setattr(trab, bool_campo, form.get(bool_campo) == "on")

    await db.commit()

    r1 = await db.execute(select(ConfigTrabajador).order_by(ConfigTrabajador.apellidos))
    r2 = await db.execute(select(ConfigRegimen).where(ConfigRegimen.activo == True))
    return templates.TemplateResponse("config/personal.html", ctx(request,
        trabajadores=r1.scalars().all(),
        regimenes=r2.scalars().all(),
        toast="Trabajador guardado", toast_tipo="ok"))


# ── Integraciones ─────────────────────────────

@router.get("/integraciones", response_class=HTMLResponse)
async def config_integraciones_get(request: Request, db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(select(ConfigIntegracion).order_by(ConfigIntegracion.servicio))
    integraciones = result.scalars().all()

    servicios = [
        {"codigo": "facturalo_pro",  "nombre": "Facturalo.pro",         "desc": "Facturacion electronica integrada (recomendado)"},
        {"codigo": "sunat_sire",     "nombre": "SUNAT SIRE",            "desc": "Registro de ventas e ingresos electronico"},
        {"codigo": "sunat_ple",      "nombre": "SUNAT PLE",             "desc": "Programa de libros electronicos"},
        {"codigo": "sunat_ruc",      "nombre": "API Consulta RUC",      "desc": "Consulta de RUC en tiempo real"},
        {"codigo": "reniec",         "nombre": "API RENIEC / DNI",      "desc": "Consulta de DNI en tiempo real"},
        {"codigo": "whatsapp",       "nombre": "WhatsApp Business API", "desc": "Notificaciones y comprobantes por WhatsApp"},
        {"codigo": "gcs",            "nombre": "Google Cloud Storage",  "desc": "Almacenamiento de archivos y documentos"},
        {"codigo": "amazon_s3",      "nombre": "Amazon S3",             "desc": "Almacenamiento alternativo AWS"},
        {"codigo": "openai",         "nombre": "OpenAI",                "desc": "Asistente IA, comandos por voz, analisis"},
        {"codigo": "claude_api",     "nombre": "Claude API (Anthropic)", "desc": "IA avanzada para analisis y automatizacion"},
        {"codigo": "google_vision",  "nombre": "Google Vision API",     "desc": "OCR de documentos y vouchers"},
        {"codigo": "openpay",        "nombre": "OpenPay",               "desc": "Pagos con tarjeta"},
        {"codigo": "niubiz",         "nombre": "Niubiz",                "desc": "POS virtual Visa/Mastercard"},
        {"codigo": "culqi",          "nombre": "Culqi",                 "desc": "Pasarela de pagos peruana"},
        {"codigo": "bcp_api",        "nombre": "BCP — Notificaciones",  "desc": "Lectura de notificaciones de movimientos BCP"},
        {"codigo": "bbva_api",       "nombre": "BBVA — Notificaciones", "desc": "Lectura de notificaciones BBVA"},
        {"codigo": "interbank_api",  "nombre": "Interbank — Notificaciones", "desc": "Lectura de notificaciones Interbank"},
        {"codigo": "gestix_remote",  "nombre": "Gestix Remote Assist",  "desc": "Soporte tecnico remoto para este cliente"},
    ]

    integ_map = {i.servicio: i for i in integraciones}

    return templates.TemplateResponse("config/integraciones.html", ctx(request,
        servicios=servicios, integ_map=integ_map))


@router.post("/integraciones/{servicio}", response_class=HTMLResponse)
async def config_integracion_post(request: Request, servicio: str,
                                   db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    result = await db.execute(
        select(ConfigIntegracion).where(ConfigIntegracion.servicio == servicio))
    integ = result.scalar_one_or_none()

    if not integ:
        integ = ConfigIntegracion(servicio=servicio)
        db.add(integ)

    for campo in ["api_url", "api_key", "api_secret"]:
        val = form.get(campo)
        if val is not None:
            setattr(integ, campo, val or None)

    integ.activo = form.get("activo") == "on"
    integ.updated_by = getattr(request.state, "user_id", None)
    await db.commit()

    return HTMLResponse(f'<div class="toast toast-ok" id="toast-{servicio}">OK {servicio} guardado</div>')


# ── Responsables ─────────────────────────────

@router.get("/responsables", response_class=HTMLResponse)
async def config_responsables_get(request: Request,
                                   db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(ConfigResponsable).order_by(ConfigResponsable.apellidos))
    responsables = result.scalars().all()
    return templates.TemplateResponse("config/responsables.html",
        ctx(request, responsables=responsables))


@router.post("/responsables", response_class=HTMLResponse)
async def config_responsables_post(request: Request,
                                    db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    resp_id = form.get("id", "").strip()

    if resp_id:
        result = await db.execute(
            select(ConfigResponsable).where(ConfigResponsable.id == int(resp_id)))
        resp = result.scalar_one_or_none()
    else:
        resp = ConfigResponsable()
        db.add(resp)

    for campo in ["dni", "nombres", "apellidos", "cargo",
                  "celular", "celular2", "correo",
                  "correo_notificaciones_banco"]:
        val = form.get(campo)
        if val is not None:
            setattr(resp, campo, val or None)

    for bool_campo in [
        "activo", "es_representante_legal",
        "puede_abrir_local", "puede_cerrar_local",
        "puede_anular_ventas", "puede_dar_descuentos_especiales",
        "puede_ver_costos",
        "recibe_alertas_sunat", "recibe_alertas_sunafil",
        "recibe_alertas_municipio", "recibe_alertas_stock",
        "recibe_alertas_caja", "recibe_notificaciones_bancarias",
    ]:
        setattr(resp, bool_campo, form.get(bool_campo) == "on")

    await db.commit()

    result = await db.execute(
        select(ConfigResponsable).order_by(ConfigResponsable.apellidos))
    responsables = result.scalars().all()
    return templates.TemplateResponse("config/responsables.html",
        ctx(request, responsables=responsables,
            toast="Responsable guardado", toast_tipo="ok"))


@router.delete("/responsables/{id}")
async def config_responsable_delete(request: Request, id: int,
                                     db: AsyncSession = Depends(get_tenant_session)):
    result = await db.execute(
        select(ConfigResponsable).where(ConfigResponsable.id == id))
    resp = result.scalar_one_or_none()
    if resp:
        resp.activo = False
        await db.commit()
    return HTMLResponse('<div class="toast toast-ok">Responsable desactivado</div>')


# ── Tipos de Cliente ─────────────────────────

@router.get("/tipos-cliente", response_class=HTMLResponse)
async def config_tipos_cliente_get(request: Request,
                                    db: AsyncSession = Depends(get_tenant_session)):
    r1 = await db.execute(
        select(ConfigTipoCliente).order_by(ConfigTipoCliente.orden))
    tipos = r1.scalars().all()
    r2 = await db.execute(
        select(ConfigListaPrecio).where(ConfigListaPrecio.activo == True))
    listas = r2.scalars().all()
    return templates.TemplateResponse("config/tipos_cliente.html",
        ctx(request, tipos=tipos, listas=listas))


@router.post("/tipos-cliente", response_class=HTMLResponse)
async def config_tipos_cliente_post(request: Request,
                                     db: AsyncSession = Depends(get_tenant_session)):
    form = await request.form()
    tipo_id = form.get("id", "").strip()

    if tipo_id:
        result = await db.execute(
            select(ConfigTipoCliente).where(ConfigTipoCliente.id == int(tipo_id)))
        tipo = result.scalar_one_or_none()
    else:
        tipo = ConfigTipoCliente()
        db.add(tipo)

    for campo in ["nombre", "descripcion", "id_lista_precio",
                  "descuento_max", "dias_credito_default",
                  "limite_credito_default", "orden"]:
        val = form.get(campo)
        if val is not None:
            setattr(tipo, campo, val or None)

    for bool_campo in ["activo", "permite_credito", "requiere_aprobacion"]:
        setattr(tipo, bool_campo, form.get(bool_campo) == "on")

    await db.commit()

    r1 = await db.execute(
        select(ConfigTipoCliente).order_by(ConfigTipoCliente.orden))
    tipos = r1.scalars().all()
    r2 = await db.execute(
        select(ConfigListaPrecio).where(ConfigListaPrecio.activo == True))
    listas = r2.scalars().all()
    return templates.TemplateResponse("config/tipos_cliente.html",
        ctx(request, tipos=tipos, listas=listas,
            toast="Tipo de cliente guardado", toast_tipo="ok"))
