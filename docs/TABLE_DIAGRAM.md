# Diagrama de Tablas — Especificación física RAMA OLTP

Definición completa de tablas, tipos de datos, constraints e índices.

```mermaid
classDiagram
    class Contaminante {
        char(5) codigo [PK]
        varchar(100) nombre [NOT NULL]
        varchar(20) unidad [NOT NULL]
        real valor_min [DEFAULT 0.0, NOT NULL]
        real valor_max [NOT NULL]
        --
        CHECK: valor_min >= 0 AND valor_max > valor_min
    }

    class Estacion {
        smallint estacion_id [PK, GENERATED ALWAYS AS IDENTITY]
        char(3) codigo [UNIQUE, NOT NULL]
        date fecha_creacion [DEFAULT CURRENT_DATE, NOT NULL]
        --
        CHECK: codigo ~ '^[A-Z]{3}$'
        INDEX: idx_estacion_codigo (codigo)
    }

    class EstacionPeriodo {
        bigint periodo_id [PK, GENERATED ALWAYS AS IDENTITY]
        smallint estacion_id [FK REFERENCES estacion, NOT NULL]
        varchar(100) nombre_estacion [NOT NULL]
        varchar(50) alcaldia [NOT NULL]
        numeric(9,6) latitud [NOT NULL]
        numeric(9,6) longitud [NOT NULL]
        geography geom [GENERATED ALWAYS AS (ST_Point(lon,lat,4326))]
        date fecha_inicio [NOT NULL]
        date fecha_fin [NULL = vigente]
        boolean activo [DEFAULT TRUE, NOT NULL]
        --
        CHECK: fecha_fin IS NULL OR fecha_inicio <= fecha_fin
        CHECK: latitud BETWEEN -90 AND 90
        CHECK: longitud BETWEEN -180 AND 180
        UNIQUE: (estacion_id) WHERE fecha_fin IS NULL
        TRIGGER: validar_periodos_no_solapados (BEFORE INSERT/UPDATE)
        INDEX: idx_estacion_periodo_estacion_id (estacion_id)
        INDEX: idx_estacion_periodo_geom USING GIST (geom)
        INDEX: idx_estacion_periodo_fecha_inicio (fecha_inicio)
        INDEX: idx_estacion_periodo_fecha_fin (fecha_fin)
    }

    class Medicion {
        timestamp medido_en [PK (parte 1), NOT NULL]
        smallint estacion_id [PK (parte 2), FK, NOT NULL]
        char(5) contaminante_codigo [PK (parte 3), FK, NOT NULL]
        real valor [NULL permitido, NULL significa dato faltante]
        --
        UNIQUE: (medido_en, estacion_id, contaminante_codigo)
        FK estacion_id -> Estacion.estacion_id [ON DELETE RESTRICT]
        FK contaminante_codigo -> Contaminante.codigo [ON DELETE RESTRICT]
        TRIGGER: validar_valor_contaminante (BEFORE INSERT/UPDATE)
        INDEX: idx_medicion_estacion_medido_en (estacion_id, medido_en)
        INDEX: idx_medicion_contaminante_medido_en (contaminante_codigo, medido_en)
        INDEX: idx_medicion_contaminante_estacion (contaminante_codigo, estacion_id)
        INDEX: idx_medicion_est_cont_fecha (estacion_id, contaminante_codigo, medido_en)
    }

    class LoteCarga {
        bigint lote_id [PK, GENERATED ALWAYS AS IDENTITY]
        smallint anio [NOT NULL, CHECK: BETWEEN 1980 AND 2100]
        timestamp fecha_carga [DEFAULT CURRENT_TIMESTAMP, NOT NULL]
        varchar(255) archivo_origen [NULL]
        bigint filas_insertadas [DEFAULT 0, NOT NULL]
        bigint filas_rechazadas [DEFAULT 0, NOT NULL]
        text comentarios [NULL]
        --
        CHECK: filas_insertadas >= 0 AND filas_rechazadas >= 0
        INDEX: idx_lote_carga_anio (anio)
        INDEX: idx_lote_carga_fecha_carga (fecha_carga DESC)
    }

    Estacion "1" -- "*" EstacionPeriodo : tiene
    Contaminante "1" -- "*" Medicion : mide
    EstacionPeriodo "1" -- "*" Medicion : registra
    LoteCarga "1" -- "*" Medicion : audita_logicamente
```

## Especificación de tipos de datos

| Tabla | Columna | Tipo | Restricción | Propósito |
|-------|---------|------|-------------|----------|
| contaminante | codigo | CHAR(5) | PK | Código único (ej: CO, NO2, PM25) |
| contaminante | nombre | VARCHAR(100) | NOT NULL | Nombre descriptivo en español |
| contaminante | unidad | VARCHAR(20) | NOT NULL | Unidad (ppm, ppb, µg/m³) |
| contaminante | valor_min | REAL | ≥ 0 | Mínimo físico permitido |
| contaminante | valor_max | REAL | > valor_min | Máximo físico permitido |
| estacion | estacion_id | SMALLINT | PK, IDENTITY | Surrogate key (~54 estaciones) |
| estacion | codigo | CHAR(3) | UNIQUE | Código de 3 letras (ACO, LPR, etc) |
| estacion | fecha_creacion | DATE | DEFAULT CURRENT_DATE | Auditoría |
| estacion_periodo | periodo_id | BIGINT | PK, IDENTITY | Surrogate key (~57 períodos) |
| estacion_periodo | estacion_id | SMALLINT | FK NOT NULL | Referencia a estación |
| estacion_periodo | nombre_estacion | VARCHAR(100) | NOT NULL | Nombre descriptivo |
| estacion_periodo | alcaldia | VARCHAR(50) | NOT NULL | Delegación/alcaldía |
| estacion_periodo | latitud | NUMERIC(9,6) | -90 a 90 | WGS84 (6 decimales ≈ 0.1m) |
| estacion_periodo | longitud | NUMERIC(9,6) | -180 a 180 | WGS84 (6 decimales ≈ 0.1m) |
| estacion_periodo | geom | GEOGRAPHY | GENERATED | Punto para `ST_DWithin()` |
| estacion_periodo | fecha_inicio | DATE | NOT NULL | Inicio del período |
| estacion_periodo | fecha_fin | DATE | NULL = vigente | Fin del período (SCD Type 2) |
| estacion_periodo | activo | BOOLEAN | DEFAULT TRUE | Indicador de actividad |
| medicion | medido_en | TIMESTAMP | PK (part 1) | Fecha + hora combinadas |
| medicion | estacion_id | SMALLINT | PK (part 2), FK | Referencia a estación |
| medicion | contaminante_codigo | CHAR(5) | PK (part 3), FK | Referencia a contaminante |
| medicion | valor | REAL | NULL permitido | Medición en unidad del contaminante |
| lote_carga | lote_id | BIGINT | PK, IDENTITY | Identificador único |
| lote_carga | anio | SMALLINT | NOT NULL | Año de datos cargados |
| lote_carga | fecha_carga | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Cuándo se cargó |
| lote_carga | archivo_origen | VARCHAR(255) | NULL | Fuente (para trazabilidad) |
| lote_carga | filas_insertadas | BIGINT | ≥ 0 | Contador de éxitos |
| lote_carga | filas_rechazadas | BIGINT | ≥ 0 | Contador de errores |
| lote_carga | comentarios | TEXT | NULL | Notas (errores, anomalías) |

## Triggers

### `trg_medicion_validar_rango`
- **Tabla**: medicion
- **Evento**: BEFORE INSERT/UPDATE
- **Lógica**: Valida que `valor` esté dentro de rango físico definido en `contaminante`
- **Rechazo**: Si valor < valor_min O valor > valor_max
- **Excepción**: NULL permitido (datos faltantes)

### `trg_estacion_periodo_validar_solapamiento`
- **Tabla**: estacion_periodo
- **Evento**: BEFORE INSERT/UPDATE
- **Lógica**: Garantiza:
  - Solo 1 período activo (fecha_fin IS NULL) por estación
  - Sin solapamientos de rango de fechas por estación
- **Mecanismo**: Validación en trigger (alternativa a EXCLUDE GIST que requiere clase de operador)

## Volúmenes esperados

| Tabla | Registros | Tamaño aprox | Notas |
|-------|-----------|--------------|-------|
| contaminante | 9 | <1 KB | Dimensión pequeña |
| estacion | 54 | <5 KB | Dimensión pequeña |
| estacion_periodo | ~57 | <10 KB | SCD Type 2 (pocas actualizaciones) |
| medicion | ~55,350,000 | ~2.5 GB | Hechos (40 años de datos horarios) |
| lote_carga | ~40 | <5 KB | Una fila por año de carga |

## Estrategia de carga

- **Bulk insert** con COPY (PostgreSQL native)
- **Validación** en trigger (no en Python)
- **Idempotencia** vía UNIQUE constraint en medicion
- **Auditoría** automática en lote_carga
