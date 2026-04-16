-- v001: Tablas base del sistema (schema public)
-- Nota: SQLAlchemy crea las tablas ORM automáticamente con create_all().
-- Este archivo es para índices, constraints adicionales y datos iniciales.

-- Índices adicionales para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_empresas_ruc ON erp_empresas(ruc);
CREATE INDEX IF NOT EXISTS idx_licencias_clave ON erp_licencias(clave_licencia);
CREATE INDEX IF NOT EXISTS idx_log_sistema_empresa ON erp_log_sistema(id_empresa, created_at DESC);

-- Datos iniciales: superadmin del sistema
-- CAMBIAR la clave antes de producción
-- clave: "erpPro2024!" hasheada con bcrypt
INSERT INTO erp_usuarios_master (email, clave_hash, nombre, activo, es_superadmin, id_empresa)
VALUES (
    'admin@erppro.pe',
    '$2b$12$placeholder_cambiar_en_produccion',
    'Administrador erpPro',
    true,
    true,
    NULL
) ON CONFLICT (email) DO NOTHING;
