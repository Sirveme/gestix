from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, Numeric, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class SgcCaja(Base):
    __tablename__ = "sgc_tesoreria_cajas"

    id_caja = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(20), unique=True, index=True, nullable=False)
    descripcion = Column(String(100), nullable=False)
    moneda = Column(String(3), nullable=False)
    saldo_inicial = Column(Numeric(18, 2), default=0.00)
    saldo_actual = Column(Numeric(18, 2), default=0.00)
    estado = Column(Boolean, default=True)
    es_caja_chica = Column(Boolean, default=False)
    id_usuario_creacion = Column(Integer, ForeignKey("sgc_usuarios.id_usuario"))
    fecha_creacion = Column(DateTime, default=datetime.now)


class SgcBanco(Base):
    __tablename__ = "sgc_tesoreria_bancos"

    id_banco = Column(Integer, primary_key=True, index=True)
    codigo_sunat = Column(String(10), nullable=True)
    nombre = Column(String(100), nullable=False)
    activo = Column(Boolean, default=True)


class SgcCuentaBancaria(Base):
    __tablename__ = "sgc_tesoreria_cuentas"

    id_cuenta = Column(Integer, primary_key=True, index=True)
    id_banco = Column(Integer, ForeignKey("sgc_tesoreria_bancos.id_banco"))
    numero_cuenta = Column(String(50), nullable=False)
    cci = Column(String(50), nullable=True)
    moneda = Column(String(3), nullable=False)
    titular = Column(String(100), nullable=True)
    saldo_inicial = Column(Numeric(18, 2), default=0.00)
    saldo_actual = Column(Numeric(18, 2), default=0.00)
    activo = Column(Boolean, default=True)

    banco = relationship("SgcBanco")


class SgcConcepto(Base):
    __tablename__ = "sgc_tesoreria_conceptos"

    id_concepto = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(20), nullable=True)
    descripcion = Column(String(100), nullable=False)
    tipo = Column(String(20), nullable=False)  # INGRESO, EGRESO, TRANSFERENCIA
    activo = Column(Boolean, default=True)


class SgcMovimientoTesoreria(Base):
    __tablename__ = "sgc_tesoreria_movimientos"

    id_movimiento = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date, default=datetime.now)
    tipo_movimiento = Column(String(20), nullable=False)
    id_caja = Column(Integer, ForeignKey("sgc_tesoreria_cajas.id_caja"), nullable=True)
    id_cuenta = Column(Integer, ForeignKey("sgc_tesoreria_cuentas.id_cuenta"), nullable=True)
    id_concepto = Column(Integer, ForeignKey("sgc_tesoreria_conceptos.id_concepto"))
    monto = Column(Numeric(18, 2), nullable=False)
    moneda = Column(String(3), nullable=False)
    tipo_cambio = Column(Numeric(10, 4), default=1.0000)
    glosa = Column(String(255), nullable=True)
    referencia = Column(String(100), nullable=True)
    es_transferencia = Column(Boolean, default=False)
    id_movimiento_relacionado = Column(Integer, nullable=True)
    id_usuario = Column(Integer, ForeignKey("sgc_usuarios.id_usuario"))
    fechahora = Column(DateTime, default=datetime.now)
    estacion = Column(String(50), nullable=True)

    caja = relationship("SgcCaja")
    cuenta = relationship("SgcCuentaBancaria")
    concepto = relationship("SgcConcepto")
