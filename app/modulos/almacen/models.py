from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Numeric, Text, CHAR, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Operacion(Base):
    __tablename__ = "sgc_operaciones"

    id_operacion = Column(String(2), primary_key=True, index=True, nullable=False)
    nombre_operacion = Column(String(100), default="", nullable=False)
    ope_ingreso = Column(Boolean, default=False, nullable=False)
    ope_salida = Column(Boolean, default=False, nullable=False)


class OperacionGre(Base):
    __tablename__ = "sgc_operaciones_gre"

    id_operacion = Column(String(2), primary_key=True, index=True, nullable=False)
    nombre_operacion = Column(String(100), default="", nullable=False)


class SgcTransportista(Base):
    __tablename__ = "sgc_transportista"

    id_transportista = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ruc = Column(String(12), unique=True, index=True)
    nombre = Column(String(100))
    direccion = Column(String(100))
    localidad = Column(String(50))
    celular = Column(String(25))
    correo = Column(String(100))
    id_usuario = Column(Integer)
    fhcontrol = Column(DateTime, default=datetime.now)
    estado = Column(Boolean, default=True)

    vehiculos = relationship("SgcTransportistaVehiculo", back_populates="transportista", cascade="all, delete-orphan")


class SgcTransportistaVehiculo(Base):
    __tablename__ = "sgc_transportista_vehiculo"

    id_vehiculo = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_transportista = Column(Integer, ForeignKey("sgc_transportista.id_transportista"))
    vehiculo = Column(String(50))
    placa = Column(String(12))
    dni_chofer = Column(String(9))
    nombre_chofer = Column(String(50))
    apellidos_chofer = Column(String(80))
    licencia = Column(String(12))
    nota = Column(Text)
    estado = Column(Boolean, default=True)

    transportista = relationship("SgcTransportista", back_populates="vehiculos")


class GuiaSalida(Base):
    __tablename__ = "sgc_guia_salida"

    id_guia_salida = Column(Integer, primary_key=True, index=True)
    origen = Column(String(10), default="Salida")
    ruc = Column(String(12), nullable=True)
    id_agenda_cli = Column(Integer, default=0)
    id_docsunat = Column(Integer, default=0)
    serie = Column(CHAR(4), default="")
    numero = Column(String(8), default="")
    fecha_emision = Column(Date, default=datetime.utcnow)
    fecha_salida = Column(Date, default=datetime.utcnow)
    fecha_vencimiento = Column(Date, nullable=True)
    id_almacen = Column(Integer, default=0)
    id_operacion = Column(CHAR(2), default="")
    id_transportista = Column(Integer, default=0)
    num_placa1 = Column(String(10), default="")
    num_placa2 = Column(String(10), default="")
    chofer_dni = Column(String(9), default="")
    chofer_nombres = Column(String(50), default="")
    chofer_apellidos = Column(String(50), default="")
    chofer_licencia = Column(String(12), default="")
    certif_aut_mtc = Column(String(12), default="")
    id_inventario = Column(Integer, default=0)
    glosa = Column(String(100), default="")
    id_almacen_desti = Column(Integer, default=0)
    id_venta = Column(Integer, default=0)
    serie_venta = Column(CHAR(4), default="")
    numero_venta = Column(String(8), default="")
    id_agenda_pro = Column(Integer, default=0)
    tc = Column(Numeric(18, 3), default=0)
    modo_transp = Column(CHAR(2), default="02")
    id_moneda = Column(Integer, default=0)
    mueve_stock_ = Column(Boolean, default=False)
    igv_ = Column(Boolean, default=False)
    total_bruto = Column(Numeric(18, 2), default=0)
    descuento = Column(Numeric(18, 2), default=0)
    sub_total = Column(Numeric(18, 2), default=0)
    igv = Column(Numeric(18, 2), default=0)
    total = Column(Numeric(18, 2), default=0)
    remite_nombre = Column(String(100), default="")
    remite_direccion = Column(String(100), default="")
    remite_ubigeo = Column(CHAR(6), default="")
    destino_nombre = Column(String(100), default="")
    destino_direccion = Column(String(100), default="")
    destino_ubigeo = Column(CHAR(6), default="")
    anulada_ = Column(Boolean, default=False)
    anulada_motivo = Column(String(100), default="")
    anulada_fecha = Column(Date, nullable=True)
    nota = Column(Text, default="")
    email = Column(String(100), default="")
    celular = Column(String(10), default="")
    cpe_ = Column(Boolean, default=False)
    cpe_cdr_ = Column(Boolean, default=False)
    cpe_qr = Column(String(200), default="")
    cpe_hash = Column(String(100), default="")
    cpe_respuesta = Column(String(100), default="")
    fecha_envio = Column(Date, nullable=True)
    hora_envio = Column(String(10), default="")
    id_empleado = Column(Integer, default=0)
    cerrado = Column(Boolean, default=False)
    id_usuario = Column(Integer, default=0)
    fhcontrol = Column(DateTime, default=datetime.now)
    estacion = Column(String(20), default="")

    detalles = relationship("GuiaSalidaDetalle", back_populates="guia_salida", cascade="all, delete-orphan")


class GuiaSalidaDetalle(Base):
    __tablename__ = "sgc_guia_salida_det"

    id_guia_salida_det = Column(Integer, primary_key=True, index=True)
    id_guia_salida = Column(Integer, ForeignKey("sgc_guia_salida.id_guia_salida", ondelete="CASCADE"), default=0)
    origen = Column(String(8), default="")
    id_producto = Column(Integer, default=0)
    codigo_producto = Column(String(20), default="")
    nombre_producto = Column(String(100), default="")
    unidad_precio = Column(String(12), default="")
    equivalente = Column(Numeric(18, 7), default=0)
    cantidad = Column(Numeric(18, 3), default=0)
    precio_venta = Column(Numeric(18, 2), default=0)
    precio_bruto = Column(Numeric(18, 2), default=0)
    descuento = Column(Numeric(18, 2), default=0)
    sub_total = Column(Numeric(18, 2), default=0)
    igv = Column(Numeric(18, 2), default=0)
    total = Column(Numeric(18, 2), default=0)
    bonificacion_ = Column(Boolean, default=False)
    fecha_vencimiento = Column(Date, nullable=True)
    lote = Column(String(12), default="")
    peso = Column(Numeric(18, 3), default=0)
    id_usuario = Column(Integer, default=0)
    fhcontrol = Column(DateTime, default=datetime.now)
    estacion = Column(String(20), default="")

    guia_salida = relationship("GuiaSalida", back_populates="detalles")
