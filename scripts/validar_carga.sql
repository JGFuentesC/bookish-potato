-- ============================================================================
-- validar_carga.sql — Validaciones post-ingesta de RAMA OLTP
-- ============================================================================
-- Ejecutar con: docker compose exec -T postgres psql -U rama -d rama -f validar_carga.sql

\echo '====== VALIDACIÓN DE CARGA RAMA OLTP ======'
\echo

-- 1. Conteos por tabla
\echo '[1/6] Conteos por tabla'
SELECT
  (SELECT COUNT(*) FROM rama.contaminante) as contaminantes,
  (SELECT COUNT(*) FROM rama.estacion) as estaciones,
  (SELECT COUNT(*) FROM rama.estacion_periodo) as periodos,
  (SELECT COUNT(*) FROM rama.medicion) as mediciones,
  (SELECT COUNT(*) FROM rama.lote_carga) as lotes_cargados;
\echo

-- 2. Verificar sin duplicados en medicion
\echo '[2/6] Verificar UNIQUE constraint (medicion)'
SELECT COUNT(*) as duplicados_detectados
FROM (
  SELECT medido_en, estacion_id, contaminante_codigo, COUNT(*) as cnt
  FROM rama.medicion
  GROUP BY medido_en, estacion_id, contaminante_codigo
  HAVING COUNT(*) > 1
) t;
\echo

-- 3. Verificar valores dentro de rango
\echo '[3/6] Valores fuera de rango (violaciones de trigger)'
SELECT COUNT(*) as fuera_de_rango
FROM rama.medicion m
JOIN rama.contaminante c ON m.contaminante_codigo = c.codigo
WHERE m.valor IS NOT NULL
  AND (m.valor < c.valor_min OR m.valor > c.valor_max);
\echo

-- 4. Verificar periodos no solapados
\echo '[4/6] Periodos solapados (violaciones de SCD Type 2)'
SELECT COUNT(*) as solapamientos
FROM rama.estacion_periodo ep1
JOIN rama.estacion_periodo ep2
  ON ep1.estacion_id = ep2.estacion_id
  AND ep1.periodo_id < ep2.periodo_id
WHERE (ep1.fecha_fin IS NULL OR ep2.fecha_inicio <= ep1.fecha_fin)
  AND (ep2.fecha_fin IS NULL OR ep1.fecha_inicio <= ep2.fecha_fin);
\echo

-- 5. Rango de fechas de mediciones
\echo '[5/6] Rango de fechas en mediciones'
SELECT
  MIN(medido_en)::date as fecha_minima,
  MAX(medido_en)::date as fecha_maxima,
  COUNT(DISTINCT DATE(medido_en)) as dias_unicos,
  COUNT(DISTINCT EXTRACT(YEAR FROM medido_en)::int) as anos_cubiertos
FROM rama.medicion;
\echo

-- 6. Cobertura por estación
\echo '[6/6] Estaciones con datos (verificar que todas tienen registros)'
SELECT
  e.codigo,
  ep.nombre_estacion,
  COUNT(*) as mediciones,
  COUNT(DISTINCT DATE(m.medido_en)) as dias_con_datos,
  MIN(DATE(m.medido_en)) as primer_dato,
  MAX(DATE(m.medido_en)) as ultimo_dato
FROM rama.estacion e
LEFT JOIN rama.estacion_periodo ep ON e.estacion_id = ep.estacion_id AND ep.activo = TRUE
LEFT JOIN rama.medicion m ON e.estacion_id = m.estacion_id
GROUP BY e.codigo, ep.nombre_estacion
ORDER BY COUNT(*) DESC
LIMIT 10;
\echo

\echo '====== FIN DE VALIDACIÓN ======'
