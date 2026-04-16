from sqlalchemy import Column, Integer, String, Boolean, Date, Numeric, Text, DateTime
from datetime import datetime
from app.database import Base


class Empleado(Base):
    __tablename__ = "sgc_empleados"

    id_empleado = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), index=True)
    direcion = Column(String(100), nullable=True)   # typo original de Walter — mantener
    celular = Column(String(50), nullable=True)
    dni = Column(String(10), nullable=True)
    fecha_ingreso = Column(Date, nullable=True)
    fecha_cese = Column(Date, nullable=True)
    observacion = Column(Text, nullable=True)
    cargo = Column(String(20), nullable=True)
    comision_factura = Column(Numeric(18, 3), nullable=True)
    comision_producto = Column(Boolean, default=False)
    comision_familia = Column(Boolean, default=False)
    repatidor = Column(Boolean, default=False)    # typo original de Walter — mantener
    mesero = Column(Boolean, default=False)
    estado = Column(Boolean, default=True)
    id_usuario = Column(Integer, nullable=True)
    fhcontrol = Column(DateTime, default=datetime.now)
    estacion = Column(String(20), nullable=True)
