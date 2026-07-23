-- ============================================================================
-- 04_tables_gold.sql — Capa Gold (Exposure): datos listos para BI
-- ============================================================================
-- Tabla plana con 24 columnas dim_* / mt_* identicas al CSV de Looker Studio.
-- ============================================================================

-- CataLogo de contaminantes
CREATE TABLE IF NOT EXISTS gold.cat_contaminantes (
    contaminante          TEXT  PRIMARY KEY,
    nombre_contaminante   TEXT  NOT NULL,
    unidad                TEXT  NOT NULL
);

-- CataLogo de estaciones
CREATE TABLE IF NOT EXISTS gold.cat_estaciones (
    estacion         TEXT    PRIMARY KEY,
    nombre_estacion  TEXT    NOT NULL,
    alcaldia         TEXT    NOT NULL,
    lat_lon          TEXT    NOT NULL
);

-- Tabla maestra mensual (Gold = Exposure, unificada)
CREATE TABLE IF NOT EXISTS gold.rama_mensual_bi (
    dim_fecha                DATE          NOT NULL,
    dim_anio                 SMALLINT      NOT NULL,
    dim_mes                  SMALLINT      NOT NULL,
    dim_nombre_mes           TEXT          NOT NULL,
    dim_trimestre            SMALLINT      NOT NULL,
    dim_estacion_anio        TEXT          NOT NULL,
    dim_estacion             TEXT          NOT NULL,
    dim_nombre_estacion      TEXT          NOT NULL,
    dim_alcaldia             TEXT          NOT NULL,
    dim_lat_lon              TEXT          NOT NULL,
    dim_contaminante         TEXT          NOT NULL,
    dim_nombre_contaminante  TEXT          NOT NULL,

    mt_valor_mean            REAL,
    mt_valor_max             REAL,
    mt_valor_min             REAL,
    mt_valor_std             REAL,
    mt_valor_p50             REAL,
    mt_valor_p95             REAL,
    mt_valor_p98             REAL,
    mt_horas_validas         INTEGER,
    mt_horas_esperadas       INTEGER,
    mt_dias_con_dato         SMALLINT,
    mt_dias_esperados        SMALLINT,
    mt_pct_datos             REAL
);
