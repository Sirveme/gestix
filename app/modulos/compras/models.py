from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime, Numeric, Text,
    CHAR, ForeignKey, JSON, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class SgcAgendaProveedores(Base):
    __tablename__ = "sgc_agenda_proveedores"

    id_agenda_pro = Column(Integer, primary_key=True, index=True)
    nombre_pro = Column(String(100))
    direccion_pro = Column(String(100))
    ubigeo_nombre = Column(String(100))
    ubigeo = Column(String(6))
    referencia = Column(Text)
    celular = Column(String(10))
    celular2 = Column(String(10))
    email = Column(String(100))
    id_doc_ide = Column(Integer, ForeignKey("sgc_doc_identidad.id_doc_ide"))
    num_doc_ide = Column(String(12))
    id_forpag = Column(Integer, ForeignKey("sgc_forma_pago.id_forpag"))
    deuda_actual = Column(Numeric(18, 2), default=0)
    saldo_disponible = Column(Numeric(18, 2), default=0)
    nota = Column(Text)
    estado = Column(Boolean, default=True)
    fecha_inicio = Column(Date)
    id_usuario = Column(Integer)
    fhcontrol = Column(DateTime, default=datetime.now)
    estacion = Column(String(20))


class GuiaIngreso(Base):
    __tablename__ = "sgc_guia_ingreso"

    id_guia_ingreso = Column(Integer, primary_key=True, index=True)
    ruc = Column(String(12), nullable=True)
    id_agenda_pro = Column(Integer, default=0)
    id_docsunat = Column(Integer, default=0)
    serie = Column(CHAR(4), default="")
    numero = Column(String(8), default="")
    fecha_emision = Column(Date, default=datetime.utcnow)
    fecha_ingreso = Column(Date, default=datetime.utcnow)
    id_almacen = Column(Integer, default=0)
    id_operacion = Column(CHAR(2), default="")
    id_inventario = Column(Integer, default=0)
    glosa = Column(String(100), default="")
    id_almacen_sal = Column(Integer, default=0)
    serie_gr_salida = Column(CHAR(4), default="")
    numero_gr_salida = Column(String(8), default="")
    id_guia_salida = Column(Integer, default=0)
    serie_compra = Column(CHAR(4), default="")
    numero_compra = Column(String(8), default="")
    id_compra = Column(Integer, default=0)
    tc = Column(Numeric(18, 3), default=0)
    id_moneda = Column(Integer, default=0)
    mueve_costo_ = Column(Boolean, default=False)
    mueve_stock_ = Column(Boolean, default=False)
    igv_ = Column(Boolean, default=False)
    total_bruto = Column(Numeric(18, 2), default=0)
    descuento = Column(Numeric(18, 2), default=0)
    sub_total = Column(Numeric(18, 2), default=0)
    igv = Column(Numeric(18, 2), default=0)
    total = Column(Numeric(18, 2), default=0)
    id_empleado = Column(Integer, default=0)
    nota = Column(Text, default="")
    id_usuario = Column(Integer, default=0)
    fhcontrol = Column(DateTime, default=datetime.now)
    estacion = Column(String(20), default="")
    cerrado = Column(Boolean, default=False)

    detalles = relationship("GuiaIngresoDetalle", back_populates="guia_ingreso", cascade="all, delete-orphan")


class GuiaIngresoDetalle(Base):
    __tablename__ = "sgc_guia_ingreso_det"

    id_guia_ingreso_det = Column(Integer, primary_key=True, index=True)
    id_guia_ingreso = Column(Integer, ForeignKey("sgc_guia_ingreso.id_guia_ingreso", ondelete="CASCADE"), default=0)
    origen = Column(String(8), default="")
    id_producto = Column(Integer, default=0)
    codigo_producto = Column(String(20), default="")
    nombre_producto = Column(String(100), default="")
    unidad_precio = Column(String(12), default="")
    equivalente = Column(Numeric(18, 7), default=0)
    cantidad = Column(Numeric(18, 3), default=0)
    precio_compra = Column(Numeric(18, 2), default=0)
    precio_bruto = Column(Numeric(18, 2), default=0)
    descuento = Column(Numeric(18, 2), default=0)
    sub_total = Column(Numeric(18, 2), default=0)
    igv = Column(Numeric(18, 2), default=0)
    total = Column(Numeric(18, 2), default=0)
    bonificacion_ = Column(Boolean, default=False)
    fecha_vencimiento = Column(Date, nullable=True)
    lote = Column(String(12), default="")
    id_usuario = Column(Integer, default=0)
    fhcontrol = Column(DateTime, default=datetime.now)
    estacion = Column(String(20), default="")
    nota = Column(Text, default="")

    guia_ingreso = relationship("GuiaIngreso", back_populates="detalles")


# ─────────────────────────────────────────────
# NUEVO SISTEMA DE COMPRAS
# ─────────────────────────────────────────────

class OrdenCompra(Base):
    __tablename__ = "com_ordenes"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, index=True)
    id_proveedor = Column(Integer, nullable=True)
    nombre_proveedor = Column(String(200))
    ruc_proveedor = Column(String(11))
    fecha_emision = Column(Date, nullable=False, default=datetime.now)
    fecha_entrega_esperada = Column(Date, nullable=True)
    id_almacen_destino = Column(Integer, nullable=True)
    subtotal = Column(Numeric(14, 2), default=0)
    igv = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), default=0)
    estado = Column(String(20), default="borrador")
    nota = Column(Text)
    condiciones = Column(Text)
    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    items = relationship("OrdenCompraItem", back_populates="orden",
                        cascade="all, delete-orphan")
    compras = relationship("Compra", back_populates="orden")


class OrdenCompraItem(Base):
    __tablename__ = "com_orden_items"

    id = Column(Integer, primary_key=True)
    id_orden = Column(Integer, ForeignKey("com_ordenes.id", ondelete="CASCADE"))
    id_producto = Column(Integer, nullable=False)
    codigo_producto = Column(String(30))
    nombre_producto = Column(String(150))
    unidad = Column(String(20))
    cantidad_solicitada = Column(Numeric(14, 4), nullable=False)
    cantidad_recibida = Column(Numeric(14, 4), default=0)
    precio_unitario = Column(Numeric(14, 4), default=0)
    subtotal = Column(Numeric(14, 2), default=0)
    igv = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), default=0)
    nota = Column(String(200))

    orden = relationship("OrdenCompra", back_populates="items")


class Compra(Base):
    __tablename__ = "com_compras"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, index=True)
    id_orden = Column(Integer, ForeignKey("com_ordenes.id"), nullable=True)
    id_proveedor = Column(Integer, nullable=True)
    nombre_proveedor = Column(String(200))
    ruc_proveedor = Column(String(11))
    direccion_proveedor = Column(String(200))
    tipo_doc_sunat = Column(String(2))
    serie_doc = Column(CHAR(4))
    numero_doc = Column(String(8))
    fecha_emision_doc = Column(Date, nullable=False)
    fecha_vencimiento_doc = Column(Date, nullable=True)
    id_almacen = Column(Integer, nullable=True)
    subtotal = Column(Numeric(14, 2), default=0)
    igv = Column(Numeric(14, 2), default=0)
    otros_cargos = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), default=0)
    tipo_cambio = Column(Numeric(8, 4), default=1)
    moneda = Column(String(3), default="PEN")
    estado = Column(String(20), default="por_aprobar")
    id_aprobador = Column(Integer, nullable=True)
    nombre_aprobador = Column(String(100))
    fecha_aprobacion = Column(DateTime, nullable=True)
    observacion_aprobacion = Column(Text, nullable=True)
    documento_url = Column(String(300))
    documento_leido_por_ia = Column(Boolean, default=False)
    datos_ia = Column(JSON)
    kardex_registrado = Column(Boolean, default=False)
    id_usuario = Column(Integer)
    nota = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    orden = relationship("OrdenCompra", back_populates="compras")
    items = relationship("CompraItem", back_populates="compra",
                        cascade="all, delete-orphan")
    pagos = relationship("CompraPago", back_populates="compra",
                        cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_compra_fecha", "fecha_emision_doc"),
        Index("ix_compra_proveedor", "id_proveedor"),
        Index("ix_compra_estado", "estado"),
    )


class CompraItem(Base):
    __tablename__ = "com_compra_items"

    id = Column(Integer, primary_key=True)
    id_compra = Column(Integer, ForeignKey("com_compras.id", ondelete="CASCADE"))
    id_producto = Column(Integer, nullable=True)
    codigo_producto = Column(String(30))
    nombre_producto = Column(String(150))
    unidad = Column(String(20))
    equivalente = Column(Numeric(12, 4), default=1)
    cantidad = Column(Numeric(14, 4), nullable=False)
    precio_unitario = Column(Numeric(14, 6), nullable=False)
    descuento = Column(Numeric(14, 2), default=0)
    subtotal = Column(Numeric(14, 2), nullable=False)
    igv = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), nullable=False)
    lote = Column(String(30))
    fecha_vencimiento = Column(Date, nullable=True)
    costo_unitario_kardex = Column(Numeric(14, 6), default=0)

    compra = relationship("Compra", back_populates="items")


class CompraPago(Base):
    __tablename__ = "com_pagos"

    id = Column(Integer, primary_key=True)
    id_compra = Column(Integer, ForeignKey("com_compras.id", ondelete="CASCADE"))
    fecha = Column(Date, default=datetime.now)
    monto = Column(Numeric(14, 2), nullable=False)
    medio = Column(String(30))
    referencia = Column(String(100))
    nota = Column(String(200))
    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    compra = relationship("Compra", back_populates="pagos")


class NotaMercaderia(Base):
    __tablename__ = "com_notas_mercaderia"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, index=True)
    id_almacen = Column(Integer, nullable=False)
    fecha_generacion = Column(Date, default=datetime.now)
    fecha_cierre = Column(Date, nullable=True)
    estado = Column(String(20), default="pendiente")
    id_compra_regularizacion = Column(Integer,
        ForeignKey("com_compras.id"), nullable=True)
    total_items = Column(Integer, default=0)
    nota = Column(Text)
    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    items = relationship("NotaMercaderiaItem", back_populates="nota_mercaderia",
                        cascade="all, delete-orphan")


class NotaMercaderiaItem(Base):
    __tablename__ = "com_nota_mercaderia_items"

    id = Column(Integer, primary_key=True)
    id_nota = Column(Integer,
        ForeignKey("com_notas_mercaderia.id", ondelete="CASCADE"))
    id_producto = Column(Integer, nullable=False)
    codigo_producto = Column(String(30))
    nombre_producto = Column(String(150))
    unidad = Column(String(20))
    cantidad_acumulada = Column(Numeric(14, 4), default=0)
    cantidad_regularizada = Column(Numeric(14, 4), default=0)
    pedidos_origen = Column(JSON)

    nota_mercaderia = relationship("NotaMercaderia", back_populates="items")
