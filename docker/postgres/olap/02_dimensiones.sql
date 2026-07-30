-- ============================================================================
-- 02_dimensiones.sql — Dimensiones (snowflake)
-- ============================================================================
-- dim_tiempo, dim_alcaldia, dim_categoria_contaminante, dim_contaminante,
-- dim_estacion, dim_calidad_aire_imeca
-- ============================================================================

-- dim_tiempo: grano horario (1986-01-01 a 2025-12-31)
CREATE TABLE IF NOT EXISTS rama_olap.dim_tiempo (
    tiempo_id           BIGINT PRIMARY KEY,
    fecha_hora          TIMESTAMP NOT NULL UNIQUE,
    fecha               DATE NOT NULL,
    anio                SMALLINT NOT NULL,
    trimestre           SMALLINT NOT NULL,  -- 1..4
    mes                 SMALLINT NOT NULL,  -- 1..12
    dia                 SMALLINT NOT NULL,  -- 1..31
    hora                SMALLINT NOT NULL,  -- 0..23
    dia_semana          SMALLINT NOT NULL,  -- 1=lunes, 7=domingo
    es_fin_semana       BOOLEAN NOT NULL,   -- sábado/domingo
    estacion_del_anio   VARCHAR(20) NOT NULL -- "Invierno", "Primavera", etc.
);

COMMENT ON TABLE rama_olap.dim_tiempo IS
  'Dimensión temporal: grano hora. Columnas para análisis de patrones '
  'temporales, estacionalidad y tendencias históricas.';

CREATE INDEX idx_dim_tiempo_fecha ON rama_olap.dim_tiempo(fecha);
CREATE INDEX idx_dim_tiempo_anio_mes ON rama_olap.dim_tiempo(anio, mes);

---

-- dim_alcaldia: geografía ZMVM limpia (deduplicada, sin HTML entities)
CREATE TABLE IF NOT EXISTS rama_olap.dim_alcaldia (
    alcaldia_id         SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    nombre_alcaldia     VARCHAR(100) NOT NULL UNIQUE,
    entidad             VARCHAR(50) NOT NULL,  -- "CDMX" o "Estado de México"
    latitud_centroide   NUMERIC(9,6),          -- opcional, para future heatmaps
    longitud_centroide  NUMERIC(9,6)           -- opcional
);

COMMENT ON TABLE rama_olap.dim_alcaldia IS
  'Geografía de ZMVM: 16 alcaldías de CDMX + 12 municipios del Estado de México. '
  'Nombres normalizados (sin HTML entities), deduplicados. '
  '~24 filas (consolidadas de 31 variantes sucias en origen).';

CREATE INDEX idx_dim_alcaldia_entidad ON rama_olap.dim_alcaldia(entidad);

---

-- dim_categoria_contaminante: clasificación química estándar
CREATE TABLE IF NOT EXISTS rama_olap.dim_categoria_contaminante (
    categoria_id        SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    nombre_categoria    VARCHAR(50) NOT NULL UNIQUE  -- "Gases", "Partículas"
);

COMMENT ON TABLE rama_olap.dim_categoria_contaminante IS
  'Clasificación química de contaminantes: Gases (CO, NO, NO2, NOX, O3, SO2) '
  'vs Partículas (PM10, PM25, PMCO). Facilita análisis por familia.';

INSERT INTO rama_olap.dim_categoria_contaminante (nombre_categoria)
VALUES ('Gases'), ('Partículas')
ON CONFLICT DO NOTHING;

---

-- dim_contaminante: snowflake → dim_categoria_contaminante
CREATE TABLE IF NOT EXISTS rama_olap.dim_contaminante (
    contaminante_id     SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    codigo              CHAR(5) NOT NULL UNIQUE,  -- CO, NO, NO2, NOX, O3, PM10, PM25, PMCO, SO2
    nombre              VARCHAR(100) NOT NULL,
    unidad              VARCHAR(20) NOT NULL,     -- ppm, ppb, µg/m³
    categoria_id        SMALLINT NOT NULL REFERENCES rama_olap.dim_categoria_contaminante,
    valor_min           REAL NOT NULL,
    valor_max           REAL NOT NULL,

    CONSTRAINT contaminante_rango CHECK (valor_min >= 0 AND valor_max > valor_min)
);

COMMENT ON TABLE rama_olap.dim_contaminante IS
  'Catálogo de contaminantes con rangos físicos. Copiado de rama.contaminante '
  'para independencia del schema OLTP. Incluye categoría (Gases/Partículas) '
  'para análisis tabulares.';

CREATE INDEX idx_dim_contaminante_categoria ON rama_olap.dim_contaminante(categoria_id);

---

-- dim_estacion: snowflake → dim_alcaldia (período vigente)
CREATE TABLE IF NOT EXISTS rama_olap.dim_estacion (
    estacion_id         SMALLINT PRIMARY KEY,  -- reutilizo surrogate key de rama.estacion
    codigo              CHAR(3) NOT NULL UNIQUE,
    nombre_estacion     VARCHAR(100) NOT NULL,
    alcaldia_id         SMALLINT NOT NULL REFERENCES rama_olap.dim_alcaldia,
    latitud             NUMERIC(9,6) NOT NULL,
    longitud            NUMERIC(9,6) NOT NULL,
    activo              BOOLEAN NOT NULL,

    CONSTRAINT latitud_valida CHECK (latitud BETWEEN -90 AND 90),
    CONSTRAINT longitud_valida CHECK (longitud BETWEEN -180 AND 180)
);

COMMENT ON TABLE rama_olap.dim_estacion IS
  'Estaciones de monitoreo: foto del período **vigente** (fecha_fin IS NULL en rama.estacion_periodo). '
  'Si se necesita historial SCD2 completo, consultar rama.estacion_periodo directamente. '
  'Aquí usamos la geografía actual para simplificar el cubo BI.';

CREATE INDEX idx_dim_estacion_alcaldia ON rama_olap.dim_estacion(alcaldia_id);
CREATE INDEX idx_dim_estacion_activo ON rama_olap.dim_estacion(activo);

---

-- dim_calidad_aire_imeca: mapeo de IMECA (parcial; ver comentarios)
CREATE TABLE IF NOT EXISTS rama_olap.dim_calidad_aire_imeca (
    contaminante_codigo CHAR(5) PRIMARY KEY REFERENCES rama.contaminante(codigo),
    imeca_50_breakpoint REAL,      -- concentración @ 50 IMECA (µg/m³ o ppb según unidad)
    imeca_100_breakpoint REAL,     -- concentración @ 100 IMECA (límite de protección)
    imeca_150_breakpoint REAL,     -- concentración @ 150 IMECA
    imeca_200_breakpoint REAL,     -- concentración @ 200 IMECA
    categoria_imeca_100 VARCHAR(50),      -- "Buena", "Regular", "Mala", etc. @ 100 IMECA
    fuente              TEXT,            -- ref. normativa (ej. NADF-009-AIRE-2006)
    verificado          BOOLEAN DEFAULT FALSE
);

COMMENT ON TABLE rama_olap.dim_calidad_aire_imeca IS
  'Tabla de referencia IMECA por contaminante. SOLO O3 tiene valores verificados contra '
  'NADF-009-AIRE-2006 (100 IMECA @ 0.110 ppm, 200 IMECA @ 0.220 ppm). '
  'Los demás están NULL, pendiente de completar con fuentes oficiales. '
  'La tabla indices_normalizado (0-100 escalado por valor_min/valor_max) es la alternativa '
  'defendible y usada en el fact table.';

-- Insertar solo O3 verificado (NADF-009-AIRE-2006, hora)
INSERT INTO rama_olap.dim_calidad_aire_imeca
  (contaminante_codigo, imeca_100_breakpoint, imeca_200_breakpoint,
   categoria_imeca_100, fuente, verificado)
VALUES ('O3', 0.110, 0.220, 'Regular',
        'NADF-009-AIRE-2006: 100 IMECA @ 0.110 ppm/h, 200 IMECA @ 0.220 ppm/h',
        TRUE)
ON CONFLICT DO NOTHING;

-- Los demás contaminantes: NULL como placeholder
INSERT INTO rama_olap.dim_calidad_aire_imeca (contaminante_codigo, verificado)
SELECT codigo, FALSE FROM rama.contaminante WHERE codigo != 'O3'
ON CONFLICT DO NOTHING;
