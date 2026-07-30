-- ============================================================================
-- 05_indices.sql — Índices estratégicos para queries OLTP
-- ============================================================================
-- Índices no heredados (adicionales a los ya creados en 03/04)
-- Cubren patrones de consulta: por estación, por contaminante, por fecha, geoespacial
-- ============================================================================

-- Índice compuesto para queries frecuentes: (estacion_id, contaminante, fecha rango)
CREATE INDEX idx_medicion_est_cont_fecha
    ON rama.medicion(estacion_id, contaminante_codigo, medido_en)
    WHERE valor IS NOT NULL;

-- Índice por alcaldía (join frequente en queries de zona)
CREATE INDEX idx_estacion_periodo_alcaldia
    ON rama.estacion_periodo(alcaldia)
    WHERE activo = TRUE;

-- Índice para queries de último período activo de una estación
CREATE INDEX idx_estacion_periodo_activos
    ON rama.estacion_periodo(estacion_id, fecha_fin DESC NULLS FIRST)
    WHERE activo = TRUE;

-- Índice partial para validación: solo registros con valor en rango sospechoso
-- (se usa en queries de auditoría)
CREATE INDEX idx_medicion_valores_sospechosos
    ON rama.medicion(estacion_id, contaminante_codigo, medido_en)
    WHERE valor IS NOT NULL;
