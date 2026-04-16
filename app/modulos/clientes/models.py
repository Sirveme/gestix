from sqlalchemy import Column, Integer, String, Boolean, Date, DateTime, Text, Numeric, ForeignKey, func
from sqlalchemy.orm import relationship
from app.database import Base


class SgcDocIdentidad(Base):
    __tablename__ = "sgc_doc_identidad"

    id_doc_ide = Column(Integer, primary_key=True, index=True)
    nombre_doc_ide = Column(String(50))
    abreviado_doc_ide = Column(String(10))
    digitos = Column(Integer)


class SgcFormaPago(Base):
    __tablename__ = "sgc_forma_pago"

    id_forpag = Column(Integer, primary_key=True, index=True)
    nombre_forpag = Column(String(50))
    tipo_forpag = Column(String(20))
    compra = Column(Boolean, default=True)
    venta = Column(Boolean, default=True)
    pv = Column(Boolean, default=True)
    agenda = Column(Boolean, default=True)
    dias = Column(Integer, default=0)


class SgcClasificadorCli(Base):
    __tablename__ = "sgc_clasificador_cli"

    id_clacli = Column(Integer, primary_key=True, index=True)
    nombre_clacli = Column(String(50))
    id_usuario = Column(Integer)
    fhcontrol = Column(DateTime, default=func.now())
    estacion = Column(String(20))


class SgcAgendaClientesVis(Base):
    __tablename__ = "sgc_agenda_clientes_vis"

    id_agenda_clivis = Column(Integer, primary_key=True, index=True)
    nombre_clivis = Column(String(32))
    valor = Column(Integer)


class SgcAgendaZona(Base):
    __tablename__ = "sgc_agenda_zona"

    id_zona = Column(Integer, primary_key=True, index=True)
    nombre_zona = Column(String(50))
    distrito = Column(String(50))
    ubigeo = Column(String(6))

    subzonas = relationship("SgcAgendaSubzona", back_populates="zona")
    clientes = relationship("SgcAgendaClientes", back_populates="zona")


class SgcAgendaSubzona(Base):
    __tablename__ = "sgc_agenda_subzona"

    id_subzona = Column(Integer, primary_key=True, index=True)
    id_zona = Column(Integer, ForeignKey("sgc_agenda_zona.id_zona"))
    nombre_subzona = Column(String(50))
    referencia = Column(String(50))

    zona = relationship("SgcAgendaZona", back_populates="subzonas")
    clientes = relationship("SgcAgendaClientes", back_populates="subzona")


class SgcAgendaClientes(Base):
    __tablename__ = "sgc_agenda_clientes"

    id_agenda_cli = Column(Integer, primary_key=True, index=True)
    nombre_cli = Column(String(100))
    direccion_cli = Column(String(100))
    ubigeo_nombre = Column(String(100))
    ubigeo = Column(String(6))
    referencia = Column(Text)
    celular = Column(String(10))
    celular2 = Column(String(10))
    email = Column(String(100))
    id_doc_ide = Column(Integer, ForeignKey("sgc_doc_identidad.id_doc_ide"))
    num_doc_ide = Column(String(12))
    id_personal = Column(Integer)
    id_clacli = Column(Integer, ForeignKey("sgc_clasificador_cli.id_clacli"))
    id_forpag = Column(Integer, ForeignKey("sgc_forma_pago.id_forpag"))
    dias_credito = Column(Integer)
    limite_credito = Column(Numeric(18, 2))
    id_agenda_clivis = Column(Integer, ForeignKey("sgc_agenda_clientes_vis.id_agenda_clivis"))
    id_zona = Column(Integer, ForeignKey("sgc_agenda_zona.id_zona"))
    id_subzona = Column(Integer, ForeignKey("sgc_agenda_subzona.id_subzona"))
    deuda_actual = Column(Numeric(18, 2))
    saldo_disponible = Column(Numeric(18, 2))
    coordenada_x = Column(Numeric(18, 6))
    coordenada_y = Column(Numeric(18, 6))
    nota = Column(Text)
    estado = Column(Boolean, default=True)
    fecha_inicio = Column(Date)
    direcciones = Column(Boolean, default=False)
    id_usuario = Column(Integer)
    fhcontrol = Column(DateTime, default=func.now())
    estacion = Column(String(20))

    zona = relationship("SgcAgendaZona", back_populates="clientes")
    subzona = relationship("SgcAgendaSubzona", back_populates="clientes")
    direcciones_list = relationship("SgcAgendaClientesDir", back_populates="cliente")


class SgcAgendaClientesDir(Base):
    __tablename__ = "sgc_agenda_clientes_dir"

    id_agenda_cli_dir = Column(Integer, primary_key=True, index=True)
    id_agenda_cli = Column(Integer, ForeignKey("sgc_agenda_clientes.id_agenda_cli"))
    direccion_cli = Column(String(100))
    ubigeo_nombre = Column(String(100))
    ubigeo = Column(String(6))
    referencia = Column(Text)

    cliente = relationship("SgcAgendaClientes", back_populates="direcciones_list")
