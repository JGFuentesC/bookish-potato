-- ============================================================================
-- 04_mediciones.sql — Tabla de hechos (mediciones) + auditoría de cargas
-- ============================================================================
-- Mediciones horarias: tabla de hechos particionada por año
-- Lote_carga: auditoría de operaciones batch
-- ============================================================================

-- Tabla de hechos: mediciones horarias
-- No particionada (ver notas: PostgreSQL requiere que PK esté contenida en clave de partición,
-- incompatible con EXTRACT(YEAR FROM ...). Para OLTP puro, índices son suficientes.)
CREATE TABLE IF NOT EXISTS rama.medicion (
    medido_en               TIMESTAMP      NOT NULL,
    estacion_id             SMALLINT       NOT NULL,
    contaminante_codigo     CHAR(5)        NOT NULL,
    valor                   REAL,

    UNIQUE (medido_en, estacion_id, contaminante_codigo),
    FOREIGN KEY (estacion_id) REFERENCES rama.estacion(estacion_id) ON DELETE RESTRICT,
    FOREIGN KEY (contaminante_codigo) REFERENCES rama.contaminante(codigo) ON DELETE RESTRICT
);

COMMENT ON TABLE rama.medicion IS
  'Tabla de hechos: mediciones horarias de contaminantes por estación. '
  'UNIQUE (medido_en, estacion_id, contaminante_codigo) previene duplicados. '
  '~55M filas, 40 años de datos. No particionada (OLTP puro).';

COMMENT ON COLUMN rama.medicion.medido_en IS 'Timestamp (fecha + hora en una columna)';
COMMENT ON COLUMN rama.medicion.estacion_id IS 'FK a estacion.estacion_id';
COMMENT ON COLUMN rama.medicion.contaminante_codigo IS 'FK a contaminante.codigo';
COMMENT ON COLUMN rama.medicion.valor IS 'Valor medido (REAL, NULL permitido para datos faltantes)';

-- Índices sobre tabla de hechos
CREATE INDEX idx_medicion_estacion_medido_en
    ON rama.medicion(estacion_id, medido_en);
CREATE INDEX idx_medicion_contaminante_medido_en
    ON rama.medicion(contaminante_codigo, medido_en);
CREATE INDEX idx_medicion_contaminante_estacion
    ON rama.medicion(contaminante_codigo, estacion_id);

-- Tabla de auditoría: registro de cargas batch
CREATE TABLE IF NOT EXISTS rama.lote_carga (
    lote_id             BIGINT        PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    anio                SMALLINT      NOT NULL,
    fecha_carga         TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archivo_origen      VARCHAR(255),
    filas_insertadas    BIGINT        NOT NULL DEFAULT 0,
    filas_rechazadas    BIGINT        NOT NULL DEFAULT 0,
    comentarios         TEXT,

    CONSTRAINT anio_valido CHECK (anio BETWEEN 1980 AND 2100),
    CONSTRAINT filas_positivas CHECK (filas_insertadas >= 0 AND filas_rechazadas >= 0)
);

COMMENT ON TABLE rama.lote_carga IS
  'Auditoría de operaciones batch: registro de cada carga anual. '
  'No es FK desde medicion (mantiene tabla de hechos liviana); '
  'idempotencia garantizada por PK de medicion.';

COMMENT ON COLUMN rama.lote_carga.lote_id IS 'Identificador único del lote';
COMMENT ON COLUMN rama.lote_carga.anio IS 'Año de datos cargados';
COMMENT ON COLUMN rama.lote_carga.fecha_carga IS 'Timestamp de la operación de carga';
COMMENT ON COLUMN rama.lote_carga.archivo_origen IS 'Ruta o nombre del archivo fuente (opcional)';
COMMENT ON COLUMN rama.lote_carga.filas_insertadas IS 'Cantidad de filas INSERT exitosas';
COMMENT ON COLUMN rama.lote_carga.filas_rechazadas IS 'Cantidad de filas que fallaron validación';
COMMENT ON COLUMN rama.lote_carga.comentarios IS 'Notas sobre la carga (errores, anomalías, etc.)';

CREATE INDEX idx_lote_carga_anio ON rama.lote_carga(anio);
CREATE INDEX idx_lote_carga_fecha_carga ON rama.lote_carga(fecha_carga DESC);
