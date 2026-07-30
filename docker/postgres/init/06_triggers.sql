-- ============================================================================
-- 06_triggers.sql — Triggers de validación y auditoría
-- ============================================================================
-- Validación de rangos físicos y auditoría de cambios
-- ============================================================================

-- Función: validar que valor esté dentro del rango físico del contaminante
CREATE OR REPLACE FUNCTION rama.validar_valor_contaminante()
RETURNS TRIGGER AS $$
DECLARE
    v_valor_min REAL;
    v_valor_max REAL;
BEGIN
    -- Si valor es NULL, permitir (datos faltantes son válidos)
    IF NEW.valor IS NULL THEN
        RETURN NEW;
    END IF;

    -- Obtener rango del contaminante
    SELECT valor_min, valor_max
    INTO v_valor_min, v_valor_max
    FROM rama.contaminante
    WHERE codigo = NEW.contaminante_codigo;

    -- Si no existe el contaminante, rechazar
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Contaminante % desconocido', NEW.contaminante_codigo;
    END IF;

    -- Validar que el valor esté en rango
    IF NEW.valor < v_valor_min OR NEW.valor > v_valor_max THEN
        RAISE EXCEPTION
            'Valor % fuera de rango para contaminante %: [%.1f, %.1f]',
            NEW.valor, NEW.contaminante_codigo, v_valor_min, v_valor_max;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Trigger: antes de INSERT/UPDATE en medicion, validar rango
CREATE TRIGGER trg_medicion_validar_rango
    BEFORE INSERT OR UPDATE ON rama.medicion
    FOR EACH ROW
    EXECUTE FUNCTION rama.validar_valor_contaminante();

COMMENT ON TRIGGER trg_medicion_validar_rango ON rama.medicion IS
  'Valida que cada medición tenga un valor dentro del rango físico '
  'definido para su contaminante. Rechaza inserciones/updates inválidos.';

-- Función: trigger para auditoría de periodos solapados (complementario al EXCLUDE constraint)
-- Este es informativo; el constraint EXCLUDE ya previene en tiempo de creación
CREATE OR REPLACE FUNCTION rama.auditar_periodo_estacion()
RETURNS TRIGGER AS $$
BEGIN
    -- Si se intenta insertar un período activo con solapamiento,
    -- el constraint EXCLUDE lo rechazará antes de llegar aquí.
    -- Este trigger es informativo (podría registrar en una tabla de auditoría si es necesario)
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Opcionalmente, un trigger para marcar fecha_fin automáticamente al desactivar
-- (aunque por ahora no se requiere automático)
