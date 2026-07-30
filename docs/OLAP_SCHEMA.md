# Schema OLAP (Snowflake) — RAMA

Cubo analítico para BI sobre datos de calidad del aire (CDMX/ZMVM).

## Diseño

**Schema**: `rama_olap` (separado del OLTP `rama`, sin cambios en producción)

**Tipo**: Snowflake (dimensiones normalizadas, fact table desnormalizado)

```
┌─────────────────────────────────────────────────────────────────┐
│                         DIMENSIONES                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  dim_tiempo ◄─ fact_medicion_hora ─► dim_contaminante           │
│    (hora)         (50.3M filas)          │ (snowflake)           │
│                                          │                       │
│                   ├─► dim_estacion ─────┤ dim_categoria_        │
│                   │   (54 estaciones)    │  contaminante         │
│                   │    ├─► dim_alcaldia  │   (Gases/             │
│                   │    │   (26 limpias)  │    Partículas)        │
│                   │    └─► (geográfico)  │                       │
│                   │                      └─► dim_calidad_aire_   │
│                   │                          imeca (ref.)        │
│                   │                                              │
│                   └─ AGREGADOS (vistas materializadas):         │
│                      ├─ agg_medicion_diaria                      │
│                      └─ agg_medicion_mensual                     │
└─────────────────────────────────────────────────────────────────┘
```

## Dimensiones

### `dim_tiempo` (350,640 filas)
Grano **hora** (1986-01-01 00:00 → 2025-12-31 23:00)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `tiempo_id` | BIGINT (PK) | Timestamp epoch × 3600 |
| `fecha_hora` | TIMESTAMP | Fecha + hora |
| `fecha` | DATE | Fecha (para joins) |
| `anio`, `trimestre`, `mes`, `dia`, `hora` | SMALLINT | Componentes de fecha/hora |
| `dia_semana` | SMALLINT | 1=lun ... 7=dom |
| `es_fin_semana` | BOOLEAN | Sábado/domingo |
| `estacion_del_anio` | VARCHAR | Invierno/Primavera/Verano/Otoño |

### `dim_alcaldia` (~26 filas)
Geografía **normalizada** y deduplicada

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `alcaldia_id` | SMALLINT (PK) | Surrogate key |
| `nombre_alcaldia` | VARCHAR | Nombre canonical (sin HTML entities) |
| `entidad` | VARCHAR | CDMX ó Estado de México |
| `latitud_centroide`, `longitud_centroide` | NUMERIC | Opcional, para heatmaps |

**Limpieza**: `rama.estacion_periodo.alcaldia` (31 variantes sucias: HTML entities + typos) → 26 canónicas (16 CDMX + 12 Edomex)

### `dim_categoria_contaminante` (2 filas)
Clasificación química

| Columna | Tipo |
|---------|------|
| `categoria_id` | SMALLINT (PK) |
| `nombre_categoria` | VARCHAR | Gases ó Partículas |

### `dim_contaminante` (9 filas)
Catálogo copiado de `rama.contaminante`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `contaminante_id` | SMALLINT (PK) | Surrogate key |
| `codigo` | CHAR(5) | CO, NO, NO2, NOX, O3, PM10, PM25, PMCO, SO2 |
| `nombre` | VARCHAR | Nombre descriptivo |
| `unidad` | VARCHAR | ppm, ppb, µg/m³ |
| `categoria_id` | SMALLINT (FK) | Gases/Partículas |
| `valor_min`, `valor_max` | REAL | Rangos físicos para índice normalizado |

### `dim_estacion` (54 filas)
Período **vigente** (más reciente) de cada estación

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `estacion_id` | SMALLINT (PK) | Reutilizado de `rama.estacion` |
| `codigo` | CHAR(3) | ACO, LPR, MER, TLA, etc. |
| `nombre_estacion` | VARCHAR | Nombre descriptivo |
| `alcaldia_id` | SMALLINT (FK) | Referencia a `dim_alcaldia` limpia |
| `latitud`, `longitud` | NUMERIC | WGS84 |
| `activo` | BOOLEAN | Estado actual |

**Nota**: Aquí usamos el período más reciente. Si se necesita el historial completo (SCD Type 2), consultar `rama.estacion_periodo` directamente.

### `dim_calidad_aire_imeca` (9 filas)
Tabla de referencia para IMECA (**parcial, verificado = O3 only**)

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `contaminante_codigo` | CHAR(5) (PK) | FK a `rama.contaminante` |
| `imeca_50_breakpoint`, `imeca_100_breakpoint`, `imeca_150_breakpoint`, `imeca_200_breakpoint` | REAL | Concentraciones @ IMECA puntos |
| `categoria_imeca_100` | VARCHAR | "Buena", "Regular", etc. @ 100 IMECA |
| `fuente` | TEXT | Referencia normativa (NADF-009-AIRE-2006) |
| `verificado` | BOOLEAN | TRUE si breakpoints fueron validados |

**Limitación**: Solo **O3** tiene valores verificados (100 IMECA @ 0.110 ppm, 200 IMECA @ 0.220 ppm, según NADF-009-AIRE-2006). Los demás contaminantes tienen NULL como placeholder, pendientes de completar con fuentes oficiales SEDEMA. En vez de datos IMECA inventados, usamos índice normalizado escalado 0-100 basado en `valor_min`/`valor_max` de cada contaminante.

## Fact Table

### `fact_medicion_hora` (50.3M filas)
Mediciones horarias con índice normalizado derivado

| Columna | Tipo | Descripción |
|---------|------|-------------|
| `tiempo_id` | BIGINT (FK) | A `dim_tiempo` |
| `estacion_id` | SMALLINT (FK) | A `dim_estacion` |
| `contaminante_id` | SMALLINT (FK) | A `dim_contaminante` |
| `valor` | REAL | Valor medido (NULL = dato faltante, 18-38% según contaminante) |
| `indice_normalizado` | REAL | `100 * (valor - valor_min) / (valor_max - valor_min)`, NULL si valor es NULL |

**Índices**:
- `(estacion_id, tiempo_id)` — queries por estación + período
- `(contaminante_id, tiempo_id)` — queries por contaminante + período
- `(tiempo_id)` — queries por fecha
- `(estacion_id, contaminante_id)` — queries bidimensionales

## Agregados (Vistas Materializadas)

### `agg_medicion_diaria`
Grano día: promedios, min/max, índice normalizado, % completitud

| Columna | Tipo |
|---------|------|
| `fecha` | DATE |
| `estacion_id`, `contaminante_id` | SMALLINT |
| `valor_promedio`, `valor_minimo`, `valor_maximo` | REAL |
| `indice_normalizado` | REAL |
| `mediciones_totales`, `mediciones_validas` | INT |
| `pct_completitud` | REAL (0-100) |

### `agg_medicion_mensual`
Grano mes: mismas métricas

| Columna | Tipo |
|---------|------|
| `anio`, `mes` | SMALLINT |
| `fecha_primer_dia_mes` | DATE |
| `estacion_id`, `contaminante_id` | SMALLINT |
| `valor_promedio`, `valor_minimo`, `valor_maximo` | REAL |
| `indice_normalizado` | REAL |
| `mediciones_totales`, `mediciones_validas` | INT |
| `pct_completitud` | REAL (0-100) |

**Performance**: Dashboard lee agregados, no el fact de 50M filas. Refrescables con `REFRESH MATERIALIZED VIEW`.

## ETL: Construcción del Cubo

```bash
uv run python scripts/construir_olap.py
```

Pasos:
1. Ejecuta DDL (`docker/postgres/olap/*.sql` en orden)
2. Puebla `dim_alcaldia`: limpia HTML entities, deduplica alcaldías sucias
3. Puebla dimensiones (contaminantes, categorías, estaciones) desde `rama.*`
4. Genera `dim_tiempo` con `generate_series`
5. Puebla `fact_medicion_hora` desde `rama.medicion` en batches/año
6. Refresca vistas materializadas
7. Imprime validación final (conteos, sin duplicados, etc.)

Tiempo: ~30-40 minutos para 50M filas (dependiendo del hardware)

Opcional: Reconstruir solo un año
```bash
uv run python scripts/construir_olap.py --anio 2020
```

## Índice Normalizado

**Definición**: `100 * (valor - valor_min) / (valor_max - valor_min)`

Escala 0-100 agnóstica a unidades (funciona para ppm, ppb, µg/m³). Calculado a partir de rangos físicos ya documentados en `rama.contaminante`, sin datos IMECA externos.

**Ventajas**:
- Defendible (datos existentes en BD)
- Comparables entre contaminantes (misma escala)
- No requiere certificación regulatoria

**Uso**: Dashboard, rankings, KPIs

## Notas

- **SCD Type 2**: La historia temporal completa de estaciones vive en `rama.estacion_periodo` (OLTP). El cubo usa la foto actual (período más reciente).
- **NULLs reales**: 18-38% de mediciones son NULL (sensor inactivo). Se explota como métrica de completitud en dashboard, no se interpola.
- **Timezones**: Todas las fechas en UTC (como origen en `rama.medicion`).
- **Validación**: Triggers de OLTP (`trg_medicion_validar_rango`) garantizan que valores en fact esté dentro de rango; índice normalizado es derivado (no falla si valor está fuera de rango, solo sería > 100 o < 0).
