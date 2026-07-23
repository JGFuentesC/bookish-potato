-- ============================================================================
-- transform_silver.sql — Bronze → Silver
-- ============================================================================
-- Valida cada fila horaria contra rangos fisicos conocidos por contaminante.
-- Las filas con valor fuera de rango se marcan con flag_fuera_rango = TRUE
-- y valor se conserva (para auditoria). Las filas con valor < 0 se marcan
-- como no validas (flag_valido = FALSE) y valor se anula.
-- HORA = 24 se normaliza a 0 (flag_hora24_corregida = TRUE).
-- ============================================================================

TRUNCATE silver.rama_horaria_validada;

INSERT INTO silver.rama_horaria_validada
    (fecha, hora, estacion, contaminante, valor,
     flag_valido, flag_fuera_rango, flag_hora24_corregida)
SELECT
    -- FECHA: corregir +1 dia si HORA era 24 (midnight del dia siguiente)
    CASE WHEN hora = 24
         THEN fecha + INTERVAL '1 day'
         ELSE fecha
    END::DATE,

    -- HORA: normalizar 24 → 0
    CASE WHEN hora = 24 THEN 0 ELSE hora END::SMALLINT,

    estacion,
    contaminante,

    -- VALOR: anular negativos (sentinel / errores de medicion)
    CASE WHEN valor < 0 THEN NULL ELSE valor END::REAL,

    -- FLAG: valido = TRUE si valor esta en rango [0, max_permitido]
    (valor IS NOT NULL AND valor >= 0
     AND valor <= (
        CASE contaminante
            WHEN 'CO'   THEN 50
            WHEN 'NO'   THEN 800
            WHEN 'NO2'  THEN 500
            WHEN 'NOX'  THEN 1000
            WHEN 'O3'   THEN 500
            WHEN 'PM10' THEN 2000
            WHEN 'PM25' THEN 1000
            WHEN 'PMCO' THEN 1000
            WHEN 'SO2'  THEN 1000
            ELSE 5000
        END
    )),

    -- FLAG: fuera de rango fisico (conservativo — solo para auditoria)
    (valor IS NOT NULL AND valor >= 0
     AND valor > (
        CASE contaminante
            WHEN 'CO'   THEN 50
            WHEN 'NO'   THEN 800
            WHEN 'NO2'  THEN 500
            WHEN 'NOX'  THEN 1000
            WHEN 'O3'   THEN 500
            WHEN 'PM10' THEN 2000
            WHEN 'PM25' THEN 1000
            WHEN 'PMCO' THEN 1000
            WHEN 'SO2'  THEN 1000
            ELSE 5000
        END
    )),

    -- FLAG: hora 24 corregida
    (hora = 24)::BOOLEAN

FROM bronze.rama_horaria;
