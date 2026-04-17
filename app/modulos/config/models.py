"""
Modelos del módulo de Configuración de Gestix.
Todas las tablas viven en el schema del tenant.
Diseñado para crecer: cada grupo de configuración es una tabla independiente.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text,
    DateTime, Date, JSON, ForeignKey, CHAR
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


# ─────────────────────────────────────────────
# 1. EMPRESA
# ─────────────────────────────────────────────

class ConfigEmpresa(Base):
    """Datos generales de la empresa del tenant."""
    __tablename__ = "cfg_empresa"

    id = Column(Integer, primary_key=True)

    # Datos fiscales
    ruc = Column(String(11), nullable=False)
    razon_social = Column(String(200), nullable=False)
    nombre_comercial = Column(String(200))
    direccion = Column(String(200))
    ubigeo = Column(CHAR(6))
    ubigeo_nombre = Column(String(100))
    telefono = Column(String(30))
    correo = Column(String(100))
    web = Column(String(100))
    logo_url = Column(String(300))          # GCS URL

    # Rubro
    id_rubro = Column(Integer)
    actividad_economica = Column(String(100))
    ciiu = Column(String(10))               # Código CIIU SUNAT

    # Representante legal
    rep_legal_nombre = Column(String(100))
    rep_legal_dni = Column(String(8))
    rep_legal_cargo = Column(String(50))

    # Contador
    contador_nombre = Column(String(100))
    contador_dni = Column(String(8))
    contador_colegiatura = Column(String(20))
    contador_correo = Column(String(100))
    contador_celular = Column(String(12))

    # Geolocalización
    gps_lat = Column(Numeric(10, 7))
    gps_lon = Column(Numeric(10, 7))
    gps_radio_metros = Column(Integer, default=500)

    # Auditoría
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by = Column(Integer)


# ─────────────────────────────────────────────
# 2. FACTURACIÓN ELECTRÓNICA
# ─────────────────────────────────────────────

class ConfigFacturacion(Base):
    """Configuración de facturación electrónica."""
    __tablename__ = "cfg_facturacion"

    id = Column(Integer, primary_key=True)

    # Proveedor
    proveedor = Column(String(30), default="facturalo.pro")
    # facturalo.pro | nubefact | efact | sunat_direct | otro
    api_url = Column(String(200))
    api_key = Column(String(200))
    api_secret = Column(String(200))

    # Credenciales SOL
    sol_usuario = Column(String(20))        # usuario secundario SOL
    sol_clave = Column(String(100))
    sol_ruc = Column(String(11))

    # Certificado digital
    cert_filename = Column(String(200))     # nombre en GCS
    cert_url = Column(String(300))          # GCS URL
    cert_password = Column(String(100))
    cert_vencimiento = Column(Date)

    # Entorno
    entorno = Column(String(10), default="beta")    # beta | produccion
    activo = Column(Boolean, default=False)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by = Column(Integer)

    series = relationship("ConfigSerie", back_populates="facturacion",
                         cascade="all, delete-orphan")


class ConfigSerie(Base):
    """Series de documentos (F001, B001, FC01, etc.)"""
    __tablename__ = "cfg_series"

    id = Column(Integer, primary_key=True)
    id_facturacion = Column(Integer, ForeignKey("cfg_facturacion.id"))

    tipo_doc = Column(String(2))            # 01=Factura, 03=Boleta, 07=NC, 08=ND, 09=GRE
    tipo_doc_nombre = Column(String(30))
    serie = Column(CHAR(4))                 # F001, B001, FC01...
    correlativo = Column(Integer, default=0)
    activo = Column(Boolean, default=True)

    facturacion = relationship("ConfigFacturacion", back_populates="series")


# ─────────────────────────────────────────────
# 3. IMPUESTOS Y PARÁMETROS TRIBUTARIOS
# ─────────────────────────────────────────────

class ConfigImpuestos(Base):
    """Parámetros tributarios vigentes."""
    __tablename__ = "cfg_impuestos"

    id = Column(Integer, primary_key=True)

    igv = Column(Numeric(5, 2), default=18.00)
    icbper = Column(Numeric(5, 2), default=0.50)        # impuesto bolsas plásticas
    isc_activo = Column(Boolean, default=False)

    # ISC
    isc_tasa_default = Column(Numeric(6, 2), default=0)

    # Interés moratorio
    tasa_interes_moratorio = Column(Numeric(6, 4), default=1.2)  # TIM SUNAT (% mensual)

    # Multas SUNAT (% de UIT o % de tributo omitido)
    multa_no_declarar = Column(Numeric(6, 2), default=100)
    multa_declarar_cero = Column(Numeric(6, 2), default=50)
    multa_omision_igv = Column(Numeric(6, 2), default=50)
    multa_omision_renta = Column(Numeric(6, 2), default=50)
    multa_no_emitir_cpe = Column(Numeric(6, 2), default=25)

    # Régimen de gradualidad
    gradualidad_subsanacion_voluntaria = Column(Numeric(5, 2), default=95)
    gradualidad_con_requerimiento = Column(Numeric(5, 2), default=70)

    percepcion_activo = Column(Boolean, default=False)
    percepcion_tasa = Column(Numeric(5, 2), default=2.00)

    retencion_activo = Column(Boolean, default=False)
    retencion_tasa = Column(Numeric(5, 2), default=3.00)

    renta_4ta = Column(Numeric(5, 2), default=8.00)
    renta_5ta = Column(Numeric(5, 2), default=8.00)
    renta_liqcom = Column(Numeric(5, 2), default=1.50)

    # Pagos a cuenta renta 3ra categoría
    pago_cuenta_metodo = Column(String(10), default="coef")  # coef | porcentaje
    pago_cuenta_coeficiente = Column(Numeric(6, 4), default=0.0000)
    pago_cuenta_porcentaje = Column(Numeric(5, 2), default=1.50)

    uit = Column(Numeric(10, 2), default=5350.00)
    vigencia_desde = Column(Date)

    exonerado_igv = Column(Boolean, default=False)
    zona = Column(String(50), nullable=True)
    # amazonia | costa | sierra | selva

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by = Column(Integer)


# ─────────────────────────────────────────────
# 4. PUNTOS DE VENTA
# ─────────────────────────────────────────────

class ConfigPuntoVenta(Base):
    """Configuración de cada terminal/caja/punto de venta."""
    __tablename__ = "cfg_puntos_venta"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(50), nullable=False)
    codigo = Column(String(10), unique=True)
    activo = Column(Boolean, default=True)

    # Almacén y series
    id_almacen = Column(Integer)
    serie_factura = Column(CHAR(4))
    serie_boleta = Column(CHAR(4))
    serie_nota_credito = Column(CHAR(4))
    serie_guia = Column(CHAR(4))

    # Modo de operación
    modo = Column(String(20), default="caja_completa")
    # caja_completa | solo_pedidos | pedidos_con_codigo

    # Comportamiento
    requiere_apertura_caja = Column(Boolean, default=True)
    pin_por_venta = Column(Boolean, default=False)      # pedir PIN del vendedor
    venta_sin_stock = Column(Boolean, default=False)
    permite_descuento = Column(Boolean, default=True)
    descuento_max = Column(Numeric(5, 2), default=10.00)
    permite_credito = Column(Boolean, default=True)

    # Anulación
    permite_anular_venta = Column(Boolean, default=False)
    permite_anular_pedido = Column(Boolean, default=True)
    requiere_motivo_anulacion = Column(Boolean, default=True)
    minutos_max_anulacion = Column(Integer, default=0)  # 0 = sin límite

    # Impresión
    impresora_tipo = Column(String(10))     # termica | pdf | ninguna
    impresora_ip = Column(String(20))
    impresora_puerto = Column(Integer, default=9100)
    impresora_ancho = Column(Integer, default=80)   # mm

    # Geolocalización (para acceso móvil)
    gps_lat = Column(Numeric(10, 7))
    gps_lon = Column(Numeric(10, 7))
    gps_radio_metros = Column(Integer, default=200)
    gps_accion = Column(String(10), default="advertir")
    # bloquear | advertir | registrar

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by = Column(Integer)


# ─────────────────────────────────────────────
# 5. LISTAS DE PRECIOS
# ─────────────────────────────────────────────

class ConfigListaPrecio(Base):
    """Tipos de lista de precio (minorista, mayorista, distribuidor, etc.)"""
    __tablename__ = "cfg_listas_precio"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(50), nullable=False)
    codigo = Column(String(10))
    descripcion = Column(String(100))
    es_default = Column(Boolean, default=False)
    activo = Column(Boolean, default=True)
    orden = Column(Integer, default=0)

    # Condiciones automáticas de asignación
    monto_minimo = Column(Numeric(12, 2))   # asignar si compra >= este monto
    requiere_aprobacion = Column(Boolean, default=False)


class ConfigPrecioEscalonado(Base):
    """Precios por cantidad (ej: 1-11 un. = S/10, 12+ = S/8.50)"""
    __tablename__ = "cfg_precios_escalonados"

    id = Column(Integer, primary_key=True)
    id_producto = Column(Integer, nullable=False)
    id_lista = Column(Integer, ForeignKey("cfg_listas_precio.id"))
    cantidad_desde = Column(Numeric(12, 3), nullable=False)
    cantidad_hasta = Column(Numeric(12, 3))     # NULL = sin límite
    precio = Column(Numeric(12, 4), nullable=False)
    activo = Column(Boolean, default=True)


# ─────────────────────────────────────────────
# 6a. RESPONSABLES ESPECIALES
# ─────────────────────────────────────────────

class ConfigResponsable(Base):
    __tablename__ = "cfg_responsables"

    id = Column(Integer, primary_key=True)

    dni = Column(String(8), nullable=False, index=True)
    nombres = Column(String(100))
    apellidos = Column(String(100))

    cargo = Column(String(50))
    celular = Column(String(12))
    celular2 = Column(String(12))
    correo = Column(String(100))
    correo_notificaciones_banco = Column(String(100))

    puede_abrir_local = Column(Boolean, default=False)
    puede_cerrar_local = Column(Boolean, default=False)
    puede_anular_ventas = Column(Boolean, default=False)
    puede_dar_descuentos_especiales = Column(Boolean, default=False)
    puede_ver_costos = Column(Boolean, default=False)
    recibe_alertas_sunat = Column(Boolean, default=False)
    recibe_alertas_sunafil = Column(Boolean, default=False)
    recibe_alertas_municipio = Column(Boolean, default=False)
    recibe_alertas_stock = Column(Boolean, default=False)
    recibe_alertas_caja = Column(Boolean, default=False)
    recibe_notificaciones_bancarias = Column(Boolean, default=False)

    activo = Column(Boolean, default=True)
    es_representante_legal = Column(Boolean, default=False)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# ─────────────────────────────────────────────
# 6b. MEDIOS DE COBRO
# ─────────────────────────────────────────────

class ConfigCuentaBancaria(Base):
    """Cuentas bancarias del negocio."""
    __tablename__ = "cfg_cuentas_bancarias"

    id = Column(Integer, primary_key=True)
    banco = Column(String(50), nullable=False)
    codigo_sunat = Column(String(10))
    numero_cuenta = Column(String(30), nullable=False)
    cci = Column(String(20))
    moneda = Column(String(3), default="PEN")
    titular = Column(String(100))
    activo = Column(Boolean, default=True)
    mostrar_en_comprobante = Column(Boolean, default=True)

    correo_notificaciones = Column(String(200))
    correo_notificaciones2 = Column(String(200))
    notificaciones_activo = Column(Boolean, default=False)


class ConfigBilleteraDigital(Base):
    """Billeteras digitales (Yape, Plin, etc.)"""
    __tablename__ = "cfg_billeteras"

    id = Column(Integer, primary_key=True)
    tipo = Column(String(20), nullable=False)   # yape | plin | tunki | otro
    nombre = Column(String(50))
    numero = Column(String(15))
    titular = Column(String(100))
    qr_url = Column(String(300))                # GCS URL del QR
    id_responsable = Column(Integer, ForeignKey("cfg_responsables.id"), nullable=True)
    activo = Column(Boolean, default=True)
    mostrar_en_comprobante = Column(Boolean, default=True)


class ConfigMedioCobro(Base):
    """Medios de cobro habilitados en el POS."""
    __tablename__ = "cfg_medios_cobro"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(50), nullable=False)
    tipo = Column(String(20), nullable=False)
    # efectivo | tarjeta | yape | plin | transferencia | credito | otro
    activo = Column(Boolean, default=True)
    requiere_referencia = Column(Boolean, default=False)
    icono = Column(String(50))


# ─────────────────────────────────────────────
# 7. ALMACENES
# ─────────────────────────────────────────────

class ConfigAlmacen(Base):
    """Almacenes del negocio."""
    __tablename__ = "cfg_almacenes"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(10), unique=True)
    nombre = Column(String(100), nullable=False)
    direccion = Column(String(200))
    ubigeo = Column(CHAR(6))
    responsable = Column(String(100))
    tipo = Column(String(20), default="principal")
    # principal | transito | consignacion | produccion
    controla_stock = Column(Boolean, default=True)
    activo = Column(Boolean, default=True)

    id_responsable = Column(Integer, ForeignKey("cfg_responsables.id"), nullable=True)

    gps_lat = Column(Numeric(10, 7))
    gps_lon = Column(Numeric(10, 7))

    # Coordenadas operativas (conteos e inventarios)
    gps_lat_op = Column(Numeric(10, 7))
    gps_lon_op = Column(Numeric(10, 7))
    gps_radio_op_metros = Column(Integer, default=50)


# ─────────────────────────────────────────────
# 8. PERSONAL Y PLANILLAS
# ─────────────────────────────────────────────

class ConfigRegimen(Base):
    """Régimen laboral del negocio."""
    __tablename__ = "cfg_regimen_laboral"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(50))
    # General | MYPE | Microempresa | Agrario | Doméstico
    gratificacion = Column(Boolean, default=True)
    cts = Column(Boolean, default=True)
    essalud_tasa = Column(Numeric(5, 2), default=9.00)
    vacaciones_dias = Column(Integer, default=30)
    activo = Column(Boolean, default=True)


class ConfigTrabajador(Base):
    """Trabajadores del negocio."""
    __tablename__ = "cfg_trabajadores"

    id = Column(Integer, primary_key=True)
    dni = Column(String(8), nullable=False, index=True)
    nombres = Column(String(100))
    apellidos = Column(String(100))
    cargo = Column(String(50))
    area = Column(String(50))

    # Contrato
    id_regimen = Column(Integer, ForeignKey("cfg_regimen_laboral.id"))
    fecha_ingreso = Column(Date)
    fecha_cese = Column(Date)
    tipo_contrato = Column(String(20))  # indefinido | plazo_fijo | practicas
    activo = Column(Boolean, default=True)

    # Remuneración
    sueldo_base = Column(Numeric(10, 2), default=0)
    asignacion_familiar = Column(Boolean, default=False)
    movilidad = Column(Numeric(10, 2), default=0)

    # Previsión social
    sistema_pension = Column(String(5))     # afp | onp
    afp_nombre = Column(String(30))
    afp_cuspp = Column(String(12))
    afp_tasa = Column(Numeric(5, 4))

    # Acceso al sistema
    id_usuario_sistema = Column(Integer)
    es_vendedor = Column(Boolean, default=False)
    es_cajero = Column(Boolean, default=False)
    es_repartidor = Column(Boolean, default=False)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    regimen = relationship("ConfigRegimen")


# ─────────────────────────────────────────────
# 9. INTEGRACIONES EXTERNAS
# ─────────────────────────────────────────────

class ConfigIntegracion(Base):
    """Credenciales y configuración de integraciones externas."""
    __tablename__ = "cfg_integraciones"

    id = Column(Integer, primary_key=True)
    servicio = Column(String(30), unique=True, nullable=False)
    # sunat_sire | sunat_ple | whatsapp | gcs | openai |
    # openpay | niubiz | culqi | reniec_api | sunat_ruc_api

    activo = Column(Boolean, default=False)
    api_url = Column(String(200))
    api_key = Column(String(300))
    api_secret = Column(String(300))
    config_extra = Column(JSON)             # parámetros adicionales por servicio
    ultimo_test = Column(DateTime)
    test_exitoso = Column(Boolean)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by = Column(Integer)


# ─────────────────────────────────────────────
# 10. PREFERENCIAS DEL SISTEMA
# ─────────────────────────────────────────────

class ConfigPreferencias(Base):
    """Preferencias generales del sistema por tenant."""
    __tablename__ = "cfg_preferencias"

    id = Column(Integer, primary_key=True)

    # Apariencia
    tema = Column(String(10), default="oscuro")         # oscuro | claro
    idioma = Column(String(5), default="es-PE")
    zona_horaria = Column(String(50), default="America/Lima")
    formato_fecha = Column(String(20), default="DD/MM/YYYY")
    moneda_principal = Column(String(3), default="PEN")
    decimales_precio = Column(Integer, default=2)
    decimales_cantidad = Column(Integer, default=3)

    # Notificaciones
    push_activo = Column(Boolean, default=True)
    whatsapp_activo = Column(Boolean, default=False)
    email_activo = Column(Boolean, default=False)
    toast_posicion = Column(String(20), default="top-right")
    # top-right | top-left | bottom-right | bottom-left | top-center

    # Sonidos
    sonidos_activo = Column(Boolean, default=True)
    sonido_venta_ok = Column(String(100))
    sonido_error = Column(String(100))
    sonido_alerta = Column(String(100))

    # Comportamiento
    confirmar_antes_anular = Column(Boolean, default=True)
    requiere_motivo_descuento = Column(Boolean, default=False)
    mostrar_costo_en_venta = Column(Boolean, default=False)
    dias_alerta_vencimiento = Column(Integer, default=30)

    # Padrón RUC (actualización semanal desde SUNAT)
    padron_ruc_activo = Column(Boolean, default=True)
    padron_ruc_ultima_actualizacion = Column(DateTime)

    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by = Column(Integer)


# ─────────────────────────────────────────────
# 11. TIPOS DE CLIENTE
# ─────────────────────────────────────────────

class ConfigTipoCliente(Base):
    __tablename__ = "cfg_tipos_cliente"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(50), nullable=False)
    descripcion = Column(String(100))
    id_lista_precio = Column(Integer, ForeignKey("cfg_listas_precio.id"), nullable=True)
    descuento_max = Column(Numeric(5, 2), default=0)
    permite_credito = Column(Boolean, default=False)
    dias_credito_default = Column(Integer, default=0)
    limite_credito_default = Column(Numeric(12, 2), default=0)
    requiere_aprobacion = Column(Boolean, default=False)
    orden = Column(Integer, default=0)
    activo = Column(Boolean, default=True)

    lista_precio = relationship("ConfigListaPrecio")
