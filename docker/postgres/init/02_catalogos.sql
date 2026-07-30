-- ============================================================================
-- 02_catalogos.sql — Tablas de catálogos (dimensiones)
-- ============================================================================
-- Contaminantes y metadatos asociados (unidad, rangos físicos)
-- ============================================================================

CREATE TABLE IF NOT EXISTS rama.contaminante (
    codigo          CHAR(5)       PRIMARY KEY,
    nombre          VARCHAR(100)  NOT NULL,
    unidad          VARCHAR(20)   NOT NULL,
    valor_min       REAL          NOT NULL  DEFAULT 0.0,
    valor_max       REAL          NOT NULL,

    CONSTRAINT contaminante_rango_positivo CHECK (valor_min >= 0 AND valor_max > valor_min)
);

COMMENT ON TABLE rama.contaminante IS
  'Catálogo de contaminantes medidos. Cada registro define el código, nombre, '
  'unidad de medida y rangos físicos válidos (valor_min, valor_max).';

COMMENT ON COLUMN rama.contaminante.codigo IS 'Código único (ej: CO, NO2, PM25)';
COMMENT ON COLUMN rama.contaminante.nombre IS 'Nombre descriptivo en español';
COMMENT ON COLUMN rama.contaminante.unidad IS 'Unidad de medida (ppm, ppb, µg/m³)';
COMMENT ON COLUMN rama.contaminante.valor_min IS 'Mínimo físico esperado (siempre >= 0)';
COMMENT ON COLUMN rama.contaminante.valor_max IS 'Máximo físico esperado';

-- Insertar catálogo de contaminantes (rangos extraídos de ge_audit.py / docs históricos)
INSERT INTO rama.contaminante (codigo, nombre, unidad, valor_min, valor_max)
VALUES
    ('CO',    'Monoxido de carbono',     'ppm',  0.0,  50.0),
    ('NO',    'Oxido nitrico',           'ppb',  0.0, 800.0),
    ('NO2',   'Dioxido de nitrogeno',    'ppb',  0.0, 500.0),
    ('NOX',   'Oxidos de nitrogeno',     'ppb',  0.0, 1000.0),
    ('O3',    'Ozono',                   'ppb',  0.0, 500.0),
    ('PM10',  'Particulas < 10 µm',      'µg/m³', 0.0, 2000.0),
    ('PM25',  'Particulas < 2.5 µm',     'µg/m³', 0.0, 1000.0),
    ('PMCO',  'Particulas gruesas',      'µg/m³', 0.0, 1000.0),
    ('SO2',   'Dioxido de azufre',       'ppb',  0.0, 1000.0)
ON CONFLICT DO NOTHING;
