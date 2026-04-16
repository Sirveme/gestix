"""
Modulo de Inventario — Gestix
Tablas en schema del tenant.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text,
    DateTime, Date, JSON, ForeignKey, CHAR, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class AjusteStock(Base):
    __tablename__ = "inv_ajustes"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, index=True)
    id_almacen = Column(Integer, nullable=False)
    fecha = Column(Date, nullable=False, default=datetime.now)
    tipo = Column(String(10), nullable=False)
    motivo = Column(String(50), nullable=False)
    sustento = Column(Text, nullable=False)
    documento_sustento_url = Column(String(300))
    estado = Column(String(15), default="pendiente")
    id_aprobador = Column(Integer, nullable=True)
    nombre_aprobador = Column(String(100))
    fecha_aprobacion = Column(DateTime, nullable=True)
    observacion_aprobacion = Column(Text)
    kardex_registrado = Column(Boolean, default=False)
    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    items = relationship("AjusteStockItem", back_populates="ajuste", cascade="all, delete-orphan")
    __table_args__ = (Index("ix_ajuste_fecha", "id_almacen", "fecha"),)


class AjusteStockItem(Base):
    __tablename__ = "inv_ajuste_items"
    id = Column(Integer, primary_key=True)
    id_ajuste = Column(Integer, ForeignKey("inv_ajustes.id", ondelete="CASCADE"))
    id_producto = Column(Integer, nullable=False)
    codigo_producto = Column(String(30))
    nombre_producto = Column(String(150))
    unidad = Column(String(20))
    cantidad_sistema = Column(Numeric(14, 4))
    cantidad_ajuste = Column(Numeric(14, 4), nullable=False)
    costo_unitario = Column(Numeric(14, 6), default=0)
    nota = Column(String(200))
    ajuste = relationship("AjusteStock", back_populates="items")


class Transferencia(Base):
    __tablename__ = "inv_transferencias"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, index=True)
    id_almacen_origen = Column(Integer, nullable=False)
    id_almacen_destino = Column(Integer, nullable=False)
    fecha = Column(Date, nullable=False, default=datetime.now)
    motivo = Column(String(200))
    estado = Column(String(15), default="pendiente")
    id_usuario_envia = Column(Integer)
    id_usuario_recibe = Column(Integer, nullable=True)
    fecha_envio = Column(DateTime, nullable=True)
    fecha_recepcion = Column(DateTime, nullable=True)
    kardex_registrado = Column(Boolean, default=False)
    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    items = relationship("TransferenciaItem", back_populates="transferencia", cascade="all, delete-orphan")


class TransferenciaItem(Base):
    __tablename__ = "inv_transferencia_items"
    id = Column(Integer, primary_key=True)
    id_transferencia = Column(Integer, ForeignKey("inv_transferencias.id", ondelete="CASCADE"))
    id_producto = Column(Integer, nullable=False)
    codigo_producto = Column(String(30))
    nombre_producto = Column(String(150))
    unidad = Column(String(20))
    cantidad_enviada = Column(Numeric(14, 4), nullable=False)
    cantidad_recibida = Column(Numeric(14, 4), nullable=True)
    costo_unitario = Column(Numeric(14, 6), default=0)
    nota = Column(String(200))
    transferencia = relationship("Transferencia", back_populates="items")


class TomaInventario(Base):
    __tablename__ = "inv_tomas"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, index=True)
    id_almacen = Column(Integer, nullable=False)
    nombre = Column(String(100))
    fecha_inicio = Column(DateTime, default=datetime.now)
    fecha_fin = Column(DateTime, nullable=True)
    tipo = Column(String(20), default="total")
    id_clas1_filtro = Column(Integer, nullable=True)
    estado = Column(String(15), default="en_proceso")
    total_items_contados = Column(Integer, default=0)
    items_con_diferencia = Column(Integer, default=0)
    valor_diferencia_total = Column(Numeric(14, 2), default=0)
    id_ajuste_generado = Column(Integer, ForeignKey("inv_ajustes.id"), nullable=True)
    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    items = relationship("TomaInventarioItem", back_populates="toma", cascade="all, delete-orphan")


class TomaInventarioItem(Base):
    __tablename__ = "inv_toma_items"
    id = Column(Integer, primary_key=True)
    id_toma = Column(Integer, ForeignKey("inv_tomas.id", ondelete="CASCADE"))
    id_producto = Column(Integer, nullable=False)
    codigo_producto = Column(String(30))
    nombre_producto = Column(String(150))
    unidad = Column(String(20))
    cantidad_sistema = Column(Numeric(14, 4), default=0)
    cantidad_contada = Column(Numeric(14, 4), nullable=True)
    diferencia = Column(Numeric(14, 4), default=0)
    costo_unitario = Column(Numeric(14, 6), default=0)
    valor_diferencia = Column(Numeric(14, 2), default=0)
    contado_por = Column(String(100))
    fecha_conteo = Column(DateTime, nullable=True)
    nota = Column(String(200))
    toma = relationship("TomaInventario", back_populates="items")


class ActivoFijo(Base):
    __tablename__ = "inv_activos_fijos"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, index=True)
    nombre = Column(String(150), nullable=False)
    descripcion = Column(Text)
    categoria = Column(String(50))
    marca = Column(String(50))
    modelo = Column(String(50))
    serie = Column(String(50))
    color = Column(String(30))
    id_almacen = Column(Integer, nullable=True)
    ubicacion_descripcion = Column(String(200))
    fecha_adquisicion = Column(Date)
    proveedor_adquisicion = Column(String(200))
    documento_adquisicion = Column(String(50))
    valor_adquisicion = Column(Numeric(14, 2), default=0)
    moneda_adquisicion = Column(String(3), default="PEN")
    vida_util_anios = Column(Integer, default=5)
    tasa_depreciacion = Column(Numeric(5, 2), default=20)
    valor_residual = Column(Numeric(14, 2), default=0)
    valor_libro_actual = Column(Numeric(14, 2), default=0)
    estado_fisico = Column(String(20), default="bueno")
    imagen_url = Column(String(300))
    documento_url = Column(String(300))
    id_responsable = Column(Integer, ForeignKey("cfg_responsables.id"), nullable=True)
    nombre_responsable = Column(String(100))
    activo = Column(Boolean, default=True)
    fecha_baja = Column(Date, nullable=True)
    motivo_baja = Column(String(200))
    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    inventarios = relationship("InventarioActivoItem", back_populates="activo_fijo")


class InventarioActivo(Base):
    __tablename__ = "inv_inventario_activos"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True)
    nombre = Column(String(100))
    fecha = Column(Date, default=datetime.now)
    estado = Column(String(15), default="en_proceso")
    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    items = relationship("InventarioActivoItem", back_populates="inventario", cascade="all, delete-orphan")


class InventarioActivoItem(Base):
    __tablename__ = "inv_inventario_activo_items"
    id = Column(Integer, primary_key=True)
    id_inventario = Column(Integer, ForeignKey("inv_inventario_activos.id", ondelete="CASCADE"))
    id_activo = Column(Integer, ForeignKey("inv_activos_fijos.id"))
    encontrado = Column(Boolean, nullable=True)
    estado_fisico_verificado = Column(String(20))
    ubicacion_verificada = Column(String(200))
    foto_url = Column(String(300))
    gps_lat = Column(Numeric(10, 7))
    gps_lon = Column(Numeric(10, 7))
    nota = Column(String(200))
    verificado_por = Column(String(100))
    fecha_verificacion = Column(DateTime, nullable=True)
    inventario = relationship("InventarioActivo", back_populates="items")
    activo_fijo = relationship("ActivoFijo", back_populates="inventarios")


class PedidoSustento(Base):
    __tablename__ = "inv_pedidos_sustento"
    id = Column(Integer, primary_key=True)
    codigo = Column(String(20), unique=True, index=True)
    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text)
    estado = Column(String(15), default="pendiente")
    id_responsable_destino = Column(Integer, ForeignKey("cfg_responsables.id"), nullable=True)
    nombre_responsable = Column(String(100))
    correo_destino = Column(String(100))
    fecha_limite = Column(Date, nullable=True)
    respuesta = Column(Text, nullable=True)
    fecha_respuesta = Column(DateTime, nullable=True)
    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    items = relationship("PedidoSustentoItem", back_populates="pedido", cascade="all, delete-orphan")


class PedidoSustentoItem(Base):
    __tablename__ = "inv_pedido_sustento_items"
    id = Column(Integer, primary_key=True)
    id_pedido = Column(Integer, ForeignKey("inv_pedidos_sustento.id", ondelete="CASCADE"))
    modulo = Column(String(20))
    id_operacion = Column(Integer)
    codigo_operacion = Column(String(30))
    descripcion_operacion = Column(Text)
    monto_operacion = Column(Numeric(14, 2), nullable=True)
    fecha_operacion = Column(Date, nullable=True)
    motivo_consulta = Column(Text, nullable=False)
    pedido = relationship("PedidoSustento", back_populates="items")
