"""
Modulo de Contabilidad -- Gestix
Tablas en schema del tenant.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text,
    DateTime, Date, JSON, ForeignKey, CHAR, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.database import Base


# -----------------------------------------
# CAPA 1: PLAN DE CUENTAS PCGE
# -----------------------------------------

class CuentaContable(Base):
    """
    Plan de Cuentas General Empresarial (PCGE) peruano.
    Precargado con cuentas estandar.
    Permite alias y personalizacion sin alterar codigo oficial.
    """
    __tablename__ = "cont_cuentas"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(10), nullable=False, unique=True, index=True)

    nombre_oficial = Column(String(200), nullable=False)
    alias = Column(String(200))
    nivel = Column(Integer, nullable=False)

    id_padre = Column(Integer, ForeignKey("cont_cuentas.id"), nullable=True)

    naturaleza = Column(String(10))
    tipo = Column(String(20))

    acepta_movimiento = Column(Boolean, default=True)

    aplica_ventas = Column(Boolean, default=False)
    aplica_compras = Column(Boolean, default=False)
    aplica_caja = Column(Boolean, default=False)
    aplica_planilla = Column(Boolean, default=False)

    activo = Column(Boolean, default=True)
    es_pcge_oficial = Column(Boolean, default=True)

    hijos = relationship(
        "CuentaContable",
        primaryjoin="CuentaContable.id_padre == CuentaContable.id",
        foreign_keys="[CuentaContable.id_padre]",
        back_populates="padre_rel",
    )
    padre_rel = relationship(
        "CuentaContable",
        primaryjoin="CuentaContable.id_padre == CuentaContable.id",
        foreign_keys="[CuentaContable.id_padre]",
        back_populates="hijos",
        remote_side="[CuentaContable.id]",
    )


# -----------------------------------------
# CAPA 1: ASIENTOS CONTABLES
# -----------------------------------------

class AsientoContable(Base):
    """
    Asiento contable. Puede ser automatico (generado desde ventas/compras)
    o manual (ingresado por el contador).
    """
    __tablename__ = "cont_asientos"

    id = Column(Integer, primary_key=True)
    numero = Column(Integer, index=True)
    periodo = Column(String(7), nullable=False, index=True)

    fecha = Column(Date, nullable=False, index=True)
    glosa = Column(String(300), nullable=False)

    origen = Column(String(20), default="manual")
    origen_tabla = Column(String(30))
    origen_id = Column(Integer)
    origen_codigo = Column(String(30))

    total_debe = Column(Numeric(16, 2), default=0)
    total_haber = Column(Numeric(16, 2), default=0)

    moneda = Column(String(3), default="PEN")
    tipo_cambio = Column(Numeric(8, 4), default=1)

    estado = Column(String(15), default="borrador")

    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    partidas = relationship("PartidaContable", back_populates="asiento",
                           cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_asiento_periodo_fecha", "periodo", "fecha"),
    )


class PartidaContable(Base):
    """Linea de debito o credito del asiento."""
    __tablename__ = "cont_partidas"

    id = Column(Integer, primary_key=True)
    id_asiento = Column(Integer,
        ForeignKey("cont_asientos.id", ondelete="CASCADE"))

    id_cuenta = Column(Integer, ForeignKey("cont_cuentas.id"))
    codigo_cuenta = Column(String(10))
    nombre_cuenta = Column(String(200))

    debe = Column(Numeric(16, 2), default=0)
    haber = Column(Numeric(16, 2), default=0)

    glosa_partida = Column(String(200))

    id_cliente = Column(Integer, nullable=True)
    id_proveedor = Column(Integer, nullable=True)
    id_empleado = Column(Integer, nullable=True)
    centro_costo = Column(String(50), nullable=True)

    asiento = relationship("AsientoContable", back_populates="partidas")
    cuenta = relationship("CuentaContable")


# -----------------------------------------
# CAPA 1: CONFIGURACION CONTABLE
# -----------------------------------------

class ConfigContable(Base):
    """
    Mapeo de cuentas para asientos automaticos.
    Define que cuenta usar en cada tipo de operacion.
    """
    __tablename__ = "cont_config"

    id = Column(Integer, primary_key=True)
    concepto = Column(String(50), unique=True, nullable=False)

    id_cuenta = Column(Integer, ForeignKey("cont_cuentas.id"))
    codigo_cuenta = Column(String(10))
    descripcion = Column(String(200))

    cuenta = relationship("CuentaContable")


# -----------------------------------------
# CAPA 1: LIBROS ELECTRONICOS (PLE)
# -----------------------------------------

class LibroElectronico(Base):
    """
    Registro de libros electronicos generados para SUNAT.
    """
    __tablename__ = "cont_libros_electronicos"

    id = Column(Integer, primary_key=True)
    tipo = Column(String(20), nullable=False)

    periodo = Column(String(7), nullable=False)
    ruc = Column(String(11))
    nombre_archivo = Column(String(200))
    contenido = Column(Text)
    hash_md5 = Column(String(32))

    estado = Column(String(15), default="generado")

    fecha_generacion = Column(DateTime, default=datetime.now)
    fecha_envio = Column(DateTime, nullable=True)
    respuesta_sunat = Column(Text, nullable=True)

    id_usuario = Column(Integer)


# -----------------------------------------
# CAPA 2: CRUCE CON SIRE
# -----------------------------------------

class RegistroSIRE(Base):
    """
    Registro de comprobantes importados desde SUNAT SIRE.
    Se cruza con lo registrado en Gestix para detectar diferencias.
    """
    __tablename__ = "cont_sire_registros"

    id = Column(Integer, primary_key=True)
    periodo = Column(String(7), nullable=False, index=True)
    tipo = Column(String(10))

    tipo_doc = Column(String(2))
    serie = Column(String(4))
    numero = Column(String(8))
    fecha_emision = Column(Date)
    ruc_contraparte = Column(String(11))
    nombre_contraparte = Column(String(200))
    base_imponible = Column(Numeric(14, 2), default=0)
    igv = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), default=0)
    estado_cpe = Column(String(20))

    estado_cruce = Column(String(20), default="pendiente")

    id_documento_gestix = Column(Integer, nullable=True)
    diferencia_monto = Column(Numeric(14, 2), nullable=True)
    observacion_cruce = Column(Text, nullable=True)

    importado_en = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("ix_sire_periodo_tipo", "periodo", "tipo"),
    )


# -----------------------------------------
# CAPA 2: NOTIFICACIONES BANCARIAS
# -----------------------------------------

class NotificacionBancaria(Base):
    """
    Movimientos bancarios importados desde correos de notificacion.
    Se cruza con ventas y compras de Gestix.
    """
    __tablename__ = "cont_notif_bancarias"

    id = Column(Integer, primary_key=True)
    id_cuenta_bancaria = Column(Integer, nullable=True)
    banco = Column(String(50))
    numero_cuenta = Column(String(30))

    fecha = Column(Date, nullable=False, index=True)
    tipo = Column(String(10))
    monto = Column(Numeric(14, 2), nullable=False)
    moneda = Column(String(3), default="PEN")
    descripcion = Column(String(300))
    referencia = Column(String(100))

    origen = Column(String(20), default="email")

    estado_cruce = Column(String(20), default="pendiente")
    id_venta = Column(Integer, nullable=True)
    id_compra = Column(Integer, nullable=True)
    observacion = Column(Text, nullable=True)

    importado_en = Column(DateTime, default=datetime.now)


# -----------------------------------------
# CAPA 2: DECLARACIONES TRIBUTARIAS
# -----------------------------------------

class DeclaracionTributaria(Base):
    """
    Registro de declaraciones mensuales (PDT 621, planilla, etc.)
    """
    __tablename__ = "cont_declaraciones"

    id = Column(Integer, primary_key=True)
    periodo = Column(String(7), nullable=False, index=True)
    tipo = Column(String(20), nullable=False)

    base_ventas = Column(Numeric(14, 2), default=0)
    igv_ventas = Column(Numeric(14, 2), default=0)
    base_compras = Column(Numeric(14, 2), default=0)
    igv_compras = Column(Numeric(14, 2), default=0)
    igv_a_pagar = Column(Numeric(14, 2), default=0)

    renta_a_pagar = Column(Numeric(14, 2), default=0)
    coeficiente_renta = Column(Numeric(6, 4), default=0)

    estado = Column(String(15), default="borrador")

    fecha_vencimiento = Column(Date)
    fecha_presentacion = Column(Date, nullable=True)
    fecha_pago = Column(Date, nullable=True)
    monto_pagado = Column(Numeric(14, 2), default=0)
    numero_orden_pago = Column(String(20))

    observaciones = Column(Text)
    datos_calculo = Column(JSON)

    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


# -----------------------------------------
# CAPA 3: SCAN / DIAGNOSTICO
# -----------------------------------------

class DiagnosticoEmpresa(Base):
    """
    Resultado del SCAN periodico de la empresa.
    Semaforo: verde / amarillo / rojo por area.
    """
    __tablename__ = "cont_diagnosticos"

    id = Column(Integer, primary_key=True)
    periodo = Column(String(7), nullable=False, index=True)
    fecha_scan = Column(DateTime, default=datetime.now)

    estado_global = Column(String(10), default="verde")

    estado_ventas = Column(String(10), default="verde")
    estado_compras = Column(String(10), default="verde")
    estado_tributario = Column(String(10), default="verde")
    estado_laboral = Column(String(10), default="verde")
    estado_bancario = Column(String(10), default="verde")
    estado_inventario = Column(String(10), default="verde")

    total_alertas_rojas = Column(Integer, default=0)
    total_alertas_amarillas = Column(Integer, default=0)
    resumen = Column(Text)

    id_usuario = Column(Integer)

    hallazgos = relationship("HallazgoDiagnostico",
                            back_populates="diagnostico",
                            cascade="all, delete-orphan")


class HallazgoDiagnostico(Base):
    """
    Hallazgo especifico del SCAN.
    Indica que falta, como conseguirlo, quien debe darlo.
    """
    __tablename__ = "cont_hallazgos"

    id = Column(Integer, primary_key=True)
    id_diagnostico = Column(Integer,
        ForeignKey("cont_diagnosticos.id", ondelete="CASCADE"))

    area = Column(String(20))
    severidad = Column(String(10))
    codigo = Column(String(30))

    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text)

    que_falta = Column(Text)
    como_conseguir = Column(Text)
    quien_debe_dar = Column(Text)
    quien_es_responsable = Column(Text)

    accion_sugerida = Column(String(300))
    url_accion = Column(String(200))

    resuelto = Column(Boolean, default=False)
    fecha_resolucion = Column(DateTime, nullable=True)

    datos_adicionales = Column(JSON)

    diagnostico = relationship("DiagnosticoEmpresa",
                              back_populates="hallazgos")


# -----------------------------------------
# CAPA 2: CUENTAS BANCARIAS
# -----------------------------------------

class CuentaBancaria(Base):
    """Cuentas bancarias de la empresa."""
    __tablename__ = "cont_cuentas_bancarias"

    id = Column(Integer, primary_key=True)
    banco = Column(String(50), nullable=False)
    numero_cuenta = Column(String(30))
    nombre_cuenta = Column(String(200))
    moneda = Column(String(3), default="PEN")
    tipo = Column(String(20), default="corriente")
    email_notif = Column(String(100))
    saldo_actual = Column(Numeric(16, 2), default=0)
    saldo_fecha = Column(Date, nullable=True)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)

    movimientos = relationship("MovimientoBancario",
                               back_populates="cuenta",
                               cascade="all, delete-orphan")


class DominioBancario(Base):
    """
    Registro de dominios DKIM verificados por banco.
    Se aprende automaticamente + se precarga manualmente.
    """
    __tablename__ = "cont_dominios_bancarios"

    id = Column(Integer, primary_key=True)
    dominio = Column(String(200), unique=True, nullable=False, index=True)
    banco = Column(String(50), nullable=False)

    estado = Column(String(20), default="nuevo")
    fuente = Column(String(30), default="automatico")

    primera_vez = Column(DateTime, default=datetime.now)
    ultima_vez = Column(DateTime, default=datetime.now)
    total_correos = Column(Integer, default=0)
    total_hoy = Column(Integer, default=0)
    fecha_conteo_hoy = Column(Date, default=date.today)

    nota = Column(Text, nullable=True)
    revisado_por = Column(Integer, nullable=True)
    revisado_en = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class CorreoSospechoso(Base):
    """
    Correos que no pasaron DKIM o tienen dominio desconocido.
    Se guardan para revision manual.
    """
    __tablename__ = "cont_correos_sospechosos"

    id = Column(Integer, primary_key=True)

    from_addr = Column(String(300))
    asunto = Column(String(300))
    fecha_correo = Column(DateTime)
    dominio_dkim = Column(String(200), nullable=True)
    dkim_resultado = Column(String(20))
    spf_resultado = Column(String(20), nullable=True)
    auth_results_raw = Column(Text, nullable=True)

    razon = Column(String(50))
    descripcion_razon = Column(Text)
    cuerpo_preview = Column(Text, nullable=True)

    revisado = Column(Boolean, default=False)
    revision_accion = Column(String(20), nullable=True)
    revisado_por = Column(Integer, nullable=True)
    revisado_en = Column(DateTime, nullable=True)
    nota_revision = Column(Text, nullable=True)

    email_mensaje_id = Column(String(200), unique=True, nullable=True)
    importado_en = Column(DateTime, default=datetime.now)


class MovimientoBancario(Base):
    """Movimiento bancario extraido de notificacion por correo."""
    __tablename__ = "cont_movimientos_bancarios"

    id = Column(Integer, primary_key=True)
    id_cuenta = Column(Integer,
        ForeignKey("cont_cuentas_bancarias.id"), nullable=True)

    banco = Column(String(50), index=True)
    fecha = Column(Date, nullable=False, index=True)
    hora = Column(String(8), nullable=True)
    tipo = Column(String(10), nullable=False)

    monto = Column(Numeric(14, 2), nullable=False)
    moneda = Column(String(3), default="PEN")
    descripcion = Column(String(500))
    referencia = Column(String(100))
    numero_operacion = Column(String(50))
    saldo_posterior = Column(Numeric(14, 2), nullable=True)

    tipo_operacion = Column(String(20))

    nombre_contraparte = Column(String(200))
    celular_contraparte = Column(String(15))

    confianza = Column(String(20), default="alta")

    origen = Column(String(20), default="email")
    email_mensaje_id = Column(String(200))
    email_asunto = Column(String(300))
    email_fecha = Column(DateTime)
    dominio_dkim = Column(String(200))

    estado_cruce = Column(String(20), default="pendiente")

    id_venta = Column(Integer, nullable=True)
    id_compra = Column(Integer, nullable=True)
    diferencia_monto = Column(Numeric(14, 2), nullable=True)
    nota_cruce = Column(Text, nullable=True)
    cruzado_en = Column(DateTime, nullable=True)
    id_usuario_cruzo = Column(Integer, nullable=True)

    importado_en = Column(DateTime, default=datetime.now)

    cuenta = relationship("CuentaBancaria", back_populates="movimientos")

    __table_args__ = (
        Index("ix_movbanco_fecha_banco", "fecha", "banco"),
        Index("ix_movbanco_estado", "estado_cruce"),
    )


class ValidacionPago(Base):
    """
    Registro de cada validacion de pago Yape/Plin/Transferencia
    realizada desde el POS mediante foto del comprobante del cliente.
    """
    __tablename__ = "cont_validaciones_pago"

    id = Column(Integer, primary_key=True)

    id_pedido = Column(Integer, nullable=True)
    id_punto_venta = Column(Integer, nullable=True)
    id_usuario = Column(Integer, nullable=True)

    foto_url = Column(String(500), nullable=True)

    numero_operacion_ocr = Column(String(50), nullable=True)
    monto_ocr = Column(Numeric(14, 2), nullable=True)
    banco_ocr = Column(String(50), nullable=True)
    texto_ocr_completo = Column(Text, nullable=True)

    estado = Column(String(20), default="pendiente")
    # pendiente | confirmado | rechazado | no_encontrado | manual

    id_movimiento_bancario = Column(Integer, nullable=True)
    diferencia_monto = Column(Numeric(14, 2), nullable=True)
    nota = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    confirmado_en = Column(DateTime, nullable=True)
    tiempo_respuesta_seg = Column(Integer, nullable=True)
