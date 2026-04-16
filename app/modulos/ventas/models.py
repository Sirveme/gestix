"""
Modulo de Ventas — Gestix
Tablas en schema del tenant.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text,
    DateTime, Date, JSON, ForeignKey, CHAR, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class CajaApertura(Base):
    __tablename__ = "ven_caja_aperturas"

    id = Column(Integer, primary_key=True)
    id_punto_venta = Column(Integer, nullable=False)
    id_usuario = Column(Integer, nullable=False)

    fecha = Column(Date, nullable=False, default=datetime.now)
    hora_apertura = Column(DateTime, default=datetime.now)
    hora_cierre = Column(DateTime, nullable=True)

    monto_inicial = Column(Numeric(14, 2), default=0)
    monto_cierre_declarado = Column(Numeric(14, 2), nullable=True)
    monto_cierre_calculado = Column(Numeric(14, 2), nullable=True)
    diferencia = Column(Numeric(14, 2), nullable=True)

    estado = Column(String(10), default="abierta")
    nota_apertura = Column(String(200))
    nota_cierre = Column(String(200))

    ventas = relationship("Pedido", back_populates="caja_apertura")

    __table_args__ = (
        Index("ix_caja_apertura_fecha", "id_punto_venta", "fecha"),
    )


class Pedido(Base):
    __tablename__ = "ven_pedidos"

    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, index=True)

    id_caja_apertura = Column(Integer, ForeignKey("ven_caja_aperturas.id"), nullable=True)
    id_punto_venta = Column(Integer, nullable=False)

    id_cliente = Column(Integer, nullable=True)
    ruc_dni = Column(String(11))
    nombre_cliente = Column(String(200))
    direccion_cliente = Column(String(200))

    fecha = Column(Date, nullable=False, default=datetime.now)
    fechahora = Column(DateTime, default=datetime.now)

    subtotal = Column(Numeric(14, 2), default=0)
    descuento_total = Column(Numeric(14, 2), default=0)
    igv = Column(Numeric(14, 2), default=0)
    icbper = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), default=0)

    medio_pago = Column(String(20), default="efectivo")
    monto_pagado = Column(Numeric(14, 2), default=0)
    vuelto = Column(Numeric(14, 2), default=0)

    estado = Column(String(15), default="borrador")

    tipo_comprobante = Column(String(2))
    serie_comprobante = Column(CHAR(4))
    numero_comprobante = Column(String(8))
    id_comprobante_facturalo = Column(String(50))
    estado_cpe = Column(String(20))

    anulado = Column(Boolean, default=False)
    motivo_anulacion = Column(String(200))
    fecha_anulacion = Column(DateTime, nullable=True)
    id_usuario_anulacion = Column(Integer, nullable=True)

    id_usuario = Column(Integer, nullable=False)
    id_vendedor = Column(Integer, nullable=True)
    estacion = Column(String(50))
    nota = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    caja_apertura = relationship("CajaApertura", back_populates="ventas")
    items = relationship("PedidoItem", back_populates="pedido",
                        cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_pedido_fecha", "fecha"),
        Index("ix_pedido_cliente", "id_cliente"),
        Index("ix_pedido_estado", "estado"),
    )


class PedidoItem(Base):
    __tablename__ = "ven_pedido_items"

    id = Column(Integer, primary_key=True)
    id_pedido = Column(Integer, ForeignKey("ven_pedidos.id", ondelete="CASCADE"))

    id_producto = Column(Integer, nullable=False)
    id_precio = Column(Integer, nullable=True)
    codigo_producto = Column(String(30))
    nombre_producto = Column(String(150))
    unidad = Column(String(20))
    equivalente = Column(Numeric(12, 4), default=1)

    cantidad = Column(Numeric(14, 4), nullable=False)
    precio_unitario = Column(Numeric(14, 4), nullable=False)
    descuento = Column(Numeric(14, 2), default=0)
    subtotal = Column(Numeric(14, 2), nullable=False)
    igv = Column(Numeric(14, 2), default=0)
    icbper = Column(Numeric(14, 2), default=0)
    total = Column(Numeric(14, 2), nullable=False)

    afecto_igv = Column(Boolean, default=True)
    es_combo = Column(Boolean, default=False)
    nota = Column(String(200))

    pedido = relationship("Pedido", back_populates="items")
