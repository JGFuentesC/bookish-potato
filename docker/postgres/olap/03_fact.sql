-- ============================================================================
-- 03_fact.sql — Fact table (mediciones horarias) + índices
-- ============================================================================

-- Fact table: mediciones horarias con índice normalizado derivado
CREATE TABLE IF NOT EXISTS rama_olap.fact_medicion_hora (
    tiempo_id           BIGINT NOT NULL,
    estacion_id         SMALLINT NOT NULL,
    contaminante_id     SMALLINT NOT NULL,
    valor               REAL,                   -- NULL = dato faltante (sensor inactivo)
    indice_normalizado  REAL,                   -- 0..100, escalado de valor_min/valor_max

    FOREIGN KEY (tiempo_id) REFERENCES rama_olap.dim_tiempo,
    FOREIGN KEY (estacion_id) REFERENCES rama_olap.dim_estacion,
    FOREIGN KEY (contaminante_id) REFERENCES rama_olap.dim_contaminante
);

COMMENT ON TABLE rama_olap.fact_medicion_hora IS
  '50M+ mediciones horarias (1986-2025). '
  'indice_normalizado = 100 * (valor - valor_min) / (valor_max - valor_min), NULL si valor es NULL. '
  'Escalado 0-100 es agnóstico a unidades y defendible sin datos IMECA externos.';

-- Índices estratégicos para queries de BI
CREATE INDEX idx_fact_medicion_estacion_tiempo
    ON rama_olap.fact_medicion_hora(estacion_id, tiempo_id)
    WHERE valor IS NOT NULL;

CREATE INDEX idx_fact_medicion_contaminante_tiempo
    ON rama_olap.fact_medicion_hora(contaminante_id, tiempo_id)
    WHERE valor IS NOT NULL;

CREATE INDEX idx_fact_medicion_tiempo
    ON rama_olap.fact_medicion_hora(tiempo_id)
    WHERE valor IS NOT NULL;

CREATE INDEX idx_fact_medicion_est_cont
    ON rama_olap.fact_medicion_hora(estacion_id, contaminante_id)
    WHERE valor IS NOT NULL;
