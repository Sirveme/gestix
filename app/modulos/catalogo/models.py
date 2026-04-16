"""
Módulo Catálogo de Productos — Gestix.
Incluye kardex para soporte de cortes de inventario a fecha.
"""
from sqlalchemy import (
    Column, Integer, String, Boolean, Numeric, Text,
    DateTime, Date, JSON, ForeignKey, CHAR, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


# ─────────────────────────────────────────────
# CLASIFICADORES (3 niveles)
# ─────────────────────────────────────────────

class CatClasificador1(Base):
    """Nivel 1: Familia / Categoría principal"""
    __tablename__ = "cat_clasificador1"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(10))
    nombre = Column(String(100), nullable=False)
    imagen_url = Column(String(300))
    origen = Column(String(10), default="NAC")  # NAC | IMP
    activo = Column(Boolean, default=True)
    orden = Column(Integer, default=0)

    # Cuentas contables
    cta_ventas = Column(String(12))
    cta_compras = Column(String(12))
    cta_inventario = Column(String(12))

    nivel2 = relationship("CatClasificador2", back_populates="nivel1")


class CatClasificador2(Base):
    """Nivel 2: Subfamilia"""
    __tablename__ = "cat_clasificador2"

    id = Column(Integer, primary_key=True, index=True)
    id_nivel1 = Column(Integer, ForeignKey("cat_clasificador1.id"), nullable=False)
    codigo = Column(String(10))
    nombre = Column(String(100), nullable=False)
    activo = Column(Boolean, default=True)
    orden = Column(Integer, default=0)

    nivel1 = relationship("CatClasificador1", back_populates="nivel2")
    nivel3 = relationship("CatClasificador3", back_populates="nivel2")


class CatClasificador3(Base):
    """Nivel 3: Tipo / Subtipo"""
    __tablename__ = "cat_clasificador3"

    id = Column(Integer, primary_key=True, index=True)
    id_nivel2 = Column(Integer, ForeignKey("cat_clasificador2.id"), nullable=False)
    nombre = Column(String(100), nullable=False)
    activo = Column(Boolean, default=True)

    nivel2 = relationship("CatClasificador2", back_populates="nivel3")


# ─────────────────────────────────────────────
# ATRIBUTOS
# ─────────────────────────────────────────────

class CatMarca(Base):
    __tablename__ = "cat_marcas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), nullable=False)
    activo = Column(Boolean, default=True)


class CatUnidad(Base):
    __tablename__ = "cat_unidades"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(30), nullable=False)
    abreviado = Column(String(6), nullable=False)
    codigo_sunat = Column(CHAR(3))
    activo = Column(Boolean, default=True)


class CatColor(Base):
    __tablename__ = "cat_colores"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(30), nullable=False)
    hex_color = Column(CHAR(7))     # #RRGGBB para mostrar en UI


class CatTalla(Base):
    __tablename__ = "cat_tallas"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(20), nullable=False)
    orden = Column(Integer, default=0)  # para ordenar XS < S < M < L < XL


# ─────────────────────────────────────────────
# PRODUCTO MAESTRO
# ─────────────────────────────────────────────

class Producto(Base):
    __tablename__ = "cat_productos"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(30), index=True)
    nombre = Column(String(200), nullable=False, index=True)
    descripcion = Column(Text)
    imagen_url = Column(String(300))

    # Clasificación
    id_clasificador1 = Column(Integer, ForeignKey("cat_clasificador1.id"))
    id_clasificador2 = Column(Integer, ForeignKey("cat_clasificador2.id"))
    id_clasificador3 = Column(Integer, ForeignKey("cat_clasificador3.id"))
    id_marca = Column(Integer, ForeignKey("cat_marcas.id"))
    id_unidad = Column(Integer, ForeignKey("cat_unidades.id"), nullable=False)

    # SUNAT
    cod_sunat = Column(String(12))      # código producto/servicio SUNAT
    afecto_igv = Column(Boolean, default=True)
    afecto_isc = Column(Boolean, default=False)
    afecto_icbper = Column(Boolean, default=False)

    # Farmacia / regulado
    cod_diremid = Column(String(12))
    reg_sanitario = Column(String(20))

    # Control
    tipo = Column(String(10), default="producto")  # producto | servicio | combo
    inventariado = Column(Boolean, default=True)
    tiene_vencimiento = Column(Boolean, default=False)
    tiene_lote = Column(Boolean, default=False)
    tiene_talla = Column(Boolean, default=False)
    tiene_color = Column(Boolean, default=False)
    tiene_serie = Column(Boolean, default=False)    # para electrónicos

    # Stock
    stock_minimo = Column(Numeric(12, 3), default=0)
    stock_maximo = Column(Numeric(12, 3), default=0)

    # Ubicación en almacén
    ubicacion = Column(String(20))

    # Precio rápido (precio principal de venta)
    precio_costo = Column(Numeric(12, 4), default=0)
    precio_venta = Column(Numeric(12, 4), default=0)

    # Proveedor principal
    id_proveedor = Column(Integer)

    # Estado
    activo = Column(Boolean, default=True)
    destacado = Column(Boolean, default=False)

    # Auditoría
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(Integer)

    # Relaciones
    clasificador1 = relationship("CatClasificador1")
    clasificador2 = relationship("CatClasificador2")
    clasificador3 = relationship("CatClasificador3")
    marca = relationship("CatMarca")
    unidad = relationship("CatUnidad")
    precios = relationship("ProductoPrecio", back_populates="producto",
                          cascade="all, delete-orphan")
    barras = relationship("ProductoBarra", back_populates="producto",
                         cascade="all, delete-orphan")
    combos = relationship("ProductoCombo", foreign_keys="ProductoCombo.id_producto_padre",
                         back_populates="padre", cascade="all, delete-orphan")
    stocks = relationship("ProductoStock", back_populates="producto",
                         cascade="all, delete-orphan")


# ─────────────────────────────────────────────
# PRECIOS (múltiples por lista y unidad)
# ─────────────────────────────────────────────

class ProductoPrecio(Base):
    """
    Precios por lista de precio y unidad de venta.
    Soporta: docena, caja, pack, unidad, kg, etc.
    """
    __tablename__ = "cat_producto_precios"

    id = Column(Integer, primary_key=True, index=True)
    id_producto = Column(Integer, ForeignKey("cat_productos.id"), nullable=False)
    id_lista = Column(Integer, ForeignKey("cfg_listas_precio.id"), nullable=True)
    # NULL = precio base (aplica a todos)

    nombre = Column(String(50))         # "Precio minorista", "Precio mayorista"
    unidad_venta = Column(String(20))   # "UND", "DOC", "CAJA", "KG"
    equivalente = Column(Numeric(12, 7), default=1)  # 1 caja = 12 unidades

    precio_costo = Column(Numeric(12, 4), default=0)
    flete = Column(Numeric(12, 4), default=0)
    otros_gastos = Column(Numeric(12, 4), default=0)
    margen = Column(Numeric(5, 2), default=0)       # %
    precio_venta = Column(Numeric(12, 4), nullable=False)

    # Comportamiento
    es_precio_compra = Column(Boolean, default=False)   # unidad de compra
    es_precio_venta = Column(Boolean, default=True)     # unidad de venta
    redondeo = Column(Boolean, default=True)
    permite_fraccion = Column(Boolean, default=False)
    bonificacion = Column(Boolean, default=False)
    venta_por_importe = Column(Boolean, default=False)  # para balanza
    es_balanza = Column(Boolean, default=False)

    activo = Column(Boolean, default=True)

    producto = relationship("Producto", back_populates="precios")


# ─────────────────────────────────────────────
# CÓDIGOS DE BARRA
# ─────────────────────────────────────────────

class ProductoBarra(Base):
    __tablename__ = "cat_producto_barras"

    id = Column(Integer, primary_key=True, index=True)
    id_producto = Column(Integer, ForeignKey("cat_productos.id"), nullable=False)
    id_precio = Column(Integer, ForeignKey("cat_producto_precios.id"), nullable=True)
    codigo = Column(String(30), nullable=False, index=True)
    tipo = Column(String(10), default="EAN13")  # EAN13 | QR | CODE128

    producto = relationship("Producto", back_populates="barras")

    __table_args__ = (
        Index("ix_cat_barras_codigo", "codigo"),
    )


# ─────────────────────────────────────────────
# COMBOS / PAQUETES
# ─────────────────────────────────────────────

class ProductoCombo(Base):
    """Componentes de un producto combo/paquete."""
    __tablename__ = "cat_producto_combos"

    id = Column(Integer, primary_key=True, index=True)
    id_producto_padre = Column(Integer, ForeignKey("cat_productos.id"), nullable=False)
    id_producto_hijo = Column(Integer, ForeignKey("cat_productos.id"), nullable=False)
    id_precio_hijo = Column(Integer, ForeignKey("cat_producto_precios.id"))

    cantidad = Column(Numeric(12, 3), nullable=False, default=1)
    precio_costo = Column(Numeric(12, 4), default=0)
    precio_venta = Column(Numeric(12, 4), default=0)

    padre = relationship("Producto", foreign_keys=[id_producto_padre],
                        back_populates="combos")
    hijo = relationship("Producto", foreign_keys=[id_producto_hijo])


# ─────────────────────────────────────────────
# STOCK POR ALMACÉN
# ─────────────────────────────────────────────

class ProductoStock(Base):
    """Stock actual por producto y almacén."""
    __tablename__ = "cat_producto_stock"

    id = Column(Integer, primary_key=True, index=True)
    id_producto = Column(Integer, ForeignKey("cat_productos.id"), nullable=False)
    id_almacen = Column(Integer, nullable=False)    # FK a cfg_almacenes

    stock_actual = Column(Numeric(12, 3), default=0)
    stock_reservado = Column(Numeric(12, 3), default=0)
    stock_disponible = Column(Numeric(12, 3), default=0)    # actual - reservado
    costo_promedio = Column(Numeric(12, 4), default=0)
    ultima_entrada = Column(DateTime)
    ultima_salida = Column(DateTime)

    producto = relationship("Producto", back_populates="stocks")

    __table_args__ = (
        Index("ix_stock_prod_alm", "id_producto", "id_almacen", unique=True),
    )


# ─────────────────────────────────────────────
# KARDEX
# ─────────────────────────────────────────────

class Kardex(Base):
    """
    Registro de todos los movimientos de stock.
    Permite cortes de inventario a cualquier fecha.
    Cada venta, compra, ajuste o traslado genera una línea aquí.
    """
    __tablename__ = "cat_kardex"

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, nullable=False, index=True)
    fecha_hora = Column(DateTime, default=datetime.now, index=True)

    # Producto y almacén
    id_producto = Column(Integer, ForeignKey("cat_productos.id"), nullable=False, index=True)
    id_almacen = Column(Integer, nullable=False, index=True)

    # Tipo de movimiento
    tipo = Column(String(20), nullable=False)
    # COMPRA | VENTA | DEVOLUCION_COMPRA | DEVOLUCION_VENTA |
    # AJUSTE_ENTRADA | AJUSTE_SALIDA | TRASLADO_ENTRADA | TRASLADO_SALIDA |
    # PRODUCCION_ENTRADA | PRODUCCION_SALIDA | INVENTARIO_INICIAL

    # Origen del movimiento (trazabilidad)
    origen_tipo = Column(String(20))    # venta | compra | ajuste | traslado
    origen_serie = Column(String(4))
    origen_numero = Column(String(10))
    origen_id = Column(Integer)

    # Cantidades
    cantidad_entrada = Column(Numeric(12, 3), default=0)
    cantidad_salida = Column(Numeric(12, 3), default=0)
    saldo = Column(Numeric(12, 3), default=0)   # saldo acumulado

    # Costos (método costo promedio ponderado)
    costo_unitario = Column(Numeric(12, 4), default=0)
    costo_total_entrada = Column(Numeric(12, 2), default=0)
    costo_total_salida = Column(Numeric(12, 2), default=0)
    costo_saldo = Column(Numeric(12, 2), default=0)

    # Precio de venta (para análisis de margen)
    precio_venta = Column(Numeric(12, 4), default=0)

    # Datos adicionales
    lote = Column(String(20))
    fecha_vencimiento = Column(Date)
    observacion = Column(String(200))

    # Auditoría
    id_usuario = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    producto = relationship("Producto")

    __table_args__ = (
        Index("ix_kardex_fecha_prod", "fecha", "id_producto", "id_almacen"),
    )


class StockActual(Base):
    __tablename__ = "cat_stock_actual"

    id = Column(Integer, primary_key=True)
    id_producto = Column(Integer, ForeignKey("cat_productos.id"), nullable=False)
    id_almacen = Column(Integer, nullable=False)
    cantidad = Column(Numeric(14, 4), default=0)
    costo_promedio = Column(Numeric(14, 6), default=0)
    costo_total = Column(Numeric(14, 2), default=0)
    ultima_actualizacion = Column(DateTime, default=datetime.now)

    __table_args__ = (
        Index("ix_stock_producto_almacen", "id_producto", "id_almacen", unique=True),
    )
