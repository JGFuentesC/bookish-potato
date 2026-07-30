-- ============================================================================
-- 04_agregados.sql — Vistas materializadas para performance del dashboard
-- ============================================================================

-- agg_medicion_diaria: agregación a grano día
CREATE MATERIALIZED VIEW IF NOT EXISTS rama_olap.agg_medicion_diaria AS
SELECT
    dt.fecha,
    f.estacion_id,
    f.contaminante_id,
    ROUND(AVG(f.valor)::NUMERIC, 2) as valor_promedio,
    MIN(f.valor) as valor_minimo,
    MAX(f.valor) as valor_maximo,
    ROUND(AVG(f.indice_normalizado)::NUMERIC, 1) as indice_normalizado,
    COUNT(*) as mediciones_totales,
    COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END) as mediciones_validas,
    ROUND(100.0 * COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END) / COUNT(*)::NUMERIC, 1)
        as pct_completitud
FROM rama_olap.fact_medicion_hora f
JOIN rama_olap.dim_tiempo dt ON f.tiempo_id = dt.tiempo_id
GROUP BY dt.fecha, f.estacion_id, f.contaminante_id;

COMMENT ON MATERIALIZED VIEW rama_olap.agg_medicion_diaria IS
  'Agregación a nivel día: promedios, min/max, índice normalizado, '
  'conteos de mediciones y % de completitud. Refrescable vía REFRESH.';

CREATE INDEX idx_agg_medicion_diaria_fecha ON rama_olap.agg_medicion_diaria(fecha);
CREATE INDEX idx_agg_medicion_diaria_estacion_fecha
    ON rama_olap.agg_medicion_diaria(estacion_id, fecha DESC);
CREATE INDEX idx_agg_medicion_diaria_contaminante_fecha
    ON rama_olap.agg_medicion_diaria(contaminante_id, fecha DESC);

---

-- agg_medicion_mensual: agregación a grano mes
CREATE MATERIALIZED VIEW IF NOT EXISTS rama_olap.agg_medicion_mensual AS
SELECT
    dt.anio,
    dt.mes,
    DATE_TRUNC('month', MIN(dt.fecha_hora))::DATE as fecha_primer_dia_mes,
    f.estacion_id,
    f.contaminante_id,
    ROUND(AVG(f.valor)::NUMERIC, 2) as valor_promedio,
    MIN(f.valor) as valor_minimo,
    MAX(f.valor) as valor_maximo,
    ROUND(AVG(f.indice_normalizado)::NUMERIC, 1) as indice_normalizado,
    COUNT(*) as mediciones_totales,
    COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END) as mediciones_validas,
    ROUND(100.0 * COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END) / COUNT(*)::NUMERIC, 1)
        as pct_completitud
FROM rama_olap.fact_medicion_hora f
JOIN rama_olap.dim_tiempo dt ON f.tiempo_id = dt.tiempo_id
GROUP BY dt.anio, dt.mes, f.estacion_id, f.contaminante_id;

COMMENT ON MATERIALIZED VIEW rama_olap.agg_medicion_mensual IS
  'Agregación a nivel mes: mismas métricas que diaria. '
  'Para dashboard usamos esta cuando los rangos son largos (> 12 meses).';

CREATE INDEX idx_agg_medicion_mensual_anio_mes
    ON rama_olap.agg_medicion_mensual(anio, mes DESC);
CREATE INDEX idx_agg_medicion_mensual_estacion
    ON rama_olap.agg_medicion_mensual(estacion_id, anio, mes DESC);
CREATE INDEX idx_agg_medicion_mensual_contaminante
    ON rama_olap.agg_medicion_mensual(contaminante_id, anio, mes DESC);
