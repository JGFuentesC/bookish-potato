# Diagrama Entidad-Relación (ER) — RAMA OLTP

Modelo relacional 4FN para datos horarios de calidad del aire.

```mermaid
erDiagram
    CONTAMINANTE ||--o{ MEDICION : mide
    ESTACION ||--o{ ESTACION_PERIODO : tiene
    ESTACION_PERIODO ||--o{ MEDICION : registra
    LOTE_CARGA ||--o{ MEDICION : audita

    CONTAMINANTE {
        char(5) codigo PK
        varchar(100) nombre
        varchar(20) unidad
        real valor_min
        real valor_max
    }

    ESTACION {
        smallint estacion_id PK
        char(3) codigo UK
        date fecha_creacion
    }

    ESTACION_PERIODO {
        bigint periodo_id PK
        smallint estacion_id FK
        varchar(100) nombre_estacion
        varchar(50) alcaldia
        numeric(9,6) latitud
        numeric(9,6) longitud
        geography geom
        date fecha_inicio
        date fecha_fin "NULL = vigente"
        boolean activo
    }

    MEDICION {
        timestamp medido_en PK
        smallint estacion_id FK
        char(5) contaminante_codigo FK
        real valor "NULL permitido"
    }

    LOTE_CARGA {
        bigint lote_id PK
        smallint anio
        timestamp fecha_carga
        varchar(255) archivo_origen
        bigint filas_insertadas
        bigint filas_rechazadas
        text comentarios
    }
```

## Notas de modelado

### Normalización (4FN)
- **Contaminante**: dimensión independiente, cada contaminante con su rango físico
- **Estacion**: surrogate key (`estacion_id`) para evitar cambios en PK si el código cambia
- **Estacion_Periodo**: SCD Type 2, permite historia temporal (estaciones que se cierran y reabre)
- **Medicion**: tabla de hechos desnormalizada (todas las mediciones en una tabla)
- **Lote_Carga**: auditoría independiente, sin FK desde medicion (evita overhead)

### Cardinalidades
- Un contaminante → muchas mediciones (1:N)
- Una estación → muchos períodos (1:N, SCD Type 2)
- Un período → muchas mediciones (1:N)
- Un lote → audita muchas mediciones (1:N, lógico, sin constraint)

### Características especiales
- **geom (GEOGRAPHY)**: columna generada de (latitud, longitud) para queries geoespaciales `ST_DWithin()`
- **fecha_fin IS NULL**: indica período actualmente vigente
- **valor IS NULL**: permitido, indica medición no disponible
- **UNIQUE (medido_en, estacion_id, contaminante_codigo)**: previene duplicados

### Constraints e Índices
- **PK UNIQUE**: previene duplicados de mediciones
- **FK**: integridad referencial con estacion y contaminante
- **EXCLUDE GIST**: validado con trigger en estacion_periodo (no periodos solapados)
- **GIST(geom)**: índice geoespacial para radio-búsquedas
- **Índices compuestos**: (estacion_id, medido_en), (contaminante_codigo, medido_en), etc.
- **Trigger validación**: rango físico de valores por contaminante

### Volumen esperado
- **Contaminantes**: 9 registros
- **Estaciones**: 54 registros
- **Periodos**: ~57 registros (SCD Type 2)
- **Mediciones**: ~55,350,000 registros (horarias, 1986-2026)
