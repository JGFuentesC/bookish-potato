-- ============================================================================
-- 01_schema_olap.sql — Crear schema OLAP (snowflake)
-- ============================================================================
-- Schema separado rama_olap para agregaciones y cubo BI, sin tocar rama (OLTP)
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS rama_olap;

COMMENT ON SCHEMA rama_olap IS
  'Schema OLAP (snowflake) para análisis históricos de calidad del aire. '
  'Contiene dimensiones (tiempo, geografía, contaminantes, estaciones) '
  'y fact table de mediciones horarias con agregados para dashboard BI.';
