-- ============================================================================
-- 01_schema.sql — Crear schema RAMA (OLTP)
-- ============================================================================
-- Modelo relacional 4FN para datos de calidad del aire RAMA (CDMX)
-- ============================================================================

-- Habilitar extensiones
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;

CREATE SCHEMA IF NOT EXISTS rama;

COMMENT ON SCHEMA rama IS
  'Schema OLTP para datos horarios de calidad del aire (Red Automatica de '
  'Monitoreo Atmosferico, CDMX). Modelo relacional 4FN con dimensiones '
  '(estacion, contaminante, estacion_periodo) e tabla de hechos (medicion).';
