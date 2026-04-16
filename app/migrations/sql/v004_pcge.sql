-- v004: Plan de Cuentas General Empresarial (PCGE) peruano
-- Elementos y cuentas principales (niveles 1 y 2)

INSERT INTO cont_cuentas (codigo, nombre_oficial, nivel, naturaleza, tipo,
    acepta_movimiento, activo, es_pcge_oficial)
VALUES
-- ELEMENTO 1: ACTIVO DISPONIBLE Y EXIGIBLE
('10','Efectivo y equivalentes de efectivo',1,'deudora','activo',false,true,true),
('101','Caja',2,'deudora','activo',false,true,true),
('1011','Caja',3,'deudora','activo',false,true,true),
('10111','Caja MN',4,'deudora','activo',true,true,true),
('10112','Caja ME',4,'deudora','activo',true,true,true),
('104','Cuentas corrientes en instituciones financieras',2,'deudora','activo',false,true,true),
('1041','Cuentas corrientes operativas',3,'deudora','activo',true,true,true),
('1042','Cuentas corrientes para fines especificos',3,'deudora','activo',true,true,true),

('12','Cuentas por cobrar comerciales - Terceros',1,'deudora','activo',false,true,true),
('121','Facturas, boletas y otros comprobantes por cobrar',2,'deudora','activo',false,true,true),
('1211','No emitidas',3,'deudora','activo',true,true,true),
('1212','Emitidas en cartera',3,'deudora','activo',true,true,true),

('20','Mercaderias',1,'deudora','activo',false,true,true),
('201','Mercaderias manufacturadas',2,'deudora','activo',false,true,true),
('2011','Mercaderias',3,'deudora','activo',false,true,true),
('20111','Costo',4,'deudora','activo',true,true,true),

('33','Inmuebles, maquinaria y equipo',1,'deudora','activo',false,true,true),
('331','Terrenos',2,'deudora','activo',true,true,true),
('332','Edificios y otras construcciones',2,'deudora','activo',true,true,true),
('333','Maquinaria, equipo y otras unidades de explotacion',2,'deudora','activo',true,true,true),
('334','Equipos de transporte',2,'deudora','activo',true,true,true),
('335','Muebles y enseres',2,'deudora','activo',true,true,true),
('336','Equipos diversos',2,'deudora','activo',true,true,true),
('3361','Equipos de computo',3,'deudora','activo',true,true,true),

-- ELEMENTO 4: PASIVO
('40','Tributos, contraprestaciones y aportes',1,'acreedora','pasivo',false,true,true),
('401','Gobierno central',2,'acreedora','pasivo',false,true,true),
('4011','Impuesto general a las ventas',3,'acreedora','pasivo',false,true,true),
('40111','IGV - Cuenta propia',4,'acreedora','pasivo',true,true,true),
('40112','IGV - Liquid. de compras',4,'acreedora','pasivo',true,true,true),
('4017','Impuesto a la renta',3,'acreedora','pasivo',false,true,true),
('40171','Renta de tercera categoria',4,'acreedora','pasivo',true,true,true),
('40172','Renta de cuarta categoria',4,'acreedora','pasivo',true,true,true),
('40173','Renta de quinta categoria',4,'acreedora','pasivo',true,true,true),

('42','Cuentas por pagar comerciales - Terceros',1,'acreedora','pasivo',false,true,true),
('421','Facturas, boletas y otros comprobantes por pagar',2,'acreedora','pasivo',false,true,true),
('4211','No emitidas',3,'acreedora','pasivo',true,true,true),
('4212','Emitidas',3,'acreedora','pasivo',false,true,true),
('42121','Emitidas - Terceros',4,'acreedora','pasivo',true,true,true),

-- ELEMENTO 5: PATRIMONIO
('50','Capital',1,'acreedora','patrimonio',false,true,true),
('501','Capital social',2,'acreedora','patrimonio',true,true,true),
('59','Resultados acumulados',1,'acreedora','patrimonio',false,true,true),
('591','Utilidades no distribuidas',2,'acreedora','patrimonio',true,true,true),
('592','Perdidas acumuladas',2,'deudora','patrimonio',true,true,true),

-- ELEMENTO 6: GASTOS
('60','Compras',1,'deudora','gasto',false,true,true),
('601','Mercaderias',2,'deudora','gasto',false,true,true),
('6011','Mercaderias manufacturadas',3,'deudora','gasto',false,true,true),
('60111','Costo de compras',4,'deudora','gasto',true,true,true),
('63','Gastos de servicios prestados por terceros',1,'deudora','gasto',false,true,true),
('631','Transporte, correos y gastos de viaje',2,'deudora','gasto',true,true,true),
('634','Mantenimiento y reparaciones',2,'deudora','gasto',true,true,true),
('636','Servicios basicos',2,'deudora','gasto',true,true,true),
('637','Publicidad, publicaciones, relaciones publicas',2,'deudora','gasto',true,true,true),
('641','Gobierno central',2,'deudora','gasto',false,true,true),
('6411','IGV y selectivo al consumo',3,'deudora','gasto',true,true,true),

-- ELEMENTO 7: INGRESOS
('70','Ventas',1,'acreedora','ingreso',false,true,true),
('701','Mercaderias',2,'acreedora','ingreso',false,true,true),
('7011','Mercaderias manufacturadas',3,'acreedora','ingreso',false,true,true),
('70111','Terceros',4,'acreedora','ingreso',true,true,true),

-- ELEMENTO 9: COSTO DE PRODUCCION
('69','Costo de ventas',1,'deudora','costo',false,true,true),
('691','Mercaderias',2,'deudora','costo',false,true,true),
('6911','Mercaderias manufacturadas',3,'deudora','costo',false,true,true),
('69111','Terceros',4,'deudora','costo',true,true,true)

ON CONFLICT (codigo) DO NOTHING;

-- Configuracion contable por defecto
INSERT INTO cont_config (concepto, codigo_cuenta, descripcion)
VALUES
('caja',            '10111', 'Caja MN -- cobros en efectivo'),
('banco',           '1041',  'Cuentas corrientes operativas'),
('clientes',        '1212',  'Facturas emitidas en cartera'),
('proveedores',     '42121', 'Facturas por pagar a terceros'),
('ventas_gravadas', '70111', 'Ventas mercaderias a terceros'),
('igv_ventas',      '40111', 'IGV cuenta propia'),
('igv_compras',     '40111', 'IGV credito fiscal'),
('compras',         '60111', 'Costo de compras mercaderias'),
('costo_ventas',    '69111', 'Costo de ventas mercaderias')
ON CONFLICT (concepto) DO NOTHING;
