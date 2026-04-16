-- v003: Ampliaciones al modulo de Configuracion
-- Nuevos campos en tablas existentes + nuevas tablas cfg_responsables y cfg_tipos_cliente

-- ── ConfigImpuestos: ISC, TIM, multas ──
ALTER TABLE cfg_impuestos ADD COLUMN IF NOT EXISTS isc_tasa_default NUMERIC(6,2) DEFAULT 0;
ALTER TABLE cfg_impuestos ADD COLUMN IF NOT EXISTS tasa_interes_moratorio NUMERIC(6,4) DEFAULT 1.2;
ALTER TABLE cfg_impuestos ADD COLUMN IF NOT EXISTS multa_no_declarar NUMERIC(6,2) DEFAULT 100;
ALTER TABLE cfg_impuestos ADD COLUMN IF NOT EXISTS multa_declarar_cero NUMERIC(6,2) DEFAULT 50;
ALTER TABLE cfg_impuestos ADD COLUMN IF NOT EXISTS multa_omision_igv NUMERIC(6,2) DEFAULT 50;
ALTER TABLE cfg_impuestos ADD COLUMN IF NOT EXISTS multa_omision_renta NUMERIC(6,2) DEFAULT 50;
ALTER TABLE cfg_impuestos ADD COLUMN IF NOT EXISTS multa_no_emitir_cpe NUMERIC(6,2) DEFAULT 25;
ALTER TABLE cfg_impuestos ADD COLUMN IF NOT EXISTS gradualidad_subsanacion_voluntaria NUMERIC(5,2) DEFAULT 95;
ALTER TABLE cfg_impuestos ADD COLUMN IF NOT EXISTS gradualidad_con_requerimiento NUMERIC(5,2) DEFAULT 70;

-- ── ConfigPuntoVenta: anulacion ──
ALTER TABLE cfg_puntos_venta ADD COLUMN IF NOT EXISTS permite_anular_venta BOOLEAN DEFAULT false;
ALTER TABLE cfg_puntos_venta ADD COLUMN IF NOT EXISTS permite_anular_pedido BOOLEAN DEFAULT true;
ALTER TABLE cfg_puntos_venta ADD COLUMN IF NOT EXISTS requiere_motivo_anulacion BOOLEAN DEFAULT true;
ALTER TABLE cfg_puntos_venta ADD COLUMN IF NOT EXISTS minutos_max_anulacion INTEGER DEFAULT 0;

-- ── ConfigCuentaBancaria: notificaciones ──
ALTER TABLE cfg_cuentas_bancarias ADD COLUMN IF NOT EXISTS correo_notificaciones VARCHAR(200);
ALTER TABLE cfg_cuentas_bancarias ADD COLUMN IF NOT EXISTS correo_notificaciones2 VARCHAR(200);
ALTER TABLE cfg_cuentas_bancarias ADD COLUMN IF NOT EXISTS notificaciones_activo BOOLEAN DEFAULT false;

-- ── Tabla cfg_responsables (nueva) ──
CREATE TABLE IF NOT EXISTS cfg_responsables (
    id SERIAL PRIMARY KEY,
    dni VARCHAR(8) NOT NULL,
    nombres VARCHAR(100),
    apellidos VARCHAR(100),
    cargo VARCHAR(50),
    celular VARCHAR(12),
    celular2 VARCHAR(12),
    correo VARCHAR(100),
    correo_notificaciones_banco VARCHAR(100),
    puede_abrir_local BOOLEAN DEFAULT false,
    puede_cerrar_local BOOLEAN DEFAULT false,
    puede_anular_ventas BOOLEAN DEFAULT false,
    puede_dar_descuentos_especiales BOOLEAN DEFAULT false,
    puede_ver_costos BOOLEAN DEFAULT false,
    recibe_alertas_sunat BOOLEAN DEFAULT false,
    recibe_alertas_sunafil BOOLEAN DEFAULT false,
    recibe_alertas_municipio BOOLEAN DEFAULT false,
    recibe_alertas_stock BOOLEAN DEFAULT false,
    recibe_alertas_caja BOOLEAN DEFAULT false,
    recibe_notificaciones_bancarias BOOLEAN DEFAULT false,
    activo BOOLEAN DEFAULT true,
    es_representante_legal BOOLEAN DEFAULT false,
    updated_at TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cfg_responsables_dni ON cfg_responsables(dni);

-- ── ConfigBilleteraDigital: responsable ──
ALTER TABLE cfg_billeteras ADD COLUMN IF NOT EXISTS id_responsable INTEGER REFERENCES cfg_responsables(id);

-- ── ConfigAlmacen: responsable + GPS operativo ──
ALTER TABLE cfg_almacenes ADD COLUMN IF NOT EXISTS id_responsable INTEGER REFERENCES cfg_responsables(id);
ALTER TABLE cfg_almacenes ADD COLUMN IF NOT EXISTS gps_lat_op NUMERIC(10,7);
ALTER TABLE cfg_almacenes ADD COLUMN IF NOT EXISTS gps_lon_op NUMERIC(10,7);
ALTER TABLE cfg_almacenes ADD COLUMN IF NOT EXISTS gps_radio_op_metros INTEGER DEFAULT 50;

-- ── Tabla cfg_tipos_cliente (nueva) ──
CREATE TABLE IF NOT EXISTS cfg_tipos_cliente (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) NOT NULL,
    descripcion VARCHAR(100),
    id_lista_precio INTEGER REFERENCES cfg_listas_precio(id),
    descuento_max NUMERIC(5,2) DEFAULT 0,
    permite_credito BOOLEAN DEFAULT false,
    dias_credito_default INTEGER DEFAULT 0,
    limite_credito_default NUMERIC(12,2) DEFAULT 0,
    requiere_aprobacion BOOLEAN DEFAULT false,
    orden INTEGER DEFAULT 0,
    activo BOOLEAN DEFAULT true
);
