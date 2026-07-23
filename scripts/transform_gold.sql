-- ============================================================================
-- transform_gold.sql — Silver → Gold (Exposure)
-- ============================================================================
-- Agrega datos horarios validos a nivel mensual por estacion y contaminante.
-- Une con catalogos para la tabla plana final de 24 columnas.
-- ============================================================================

TRUNCATE gold.rama_mensual_bi;

WITH monthly AS (
    SELECT
        s.estacion,
        s.contaminante,
        s.fecha AS fecha_raw,
        s.valor,
        DATE_TRUNC('month', s.fecha) AS mes_start,
        EXTRACT(DAYS FROM (DATE_TRUNC('month', s.fecha) + INTERVAL '1 month' - INTERVAL '1 day'))::INT AS dias_mes
    FROM silver.rama_horaria_validada s
    WHERE s.flag_valido
)
INSERT INTO gold.rama_mensual_bi (
    dim_fecha, dim_anio, dim_mes, dim_nombre_mes, dim_trimestre,
    dim_estacion_anio, dim_estacion, dim_nombre_estacion, dim_alcaldia,
    dim_lat_lon, dim_contaminante, dim_nombre_contaminante,
    mt_valor_mean, mt_valor_max, mt_valor_min, mt_valor_std,
    mt_valor_p50, mt_valor_p95, mt_valor_p98,
    mt_horas_validas, mt_horas_esperadas,
    mt_dias_con_dato, mt_dias_esperados, mt_pct_datos
)
SELECT
    -- ==== DIMENSIONES ====
    m.mes_start::DATE,

    EXTRACT(YEAR  FROM m.mes_start)::SMALLINT,
    EXTRACT(MONTH FROM m.mes_start)::SMALLINT,

    CASE EXTRACT(MONTH FROM m.mes_start)::INT
        WHEN 1  THEN 'Enero'      WHEN 2  THEN 'Febrero'
        WHEN 3  THEN 'Marzo'      WHEN 4  THEN 'Abril'
        WHEN 5  THEN 'Mayo'       WHEN 6  THEN 'Junio'
        WHEN 7  THEN 'Julio'      WHEN 8  THEN 'Agosto'
        WHEN 9  THEN 'Septiembre' WHEN 10 THEN 'Octubre'
        WHEN 11 THEN 'Noviembre'  WHEN 12 THEN 'Diciembre'
    END,

    EXTRACT(QUARTER FROM m.mes_start)::SMALLINT,

    CASE EXTRACT(MONTH FROM m.mes_start)::INT
        WHEN 12 THEN 'Invierno'
        WHEN 1  THEN 'Invierno'
        WHEN 2  THEN 'Invierno'
        WHEN 3  THEN 'Primavera'
        WHEN 4  THEN 'Primavera'
        WHEN 5  THEN 'Primavera'
        WHEN 6  THEN 'Verano'
        WHEN 7  THEN 'Verano'
        WHEN 8  THEN 'Verano'
        WHEN 9  THEN 'Otonio'
        WHEN 10 THEN 'Otonio'
        WHEN 11 THEN 'Otonio'
    END,

    m.estacion,
    e.nombre_estacion,
    e.alcaldia,
    e.lat_lon,

    m.contaminante,
    c.nombre_contaminante,

    -- ==== METRICAS ====
    AVG(m.valor)::REAL,
    MAX(m.valor)::REAL,
    MIN(m.valor)::REAL,
    STDDEV(m.valor)::REAL,

    PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY m.valor)::REAL,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY m.valor)::REAL,
    PERCENTILE_CONT(0.98) WITHIN GROUP (ORDER BY m.valor)::REAL,

    COUNT(*)::INTEGER,
    (24 * MAX(m.dias_mes))::INTEGER,
    COUNT(DISTINCT m.fecha_raw)::SMALLINT,
    MAX(m.dias_mes)::SMALLINT,

    (COUNT(*)::REAL / NULLIF((24 * MAX(m.dias_mes))::REAL, 0) * 100)::REAL

FROM monthly m
JOIN gold.cat_estaciones     e ON m.estacion     = e.estacion
JOIN gold.cat_contaminantes  c ON m.contaminante = c.contaminante
GROUP BY
    m.mes_start,
    m.estacion, e.nombre_estacion, e.alcaldia, e.lat_lon,
    m.contaminante, c.nombre_contaminante;
