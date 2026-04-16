"""
Servicio de permisos — logica centralizada de verificacion.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.modulos.auth.models import (
    Usuario, Rol, RolPermiso, UsuarioPermiso, Accion
)

ACCIONES_SISTEMA = [
    ("ventas", "ventas.ver_dashboard",      "Ver dashboard de ventas"),
    ("ventas", "ventas.abrir_caja",         "Abrir caja"),
    ("ventas", "ventas.cerrar_caja",        "Cerrar caja"),
    ("ventas", "ventas.crear_pedido",       "Crear pedido/venta"),
    ("ventas", "ventas.anular_pedido",      "Anular pedido"),
    ("ventas", "ventas.anular_venta",       "Anular venta/comprobante"),
    ("ventas", "ventas.aplicar_descuento",  "Aplicar descuentos"),
    ("ventas", "ventas.emitir_factura",     "Emitir factura electronica"),
    ("ventas", "ventas.emitir_boleta",      "Emitir boleta electronica"),
    ("catalogo", "catalogo.ver",               "Ver catalogo de productos"),
    ("catalogo", "catalogo.crear_producto",    "Crear productos"),
    ("catalogo", "catalogo.editar_producto",   "Editar productos"),
    ("catalogo", "catalogo.eliminar_producto", "Eliminar/desactivar productos"),
    ("catalogo", "catalogo.ver_costos",        "Ver precios de costo"),
    ("catalogo", "catalogo.gestionar_precios", "Gestionar listas de precios"),
    ("catalogo", "catalogo.gestionar_maestros","Gestionar maestros (unidades, marcas)"),
    ("config", "config.ver",                  "Ver configuracion"),
    ("config", "config.editar_empresa",       "Editar datos de la empresa"),
    ("config", "config.editar_facturacion",   "Configurar facturacion electronica"),
    ("config", "config.editar_impuestos",     "Editar parametros tributarios"),
    ("config", "config.gestionar_usuarios",   "Gestionar usuarios"),
    ("config", "config.gestionar_permisos",   "Asignar permisos"),
    ("config", "config.gestionar_pvs",        "Gestionar puntos de venta"),
    ("compras", "compras.ver",          "Ver modulo de compras"),
    ("compras", "compras.crear_compra", "Registrar compras"),
    ("compras", "compras.aprobar_compra","Aprobar compras"),
    ("compras", "compras.anular_compra","Anular compras"),
    ("inventario", "inventario.ver",              "Ver inventario y stock"),
    ("inventario", "inventario.ajustar_stock",    "Ajustar stock"),
    ("inventario", "inventario.transferir_stock", "Transferir entre almacenes"),
    ("inventario", "inventario.corte_inventario", "Generar corte de inventario"),
    ("rrhh", "rrhh.ver",                  "Ver modulo de RRHH"),
    ("rrhh", "rrhh.gestionar_trabajadores","Gestionar trabajadores"),
    ("rrhh", "rrhh.ver_planillas",        "Ver planillas"),
    ("rrhh", "rrhh.procesar_planillas",   "Procesar planillas"),
    ("proveedores", "proveedores.ver",                  "Ver portal de proveedores"),
    ("proveedores", "proveedores.registrar_comprobantes","Registrar facturas/guias"),
    ("proveedores", "proveedores.ver_mis_pedidos",       "Ver mis pedidos"),
    ("proveedores", "proveedores.ver_stock_cliente",     "Ver stock del cliente"),
    ("proveedores", "proveedores.acceso_portal",         "Acceso al portal proveedor"),
    ("sistema", "sistema.ver_reportes",    "Ver reportes"),
    ("sistema", "sistema.exportar_excel",  "Exportar a Excel"),
    ("sistema", "sistema.exportar_pdf",    "Exportar a PDF"),
    ("sistema", "sistema.acceso_total",    "Acceso total (superadmin)"),
]

PERMISOS_ROL = {
    "Administrador": [a[1] for a in ACCIONES_SISTEMA],
    "Gerente": [
        "ventas.ver_dashboard", "ventas.abrir_caja", "ventas.cerrar_caja",
        "ventas.crear_pedido", "ventas.anular_pedido", "ventas.anular_venta",
        "ventas.aplicar_descuento", "ventas.emitir_factura", "ventas.emitir_boleta",
        "catalogo.ver", "catalogo.crear_producto", "catalogo.editar_producto",
        "catalogo.ver_costos", "catalogo.gestionar_precios",
        "compras.ver", "compras.crear_compra", "compras.aprobar_compra",
        "inventario.ver", "inventario.ajustar_stock", "inventario.corte_inventario",
        "rrhh.ver", "rrhh.gestionar_trabajadores", "rrhh.ver_planillas",
        "sistema.ver_reportes", "sistema.exportar_excel", "sistema.exportar_pdf",
    ],
    "Cajero": [
        "ventas.ver_dashboard", "ventas.abrir_caja", "ventas.cerrar_caja",
        "ventas.crear_pedido", "ventas.emitir_boleta",
        "catalogo.ver",
    ],
    "Vendedor": [
        "ventas.ver_dashboard", "ventas.crear_pedido",
        "catalogo.ver",
    ],
    "Almacenero": [
        "catalogo.ver", "inventario.ver",
        "inventario.ajustar_stock", "inventario.transferir_stock",
        "compras.ver",
    ],
    "Contador": [
        "ventas.ver_dashboard",
        "catalogo.ver", "catalogo.ver_costos",
        "compras.ver", "compras.crear_compra",
        "inventario.ver", "inventario.corte_inventario",
        "rrhh.ver", "rrhh.ver_planillas",
        "sistema.ver_reportes", "sistema.exportar_excel", "sistema.exportar_pdf",
        "config.ver", "config.editar_impuestos",
    ],
    "Proveedor": [
        "proveedores.ver", "proveedores.registrar_comprobantes",
        "proveedores.ver_mis_pedidos",
    ],
}


async def get_permisos_usuario(
    db: AsyncSession,
    id_usuario: int,
) -> set[str]:
    result = await db.execute(
        select(Usuario).where(Usuario.id == id_usuario))
    usuario = result.scalar_one_or_none()
    if not usuario:
        return set()

    if usuario.rol and usuario.rol.es_admin:
        result2 = await db.execute(
            select(Accion.codigo).where(Accion.activo == True))
        return {row[0] for row in result2.fetchall()}

    permisos = set()
    if usuario.id_rol:
        result3 = await db.execute(
            select(Accion.codigo)
            .join(RolPermiso, RolPermiso.id_accion == Accion.id)
            .where(RolPermiso.id_rol == usuario.id_rol)
        )
        permisos = {row[0] for row in result3.fetchall()}

    result4 = await db.execute(
        select(UsuarioPermiso).where(UsuarioPermiso.id_usuario == id_usuario))
    extras = result4.scalars().all()

    for extra in extras:
        if extra.accion:
            if extra.permitido:
                permisos.add(extra.accion.codigo)
            else:
                permisos.discard(extra.accion.codigo)

    return permisos


async def puede(
    db: AsyncSession,
    id_usuario: int,
    accion: str,
) -> bool:
    permisos = await get_permisos_usuario(db, id_usuario)
    return accion in permisos or "sistema.acceso_total" in permisos


async def seed_acciones(db: AsyncSession):
    for modulo, codigo, nombre in ACCIONES_SISTEMA:
        result = await db.execute(
            select(Accion).where(Accion.codigo == codigo))
        if not result.scalar_one_or_none():
            db.add(Accion(modulo=modulo, codigo=codigo, nombre=nombre))
    await db.flush()


async def seed_roles(db: AsyncSession):
    for orden, (nombre_rol, codigos) in enumerate(PERMISOS_ROL.items()):
        result = await db.execute(
            select(Rol).where(Rol.nombre == nombre_rol))
        rol = result.scalar_one_or_none()

        if not rol:
            rol = Rol(
                nombre=nombre_rol,
                es_admin=(nombre_rol == "Administrador"),
                orden=orden,
            )
            db.add(rol)
            await db.flush()

        await db.execute(
            delete(RolPermiso).where(RolPermiso.id_rol == rol.id))

        for codigo in codigos:
            r_acc = await db.execute(
                select(Accion).where(Accion.codigo == codigo))
            accion = r_acc.scalar_one_or_none()
            if accion:
                db.add(RolPermiso(id_rol=rol.id, id_accion=accion.id))

    await db.flush()
