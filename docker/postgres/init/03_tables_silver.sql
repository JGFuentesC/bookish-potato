-- ============================================================================
-- 03_tables_silver.sql — Capa Silver: datos validados con flags de calidad
-- ============================================================================
-- Agrega columnas de control sobre los datos bronze.
-- ============================================================================

CREATE TABLE IF NOT EXISTS silver.rama_horaria_validada (
    fecha               DATE          NOT NULL,
    hora                SMALLINT      NOT NULL CHECK (hora BETWEEN 0 AND 23),
    estacion            TEXT          NOT NULL,
    contaminante        TEXT          NOT NULL,
    valor               REAL,           -- NULL si el original era invalido

    flag_valido         BOOLEAN       NOT NULL,  -- TRUE si valor esta en rango fisico
    flag_fuera_rango    BOOLEAN       NOT NULL,  -- TRUE si valor excede el rango esperado
    flag_hora24_corregida BOOLEAN     NOT NULL   -- TRUE si HORA=24 fue corregida a 0
);
