-- ============================================================================
-- 06_indexes.sql — Indices para cubos de consulta BI
-- ============================================================================
-- Se ejecutan despues de la carga para no relentizarla.
-- ============================================================================

-- Bronze: cubo principal de agregacion (clave para silver transform)
CREATE INDEX IF NOT EXISTS idx_bronze_fecha_est_cont
    ON bronze.rama_horaria (fecha, estacion, contaminante);

-- Silver: particion logica via indice parcial (solo filas validas)
CREATE INDEX IF NOT EXISTS idx_silver_valido_fecha_est_cont
    ON silver.rama_horaria_validada (fecha, estacion, contaminante)
    WHERE flag_valido;

-- Silver: busqueda por estacion en consultas de calidad
CREATE INDEX IF NOT EXISTS idx_silver_estacion
    ON silver.rama_horaria_validada (estacion, contaminante);

-- Gold: cubo de tendencias (serie de tiempo por contaminante)
CREATE INDEX IF NOT EXISTS idx_gold_cont_fecha
    ON gold.rama_mensual_bi (dim_contaminante, dim_fecha);

-- Gold: cubo de ranking (top estaciones por contaminante)
CREATE INDEX IF NOT EXISTS idx_gold_est_cont
    ON gold.rama_mensual_bi (dim_estacion, dim_contaminante);

-- Gold: cubo compuesto (filtro completo del dashboard)
CREATE INDEX IF NOT EXISTS idx_gold_full
    ON gold.rama_mensual_bi (dim_contaminante, dim_estacion, dim_fecha);

-- Gold: cubo de estacionalidad (mes x contaminante)
CREATE INDEX IF NOT EXISTS idx_gold_cont_mes
    ON gold.rama_mensual_bi (dim_contaminante, dim_mes);

-- Gold: soporte para busquedas geo (estacion + lat_lon)
CREATE INDEX IF NOT EXISTS idx_gold_estacion
    ON gold.rama_mensual_bi (dim_estacion);
