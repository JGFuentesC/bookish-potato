# RAMA — OLTP + Cubo OLAP + Dashboard BI

Base de datos relacional **OLTP 4FN** + cubo analítico **Snowflake OLAP** + dashboard **McKinsey/PwC** para calidad del aire (CDMX/ZMVM).

Datos: [aire.cdmx.gob.mx](https://www.aire.cdmx.gob.mx) — Red Automatica de Monitoreo Atmosferico (SEDEMA), datos abiertos.

**Branches**:
- `main` — lanzamientos estables
- `l01-oltp-olap` — desarrollo actual (rama OLTP + OLAP)
- `l00-ingesta` — pipeline ETL medallón (anterior)

---

## Demo del Dashboard

![Dashboard OLAP — recorrido por los 4 tabs](docs/dashboard-demo.gif)

Recorrido por los 4 tabs: **Resumen** (serie temporal con min/max), **Mapa** (estaciones en Leaflet), **Rankings** (top/bottom estaciones y contaminantes) y **Calidad de Datos** (% completitud).

---

## Quick Start

### 1. Levantar servicios (PostgreSQL + API FastAPI)

```bash
docker compose up -d
```

- PostgreSQL (OLTP): `postgresql://rama:rama@localhost:5433/rama`
- API FastAPI: `http://localhost:8080`
- Dashboard: `http://localhost:8080/`

### 2. Cargar datos OLTP (55M filas, ~70 minutos)

```bash
uv run python scripts/ingesta_batch.py
```

O solo un año para testing:

```bash
uv run python scripts/ingesta_batch.py --anio 2020
```

### 3. Construir cubo OLAP (dimensiones + fact + agregados, ~30-40 minutos)

```bash
uv run python scripts/construir_olap.py
```

Una vez completado, el dashboard en `http://localhost:8080/` estará activo y consultará el cubo vía `/api/*`.

**Opcional**: Reconstruir solo un año
```bash
uv run python scripts/construir_olap.py --anio 2020
```

---

## Dashboard OLAP

Interfaz web corporativa (McKinsey/PwC) para explorar el cubo:

- **URL**: `http://localhost:8080/`
- **Filtros**: Contaminante (pills), alcaldía/estación (select), período (date range), granularidad (hora/día/mes)
- **Tabs**:
  1. **Resumen** — serie temporal con min/max
  2. **Mapa** — estaciones coloreadas por índice normalizado (Leaflet)
  3. **Rankings** — top/bottom estaciones y contaminantes
  4. **Calidad de Datos** — % completitud por contaminante/estación/año
- **KPIs**: Índice promedio, % completitud, estaciones activas, total mediciones
- **Charts**: Plotly (series, barras), Leaflet (mapa)
- **API**: Endpoints REST `/api/*` para programar consultas personalizadas

### API FastAPI (`/api`)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/health` | GET | Healthcheck |
| `/api/dimensiones/{tipo}` | GET | contaminantes \| categorias \| estaciones \| alcaldias |
| `/api/kpis` | GET | KPIs agregados (índice, completitud, estaciones, mediciones) |
| `/api/series-tiempo` | GET | Serie temporal (hora/día/mes), filtrable |
| `/api/mapa-estaciones` | GET | Últimas lecturas por estación |
| `/api/ranking/estaciones` | GET | Top/bottom estaciones por índice |
| `/api/ranking/contaminantes` | GET | Top contaminantes por índice |
| `/api/completitud` | GET | % completitud agrupado (contaminante/estación/año) |

Documentación interactiva Swagger: `http://localhost:8080/docs`

### Índice Normalizado (0-100)

Escala agnóstica a unidades, calculada de rangos físicos en catálogo:

```
indice = 100 * (valor - valor_min) / (valor_max - valor_min)
```

**Ventaja**: Defendible (datos ya en BD), comparable entre contaminantes.

**Nota**: Solo O3 tiene breakpoints IMECA verificados (NADF-009-AIRE-2006). Ver `docs/OLAP_SCHEMA.md` para detalles.

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
- **`scripts/ingesta_batch.py`** — carga batch OLTP con COPY (55M filas)
- **`scripts/construir_olap.py`** — construye cubo Snowflake: dimensiones + fact + agregados

### DDL (Docker init)

**OLTP** (`docker/postgres/init/`)
- **`01_schema.sql`** — crear schema rama + PostGIS
- **`02_catalogos.sql`** — tabla contaminante (rangos físicos)
- **`03_estaciones.sql`** — tablas estacion + estacion_periodo (SCD Type 2)
- **`04_mediciones.sql`** — tabla medicion + lote_carga
- **`05_indices.sql`** — índices estratégicos
- **`06_triggers.sql`** — triggers de validación

**OLAP** (`docker/postgres/olap/`) — se ejecuta manualmente después de cargar OLTP
- **`01_schema_olap.sql`** — crear schema rama_olap
- **`02_dimensiones.sql`** — dim_tiempo, dim_alcaldia (limpia), dim_categoria_contaminante, dim_contaminante, dim_estacion, dim_calidad_aire_imeca
- **`03_fact.sql`** — fact_medicion_hora + índices
- **`04_agregados.sql`** — agg_medicion_diaria, agg_medicion_mensual (vistas materializadas)

### API & Dashboard

- **`api/main.py`** — app FastAPI, 8 endpoints `/api/*`
- **`api/db.py`** — ConnectionPool psycopg
- **`api/consultas.py`** — lógica SQL contra rama_olap.*
- **`api/schemas.py`** — modelos Pydantic de respuesta
- **`api/static/index.html`** — dashboard (Inter, nav, tabs, filtros)
- **`api/static/app.js`** — estado, fetch `/api/*`, render Plotly/Leaflet
- **`api/static/estilos.css`** — paleta corporativa (navy + acento azul)
- **`docker/api/Dockerfile`** — build FastAPI app

### Documentación

- **`docs/ER_DIAGRAM.md`** — diagrama entidad-relación OLTP (Mermaid)
- **`docs/TABLE_DIAGRAM.md`** — especificación física OLTP
- **`docs/OLAP_SCHEMA.md`** — diseño cubo Snowflake, dimensiones, fact, agregados

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

- Docker + Docker Compose (v2+)
- Python 3.13+
- `uv` (package manager)

Dependencias Python (vía `uv`):
- `polars` — procesamiento de datos
- `pydantic` — validación
- `psycopg[binary,pool]` — driver PostgreSQL + pool conexiones
- `fastapi` — framework API REST
- `uvicorn[standard]` — servidor ASGI

---

## Verificación

### OLTP

```bash
# Conectar a la BD
docker compose exec -T postgres psql -U rama -d rama

# Contar registros por tabla (schema rama)
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

### OLAP + API

```bash
# Conectar a la BD
docker compose exec -T postgres psql -U rama -d rama

# Contar registros en cubo (schema rama_olap)
SELECT
  (SELECT COUNT(*) FROM rama_olap.dim_tiempo) as dim_tiempo,
  (SELECT COUNT(*) FROM rama_olap.dim_alcaldia) as dim_alcaldia_limpia,
  (SELECT COUNT(*) FROM rama_olap.dim_contaminante) as dim_contaminante,
  (SELECT COUNT(*) FROM rama_olap.dim_estacion) as dim_estacion,
  (SELECT COUNT(*) FROM rama_olap.fact_medicion_hora) as fact_mediciones,
  (SELECT COUNT(*) FROM rama_olap.agg_medicion_diaria) as agg_diaria,
  (SELECT COUNT(*) FROM rama_olap.agg_medicion_mensual) as agg_mensual;

-- Resultado esperado:
--  dim_tiempo | dim_alcaldia_limpia | dim_contaminante | dim_estacion | fact_mediciones | agg_diaria | agg_mensual
--  350,640    | 26                  | 9                | 54           | 50.3M           | ~13.8M     | ~468K
```

```bash
# Probar API
curl http://localhost:8080/health
# {"status":"ok"}

curl http://localhost:8080/api/kpis
# Retorna KPIs del período por defecto (últimos 12 meses)

# Ver documentación interactiva
open http://localhost:8080/docs
```

```bash
# Dashboard en navegador
open http://localhost:8080
```

---

## Estado

**Rama actual**: `l01-oltp-olap` (OLTP + OLAP + Dashboard)

Completado ✓:
- OLTP 4FN normalizado (schema `rama`, 50.3M mediciones)
- Cubo OLAP Snowflake (schema `rama_olap`, 26 dimensiones normalizadas, 50.3M fact, agregados)
- API FastAPI (8 endpoints REST)
- Dashboard McKinsey/PwC (4 tabs, filtros, KPIs, charts Plotly, mapa Leaflet)
- Limpieza de datos sucios (alcaldías con HTML entities → 26 canónicas)
- Índice normalizado (0-100, agnóstico a unidades)

En progreso:
- Completar IMECA breakpoints (O3 verificado, demás pendientes de SEDEMA)

**Otras ramas**:
- **`l00-ingesta`** — pipeline medallón (bronze/silver/gold, desnormalizado para BI, anterior)
- **`main`** — lanzamientos estables

---

## Licencia

**GPLv3** (ver `LICENSE`).

Datos: Gobierno de la Ciudad de Mexico (SEDEMA), distribución bajo licencia de datos abiertos.
