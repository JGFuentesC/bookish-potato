# RAMA OLTP — Base de Datos Relacional 4FN para Calidad del Aire (CDMX)

Modelo relacional normalizado **OLTP puro** para datos horarios de la **Red Automatica de Monitoreo Atmosferico** (RAMA), Ciudad de Mexico.

Fuente: [aire.cdmx.gob.mx](https://www.aire.cdmx.gob.mx) — Datos abiertos SEDEMA.

---

## Quick Start

### Levantar la BD

```bash
docker compose up -d
```

PostgreSQL estará en `postgresql://rama:rama@localhost:5433/rama`.

### Cargar datos (55M filas, ~70 minutos)

```bash
uv run python scripts/ingesta_batch.py
```

O solo un año para testing:

```bash
uv run python scripts/ingesta_batch.py --anio 2020
```

---

## Estructura

### Tablas (Schema: `rama`)

| Tabla | Filas | Propósito |
|-------|-------|----------|
| `contaminante` | 9 | Catálogo de contaminantes + rangos físicos |
| `estacion` | 54 | Códigos de estaciones (PK surrogate) |
| `estacion_periodo` | ~57 | Historia temporal (SCD Type 2) — cuándo cada estación está activa |
| `medicion` | 55.3M | Hechos (mediciones horarias) |
| `lote_carga` | ~40 | Auditoría de cargas batch |

### Modelo relacional (4FN)

```
contaminante ──1──┐
                   ├──→ medicion ←──1──┐
estacion ──1───┐  │                    │
               │  │  estacion_periodo ─┘
               └──→ (SCD Type 2)
```

**PK compuesta en `medicion`:**
```sql
UNIQUE (medido_en, estacion_id, contaminante_codigo)
```

### Validaciones

- **Trigger `trg_medicion_validar_rango`**: valor dentro de rango físico por contaminante
- **Trigger `trg_estacion_periodo_validar_solapamiento`**: periodos no solapados (SCD Type 2)
- **CHECK constraints**: latitud/longitud, fechas coherentes
- **FK constraints**: integridad referencial

### Índices estratégicos

```sql
idx_medicion_estacion_medido_en        -- queries por estación + tiempo
idx_medicion_contaminante_medido_en    -- queries por contaminante + tiempo
idx_medicion_est_cont_fecha            -- queries complejas
idx_estacion_periodo_geom (GIST)       -- queries geoespaciales ST_DWithin()
```

---

## Ejemplos de uso

### Últimas mediciones de una estación (7 días)

```sql
SELECT m.medido_en, m.valor
FROM rama.medicion m
JOIN rama.estacion e ON m.estacion_id = e.estacion_id
WHERE e.codigo = 'LPR'
  AND m.contaminante_codigo = 'PM25'
  AND m.medido_en >= NOW() - INTERVAL '7 days'
ORDER BY m.medido_en DESC
LIMIT 100;
```

### Estaciones cercanas a un punto (radio 5 km)

```sql
SELECT ep.nombre_estacion, ep.alcaldia,
       ST_Distance(ep.geom, ST_Point(-99.1332, 19.4326, 4326)::geography) as distancia_m
FROM rama.estacion_periodo ep
WHERE ST_DWithin(ep.geom, ST_Point(-99.1332, 19.4326, 4326)::geography, 5000)
  AND ep.activo = TRUE
ORDER BY distancia_m;
```

### Rango válido de un contaminante

```sql
SELECT * FROM rama.contaminante WHERE codigo = 'PM25';
-- Retorna: PM25, Particulas < 2.5 µm, µg/m³, 0.0, 1000.0
```

### Historia de actividad de una estación

```sql
SELECT * FROM rama.estacion_periodo
WHERE estacion_id = (SELECT estacion_id FROM rama.estacion WHERE codigo = 'ACO')
ORDER BY fecha_inicio;
```

---

## Archivos & Scripts

### Datos fuente (scripts de obtención)

- **`download_rama.sh`** — descarga históricos desde aire.cdmx.gob.mx (1986-2026)
- **`scripts/scrape_stations.py`** — extrae coordenadas desde SEDEMA

### Datos curados

- **`data/curated/rama_historica.parquet`** — mediciones horarias (55M filas)
- **`data/exposure/stations_catalog.json`** — metadata de estaciones (54 registros)
- **`data/exposure/periodos_estaciones.csv`** — ciclos de vida (57 períodos detectados)

### Scripts de procesamiento

- **`scripts/analizar_periodos_estacion.py`** — detecta cuándo cada estación está activa/inactiva (gap > 30 días = cambio de estado)
- **`scripts/ingesta_batch.py`** — carga batch con COPY (bulk insert) hacia PostgreSQL

### DDL (Docker init)

- **`docker/postgres/init/01_schema.sql`** — crear schema rama + PostGIS
- **`docker/postgres/init/02_catalogos.sql`** — tabla contaminante (rangos físicos)
- **`docker/postgres/init/03_estaciones.sql`** — tablas estacion + estacion_periodo (SCD Type 2)
- **`docker/postgres/init/04_mediciones.sql`** — tabla medicion + lote_carga
- **`docker/postgres/init/05_indices.sql`** — índices estratégicos
- **`docker/postgres/init/06_triggers.sql`** — triggers de validación

### Documentación

- **`docs/ER_DIAGRAM.md`** — diagrama entidad-relación (Mermaid)
- **`docs/TABLE_DIAGRAM.md`** — especificación física de tablas

---

## Análisis de periodos

La rama detecta automáticamente **cuándo cada estación está activa**:

- **51 estaciones** con 1 período continuo (operativas de forma estable)
- **3 estaciones** con múltiples períodos:
  - **BJU**: 1986-2005 (inactiva 2005-2015), 2015-2026 (reactiva)
  - **COY**: 2003-2023, 2024-2026 (mantenimiento/gap)
  - **SJA**: 2003-2023, 2024-2026 (mismo patrón)

Ver: `scripts/analizar_periodos_estacion.py`

---

## Requisitos

- Docker + Docker Compose
- Python 3.13+
- `uv` (package manager)

Dependencias Python:
- `polars` — procesamiento de datos
- `pydantic` — validación
- `psycopg[binary]` — driver PostgreSQL

---

## Verificación

```bash
# Conectar a la BD
docker compose exec -T postgres psql -U rama -d rama

# Contar registros por tabla
SELECT 
  (SELECT COUNT(*) FROM rama.contaminante) as contaminantes,
  (SELECT COUNT(*) FROM rama.estacion) as estaciones,
  (SELECT COUNT(*) FROM rama.estacion_periodo) as periodos,
  (SELECT COUNT(*) FROM rama.medicion) as mediciones;

-- Resultado esperado:
--  contaminantes | estaciones | periodos | mediciones
--                |            |          |
--              9 |         54 |       57 | 55350526
```

---

## Branches

- **`l00-ingesta`** — pipeline medallón (bronze/silver/gold, desnormalizado para BI)
- **`l01-oltp-olap`** (actual) — modelo relacional 4FN OLTP puro
- (futuro) **`l02-olap`** — agregaciones y star schema para análisis históricos

---

## Licencia

**GPLv3** (ver `LICENSE`).

Datos: Gobierno de la Ciudad de Mexico (SEDEMA), distribución bajo licencia de datos abiertos.
