"""
Modelos de autenticación y permisos del tenant.
Usuarios operativos, módulos y permisos granulares por botón.
Viven en el schema del tenant.
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class SgcModulo(Base):
    __tablename__ = "sgc_modulos"

    id_modulo = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, index=True)
    descripcion = Column(String(200))
    activo = Column(Boolean, default=True)

    opciones = relationship("SgcOpcion", back_populates="modulo")


class SgcOpcion(Base):
    __tablename__ = "sgc_opciones"

    id_opcion = Column(Integer, primary_key=True, index=True)
    id_modulo = Column(Integer, ForeignKey("sgc_modulos.id_modulo"))
    nombre = Column(String(100))
    descripcion = Column(String(200))
    activo = Column(Boolean, default=True)

    modulo = relationship("SgcModulo", back_populates="opciones")


class SgcUsuario(Base):
    """Usuario operativo del tenant (no confundir con UsuarioMaster en public)."""
    __tablename__ = "sgc_usuarios"

    id_usuario = Column(Integer, primary_key=True, index=True)
    usuario = Column(String(15), unique=True, index=True)
    clave = Column(String(100))
    nombre_completo = Column(String(100))
    activo = Column(Boolean, default=True)
    tema = Column(String(10), default="claro")
    fecha_registro = Column(DateTime, default=datetime.now)
    id_personal = Column(Integer, nullable=True)  # FK a sgc_empleados

    accesos_modulos = relationship("SgcUsuarioModulo", back_populates="usuario")
    accesos_opciones = relationship("SgcUsuarioOpcion", back_populates="usuario")


class SgcUsuarioModulo(Base):
    __tablename__ = "sgc_usuarios_modulos"

    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey("sgc_usuarios.id_usuario"))
    id_modulo = Column(Integer, ForeignKey("sgc_modulos.id_modulo"))
    nombre_modulo = Column(String(100))
    descrip_modulo = Column(String(100))
    activo = Column(Boolean, default=True)

    usuario = relationship("SgcUsuario", back_populates="accesos_modulos")
    modulo = relationship("SgcModulo")


class SgcUsuarioOpcion(Base):
    __tablename__ = "sgc_usuarios_opciones"

    id = Column(Integer, primary_key=True, index=True)
    id_usuario = Column(Integer, ForeignKey("sgc_usuarios.id_usuario"))
    id_modulo = Column(Integer, ForeignKey("sgc_modulos.id_modulo"))
    id_opcion = Column(Integer, ForeignKey("sgc_opciones.id_opcion"))
    nombre_opcion = Column(String(100))
    descrip_opcion = Column(String(100))

    # Permisos granulares por botón
    btn_nuevo = Column(Boolean, default=True)
    btn_editar = Column(Boolean, default=True)
    btn_eliminar = Column(Boolean, default=True)
    btn_pdf = Column(Boolean, default=True)
    btn_excel = Column(Boolean, default=True)
    btn_guardar = Column(Boolean, default=True)
    btn_otro = Column(Boolean, default=True)
    activo = Column(Boolean, default=True)

    usuario = relationship("SgcUsuario", back_populates="accesos_opciones")
    modulo = relationship("SgcModulo")
    opcion = relationship("SgcOpcion")


# ─────────────────────────────────────────────
# NUEVO SISTEMA DE PERMISOS GRANULARES
# ─────────────────────────────────────────────

class Accion(Base):
    __tablename__ = "auth_acciones"

    id = Column(Integer, primary_key=True)
    modulo = Column(String(30), nullable=False, index=True)
    codigo = Column(String(50), nullable=False, unique=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String(200))
    activo = Column(Boolean, default=True)


class Rol(Base):
    __tablename__ = "auth_roles"

    id = Column(Integer, primary_key=True)
    nombre = Column(String(50), nullable=False, unique=True)
    descripcion = Column(String(200))
    es_admin = Column(Boolean, default=False)
    activo = Column(Boolean, default=True)
    orden = Column(Integer, default=0)

    permisos = relationship("RolPermiso", back_populates="rol",
                           cascade="all, delete-orphan")
    usuarios = relationship("Usuario", back_populates="rol")


class RolPermiso(Base):
    __tablename__ = "auth_rol_permisos"

    id = Column(Integer, primary_key=True)
    id_rol = Column(Integer, ForeignKey("auth_roles.id", ondelete="CASCADE"))
    id_accion = Column(Integer, ForeignKey("auth_acciones.id"))

    rol = relationship("Rol", back_populates="permisos")
    accion = relationship("Accion")


class Usuario(Base):
    __tablename__ = "auth_usuarios"

    id = Column(Integer, primary_key=True)
    id_rol = Column(Integer, ForeignKey("auth_roles.id"), nullable=True)

    usuario = Column(String(30), unique=True, index=True, nullable=False)
    dni = Column(String(8), index=True)
    nombre_completo = Column(String(100))
    correo = Column(String(100))
    celular = Column(String(12))

    clave_hash = Column(String(200))
    activo = Column(Boolean, default=True)
    debe_cambiar_clave = Column(Boolean, default=True)
    ultimo_acceso = Column(DateTime, nullable=True)
    intentos_fallidos = Column(Integer, default=0)
    bloqueado_hasta = Column(DateTime, nullable=True)

    tema = Column(String(10), default="oscuro")
    id_punto_venta_default = Column(Integer, nullable=True)
    id_almacen_default = Column(Integer, nullable=True)
    id_trabajador = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(Integer, nullable=True)

    rol = relationship("Rol", back_populates="usuarios")
    permisos_extra = relationship("UsuarioPermiso", back_populates="usuario",
                                  cascade="all, delete-orphan")


class UsuarioPermiso(Base):
    __tablename__ = "auth_usuario_permisos"

    id = Column(Integer, primary_key=True)
    id_usuario = Column(Integer, ForeignKey("auth_usuarios.id", ondelete="CASCADE"))
    id_accion = Column(Integer, ForeignKey("auth_acciones.id"))
    permitido = Column(Boolean, default=True)

    usuario = relationship("Usuario", back_populates="permisos_extra")
    accion = relationship("Accion")


class SesionUsuario(Base):
    __tablename__ = "auth_sesiones"

    id = Column(Integer, primary_key=True)
    id_usuario = Column(Integer, ForeignKey("auth_usuarios.id"))
    token_hash = Column(String(100), index=True)
    ip = Column(String(50))
    dispositivo = Column(String(200))
    creada_en = Column(DateTime, default=datetime.now)
    expira_en = Column(DateTime)
    activa = Column(Boolean, default=True)
