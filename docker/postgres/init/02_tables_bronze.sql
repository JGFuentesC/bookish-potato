-- ============================================================================
-- 02_tables_bronze.sql — Capa Bronze: datos horarios crudos RAMA
-- ============================================================================
-- 55M filas, ~200 MB. Sin validaciones, fiel al XLS original.
-- ============================================================================

CREATE TABLE IF NOT EXISTS bronze.rama_horaria (
    fecha         DATE          NOT NULL,
    hora          SMALLINT      NOT NULL CHECK (hora BETWEEN 0 AND 23),
    estacion      TEXT          NOT NULL,
    contaminante  TEXT          NOT NULL,
    valor         REAL
);
