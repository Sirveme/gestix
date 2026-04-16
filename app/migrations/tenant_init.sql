-- tenant_init.sql: Datos iniciales para un tenant recién creado
-- Se ejecuta automáticamente desde crear_schema_tenant() después de create_all

-- Documentos de identidad (SUNAT)
INSERT INTO sgc_doc_identidad (id_doc_ide, nombre_doc_ide, abreviado_doc_ide, digitos)
VALUES
    (1, 'DNI',             'DNI', 8),
    (6, 'RUC',             'RUC', 11),
    (4, 'Carnet extranj.', 'CE',  12),
    (7, 'Pasaporte',       'PAS', 12),
    (0, 'Sin documento',   'SD',  0)
ON CONFLICT (id_doc_ide) DO NOTHING;

-- Formas de pago básicas
INSERT INTO sgc_forma_pago (id_forpag, nombre_forpag, tipo_forpag, compra, venta, pv, agenda, dias)
VALUES
    (1, 'Contado', 'contado', true, true, true, true, 0),
    (2, 'Crédito', 'credito', true, true, false, true, 30)
ON CONFLICT (id_forpag) DO NOTHING;

-- Regímenes laborales peruanos
INSERT INTO cfg_regimen_laboral (nombre, gratificacion, cts, essalud_tasa, vacaciones_dias, activo)
SELECT * FROM (VALUES
    ('General'::varchar,      true,  true, 9.00, 30, true),
    ('MYPE',                  true,  true, 9.00, 15, true),
    ('Microempresa',          false, false, 9.00, 15, true)
) AS v
WHERE NOT EXISTS (SELECT 1 FROM cfg_regimen_laboral);

-- Medios de cobro básicos
INSERT INTO cfg_medios_cobro (nombre, tipo, activo, requiere_referencia)
SELECT * FROM (VALUES
    ('Efectivo'::varchar,      'efectivo'::varchar,      true, false),
    ('Yape',                   'yape',                   true, true),
    ('Plin',                   'plin',                   true, true),
    ('Tarjeta',                'tarjeta',                true, true),
    ('Transferencia',          'transferencia',          true, true),
    ('Crédito',                'credito',                true, false)
) AS v
WHERE NOT EXISTS (SELECT 1 FROM cfg_medios_cobro);

-- Roles predefinidos
INSERT INTO auth_roles (nombre, es_admin, activo, orden)
VALUES
    ('Administrador', true, true, 0),
    ('Gerente', false, true, 1),
    ('Cajero', false, true, 2),
    ('Vendedor', false, true, 3),
    ('Almacenero', false, true, 4),
    ('Contador', false, true, 5),
    ('Proveedor', false, true, 6)
ON CONFLICT (nombre) DO NOTHING;
