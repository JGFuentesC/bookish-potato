-- ============================================================================
-- 03_estaciones.sql — Tablas de estaciones (dimensión + SCD Type 2)
-- ============================================================================
-- Entidad estacion (códigos) + periodos de actividad (SCD Type 2)
-- ============================================================================

-- Tabla base de estaciones (códigos estables, surrogate key)
CREATE TABLE IF NOT EXISTS rama.estacion (
    estacion_id     SMALLINT      PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    codigo          CHAR(3)       NOT NULL UNIQUE,
    fecha_creacion  DATE          NOT NULL DEFAULT CURRENT_DATE,

    CONSTRAINT codigo_valido CHECK (codigo ~ '^[A-Z]{3}$')
);

COMMENT ON TABLE rama.estacion IS
  'Entidad estacion: mapeo entre código de 3 letras y surrogate key. '
  'Una estación puede tener múltiples "periodos" en estacion_periodo (SCD Type 2).';

COMMENT ON COLUMN rama.estacion.estacion_id IS 'Surrogate key (SMALLINT, ~54 estaciones)';
COMMENT ON COLUMN rama.estacion.codigo IS 'Código único de estación (3 letras, ej: ACO, LPR)';
COMMENT ON COLUMN rama.estacion.fecha_creacion IS 'Fecha de ingreso de la estación al catálogo';

-- Tabla SCD Type 2: periodos de actividad + metadata geográfica
CREATE TABLE IF NOT EXISTS rama.estacion_periodo (
    periodo_id      BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    estacion_id     SMALLINT      NOT NULL REFERENCES rama.estacion(estacion_id) ON DELETE RESTRICT,
    nombre_estacion VARCHAR(100)  NOT NULL,
    alcaldia        VARCHAR(50)   NOT NULL,
    latitud         NUMERIC(9,6)  NOT NULL,
    longitud        NUMERIC(9,6)  NOT NULL,
    fecha_inicio    DATE          NOT NULL,
    fecha_fin       DATE,                        -- NULL = vigente (actualmente activa)
    activo          BOOLEAN       NOT NULL DEFAULT TRUE,

    geom            GEOGRAPHY(Point, 4326) GENERATED ALWAYS AS
                    (ST_Point(longitud, latitud, 4326)) STORED,

    CONSTRAINT periodo_fechas_validas CHECK (fecha_fin IS NULL OR fecha_inicio <= fecha_fin),
    CONSTRAINT latitud_valida CHECK (latitud BETWEEN -90 AND 90),
    CONSTRAINT longitud_valida CHECK (longitud BETWEEN -180 AND 180)
);

COMMENT ON TABLE rama.estacion_periodo IS
  'Dimensión lenta (SCD Type 2) de estaciones: cada fila es un "periodo de '
  'actividad" de una estación. Una estación puede tener múltiples periodos si '
  'fue desactivada y reactivada. fecha_fin=NULL indica período vigente. '
  'geom es columna generada para queries geoespaciales.';

COMMENT ON COLUMN rama.estacion_periodo.periodo_id IS 'PK: identificador único del período';
COMMENT ON COLUMN rama.estacion_periodo.estacion_id IS 'FK a estacion.estacion_id';
COMMENT ON COLUMN rama.estacion_periodo.nombre_estacion IS 'Nombre descriptivo de la estación';
COMMENT ON COLUMN rama.estacion_periodo.alcaldia IS 'Delegación/alcaldía donde está ubicada';
COMMENT ON COLUMN rama.estacion_periodo.latitud IS 'Coordenada WGS84 (EPSG:4326)';
COMMENT ON COLUMN rama.estacion_periodo.longitud IS 'Coordenada WGS84 (EPSG:4326)';
COMMENT ON COLUMN rama.estacion_periodo.fecha_inicio IS 'Inicio del período de actividad';
COMMENT ON COLUMN rama.estacion_periodo.fecha_fin IS 'Fin del período (NULL = actualmente activa)';
COMMENT ON COLUMN rama.estacion_periodo.activo IS 'Indicador de actividad (redundante con fecha_fin, para claridad OLTP)';
COMMENT ON COLUMN rama.estacion_periodo.geom IS 'Punto geográfico (PostGIS), derivado de lat/lon';

-- Constraint EXCLUDE: prevenir periodos solapados por estación
-- (un estacion_id no puede tener dos periodos con rango de fechas que se superpongan)
ALTER TABLE rama.estacion_periodo
  ADD CONSTRAINT no_periodos_solapados
  EXCLUDE USING GIST (estacion_id WITH =, daterange(fecha_inicio, fecha_fin, '[]') WITH &&)
  WHERE (activo = TRUE);

-- Índices
CREATE INDEX idx_estacion_codigo ON rama.estacion(codigo);
CREATE INDEX idx_estacion_periodo_estacion_id ON rama.estacion_periodo(estacion_id);
CREATE INDEX idx_estacion_periodo_geom ON rama.estacion_periodo USING GIST(geom);
CREATE INDEX idx_estacion_periodo_fecha_inicio ON rama.estacion_periodo(fecha_inicio);
CREATE INDEX idx_estacion_periodo_fecha_fin ON rama.estacion_periodo(fecha_fin);
