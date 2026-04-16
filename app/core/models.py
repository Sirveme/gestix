"""
Modelos del sistema (schema: public).
NO son modelos del negocio. Son para control de licencias, empresas y usuarios master.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, JSON, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Empresa(Base):
    """Empresa/tenant registrada en el sistema."""
    __tablename__ = "erp_empresas"

    id = Column(Integer, primary_key=True, index=True)
    ruc = Column(String(11), unique=True, index=True, nullable=False)
    razon_social = Column(String(200), nullable=False)
    nombre_comercial = Column(String(200), nullable=True)
    schema_db = Column(String(50), unique=True, nullable=False)  # emp_20615446565

    # Plan y estado
    plan = Column(String(20), default="basico")       # basico | pro | enterprise
    modulos_activos = Column(JSON, default=list)       # ["ventas","compras","almacen",...]
    activo = Column(Boolean, default=True)

    # Licencia
    fecha_inicio = Column(Date, nullable=True)
    fecha_vencimiento = Column(Date, nullable=True)
    max_usuarios = Column(Integer, default=3)

    # Control de acceso por IP/GPS (para intranet y móviles)
    ips_permitidas = Column(JSON, default=list)        # ["192.168.1.0/24"]
    gps_lat_min = Column(String(20), nullable=True)
    gps_lat_max = Column(String(20), nullable=True)
    gps_lon_min = Column(String(20), nullable=True)
    gps_lon_max = Column(String(20), nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    licencia = relationship("Licencia", back_populates="empresa", uselist=False)
    usuarios_master = relationship("UsuarioMaster", back_populates="empresa")


class Licencia(Base):
    """Control de licencia SaaS por empresa."""
    __tablename__ = "erp_licencias"

    id = Column(Integer, primary_key=True, index=True)
    id_empresa = Column(Integer, ForeignKey("erp_empresas.id"), unique=True)

    clave_licencia = Column(String(64), unique=True, index=True)  # UUID generado al activar
    modo = Column(String(10), default="cloud")                    # cloud | local
    trial = Column(Boolean, default=False)
    activa = Column(Boolean, default=True)

    fecha_activacion = Column(DateTime, default=datetime.now)
    fecha_vencimiento = Column(Date, nullable=True)
    ultimo_ping = Column(DateTime, nullable=True)                 # para modo local

    empresa = relationship("Empresa", back_populates="licencia")


class UsuarioMaster(Base):
    """
    Usuario administrador de la empresa (existe en schema public).
    Los usuarios operativos de cada empresa viven en su propio schema.
    """
    __tablename__ = "erp_usuarios_master"

    id = Column(Integer, primary_key=True, index=True)
    id_empresa = Column(Integer, ForeignKey("erp_empresas.id"))
    email = Column(String(200), unique=True, index=True)
    clave_hash = Column(String(200))
    nombre = Column(String(100))
    activo = Column(Boolean, default=True)
    es_superadmin = Column(Boolean, default=False)  # solo para el equipo erpPro
    created_at = Column(DateTime, default=datetime.now)

    empresa = relationship("Empresa", back_populates="usuarios_master")


class LogSistema(Base):
    """Log de eventos críticos del sistema (activaciones, errores, accesos)."""
    __tablename__ = "erp_log_sistema"

    id = Column(Integer, primary_key=True, index=True)
    id_empresa = Column(Integer, ForeignKey("erp_empresas.id"), nullable=True)
    tipo = Column(String(30))         # LOGIN | ACTIVACION | ERROR | PING | ACCESO_DENEGADO
    descripcion = Column(Text)
    ip = Column(String(50), nullable=True)
    datos = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
