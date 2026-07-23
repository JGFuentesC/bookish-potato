# Arquitectura Medallon SQL — RAMA (PostgreSQL)

Este documento describe la transformacion de datos de calidad del aire RAMA
utilizando PostgreSQL con arquitectura medallon (Bronze → Silver → Gold).

---

## 1. Diagrama de arquitectura

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RAMA Medallon Pipeline                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  data/curated/               bronze                  silver         │
│  rama_historica.parquet  ──► rama_horaria  ──►  rama_horaria_      │
│   (55M filas horarias)        (crudo)            validada           │
│                                                    │               │
│                                          ┌─────────┘               │
│                                          ▼                          │
│  scripts/init_postgres.py           gold.rama_mensual_bi            │
│  (exporta CSV + COPY)               (76K filas, 24 cols)            │
│                                          │                          │
│                                          ▼                          │
│  Docker: rama-api (FastAPI)       GET /api/data?cont=...            │
│                                          │                          │
│                                          ▼                          │
│  Dashboard HTML                    data/exposure/                   │
│  ┌─ [📦 Archivo] embebido          rama_dashboard.html              │
│  └─ [🗄️ Servidor] PostgreSQL                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## 2. Docker Compose

```yaml
# compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg16   # PostgreSQL 16 + pgvector
    environment:
      POSTGRES_USER: rama
      POSTGRES_PASSWORD: rama
      POSTGRES_DB: rama
    ports:
      - "5433:5432"                 # externo para tools

  api:
    build: ./docker/api             # Python 3.13 + FastAPI + asyncpg
    environment:
      DATABASE_URL: postgresql://rama:rama@postgres:5432/rama
    ports:
      - "8080:8000"
```

**Arranque:**

```bash
# Construir e iniciar
docker compose up -d

# Esperar ~15s hasta que el healthcheck de PG pase
docker compose ps
```

## 3. Capa Bronze — `bronze.rama_horaria`

**Tabla:** 55,350,526 filas — copia fiel de los XLS originales, sin validaciones.

```sql
CREATE TABLE bronze.rama_horaria (
    fecha         DATE          NOT NULL,
    hora          SMALLINT      NOT NULL CHECK (hora BETWEEN 0 AND 23),
    estacion      TEXT          NOT NULL,
    contaminante  TEXT          NOT NULL,
    valor         REAL            -- NULL si no hay medicion
);
```

**Carga de datos:**

```bash
uv run python scripts/init_postgres.py
```

El script exporta `data/curated/rama_historica.parquet` a CSV (~1.3 GB) y ejecuta
`COPY bronze.rama_horaria FROM '/tmp/bronze_rama.csv' WITH (FORMAT CSV, NULL '')`.

```
COPY 55350526
Time: ~30s
```

## 4. Capa Silver — `silver.rama_horaria_validada`

**Tabla:** 55,350,526 filas. Agrega columnas de control de calidad sobre los datos
bronze.

```sql
CREATE TABLE silver.rama_horaria_validada (
    fecha               DATE          NOT NULL,
    hora                SMALLINT      NOT NULL CHECK (hora BETWEEN 0 AND 23),
    estacion            TEXT          NOT NULL,
    contaminante        TEXT          NOT NULL,
    valor               REAL,

    flag_valido             BOOLEAN   NOT NULL,  -- TRUE si en rango fisico
    flag_fuera_rango        BOOLEAN   NOT NULL,  -- TRUE si excede el maximo esperado
    flag_hora24_corregida   BOOLEAN   NOT NULL   -- TRUE si HORA=24 se normalizo a 0
);
```

### Transformacion Bronze → Silver

[`scripts/transform_silver.sql`](../scripts/transform_silver.sql)

**Validaciones aplicadas:**

| Regla | Descripcion | Implementacion SQL |
|---|---|---|
| HORA=24 | Sentinel historico (medianoche del dia siguiente) | `CASE WHEN hora=24 THEN 0 ELSE hora END` + `fecha + INTERVAL '1 day'` |
| Valor negativo | `-99` (missing sentinel) y `-1` (posible outlier) | `CASE WHEN valor < 0 THEN NULL ELSE valor END` |
| Rango fisico | Limites por contaminante (CO ≤ 50 ppm, O3 ≤ 500 ppb, etc.) | `CASE contaminante WHEN 'CO' THEN 50 ...` |

**Ejemplo de fila transformada:**

```
Bronze: 1999-12-31 | 24 | TLA | O3 | 45.2
Silver: 2000-01-01 |  0 | TLA | O3 | 45.2 | true | false | true
         (fecha+1)      (hora→0)                    (ok)   (ok)   (corregida)
```

**Resultado:**

```
INSERT 0 55350526
Time: ~45s
```

## 5. Capa Gold — `gold.rama_mensual_bi`

**Tabla:** 64,858 filas (agregacion mensual). Tabla plana lista para BI con 24
columnas `dim_*` / `mt_*`.

**Catalogos de referencia:**

| Tabla | Filas | Contenido |
|---|---|---|
| `gold.cat_contaminantes` | 9 | Codigo, nombre, unidad (ppm/ppb/µg/m³) |
| `gold.cat_estaciones` | 54 | Codigo, nombre, alcaldia, `lat_lon` (formato Looker Geo) |

### Transformacion Silver → Gold

[`scripts/transform_gold.sql`](../scripts/transform_gold.sql)

**Agregaciones aplicadas:**

| Metrica | Funcion SQL | Descripcion |
|---|---|---|
| `mt_valor_mean` | `AVG(valor)::REAL` | Media mensual |
| `mt_valor_max` | `MAX(valor)::REAL` | Pico horario del mes |
| `mt_valor_min` | `MIN(valor)::REAL` | Minimo horario del mes |
| `mt_valor_std` | `STDDEV(valor)::REAL` | Desviacion estandar |
| `mt_valor_p50` | `PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY valor)` | Mediana |
| `mt_valor_p95` | `PERCENTILE_CONT(0.95) ...` | Percentil 95 |
| `mt_valor_p98` | `PERCENTILE_CONT(0.98) ...` | Percentil 98 |
| `mt_horas_validas` | `COUNT(*)` | Lecturas con dato en el mes |
| `mt_horas_esperadas` | `24 * dias_del_mes` | Maximo teorico |
| `mt_dias_con_dato` | `COUNT(DISTINCT fecha)` | Dias con al menos 1 lectura |
| `mt_pct_datos` | `horas_validas / horas_esperadas * 100` | % completitud |

**Dimensiones precalculadas:**

- `dim_fecha` — primer dia del mes (`DATE_TRUNC('month', fecha)`)
- `dim_anio`, `dim_mes`, `dim_nombre_mes`, `dim_trimestre`, `dim_estacion_anio`
- `dim_nombre_contaminante`, `dim_nombre_estacion`, `dim_alcaldia`, `dim_lat_lon`

Las dimensiones de texto (nombre del mes, estacion del anio) se generan con `CASE`
en lugar de unirse a tablas de lookup, eliminando JOINs en las consultas de BI.

```sql
CASE EXTRACT(MONTH FROM fecha)::INT
    WHEN 1  THEN 'Enero'   WHEN 2  THEN 'Febrero' ...
END AS dim_nombre_mes
```

**CTE para optimizacion del GROUP BY:**

```sql
WITH monthly AS (
    SELECT
        estacion, contaminante, fecha AS fecha_raw, valor,
        DATE_TRUNC('month', fecha) AS mes_start,
        EXTRACT(DAYS FROM (...))::INT AS dias_mes
    FROM silver.rama_horaria_validada
    WHERE flag_valido
)
INSERT INTO gold.rama_mensual_bi (...)
SELECT ... FROM monthly m
JOIN gold.cat_estaciones    e ON m.estacion     = e.estacion
JOIN gold.cat_contaminantes c ON m.contaminante = c.contaminante
GROUP BY m.mes_start, m.estacion, ..., e.nombre_estacion, ...
```

**Resultado:**

```
INSERT 0 64858
Time: ~12s
```

## 6. Indices

[`docker/postgres/init/06_indexes.sql`](../docker/postgres/init/06_indexes.sql)

Se crean DESPUES de la carga para no relentizarla.

```sql
-- Bronze: cubo principal de agregacion (fundamental para silver transform)
CREATE INDEX idx_bronze_fecha_est_cont
    ON bronze.rama_horaria (fecha, estacion, contaminante);

-- Silver: indice parcial que funciona como particion logica
CREATE INDEX idx_silver_valido_fecha_est_cont
    ON silver.rama_horaria_validada (fecha, estacion, contaminante)
    WHERE flag_valido;

-- Gold: cubo de tendencias (serie de tiempo por contaminante)
CREATE INDEX idx_gold_cont_fecha
    ON gold.rama_mensual_bi (dim_contaminante, dim_fecha);

-- Gold: cubo compuesto (filtro completo del dashboard)
CREATE INDEX idx_gold_full
    ON gold.rama_mensual_bi (dim_contaminante, dim_estacion, dim_fecha);

-- Gold: cubo de estacionalidad (mes x contaminante)
CREATE INDEX idx_gold_cont_mes
    ON gold.rama_mensual_bi (dim_contaminante, dim_mes);
```

### Plan de ejecucion (`EXPLAIN ANALYZE`)

Consulta tipica del dashboard: O3, 2015-2025, todas las estaciones.

```sql
EXPLAIN ANALYZE
SELECT dim_fecha, dim_estacion, dim_contaminante, mt_valor_mean
FROM gold.rama_mensual_bi
WHERE dim_contaminante = 'O3'
  AND dim_anio BETWEEN 2015 AND 2025
ORDER BY dim_fecha, dim_estacion;
```

```
 Sort  (cost=1954.37..1964.69 rows=4130) (actual time=3.7..3.9ms)
   Sort Key: dim_fecha, dim_estacion
   ->  Bitmap Heap Scan on rama_mensual_bi  (actual time=1.7..2.8ms rows=3990)
         Recheck Cond: (dim_contaminante = 'O3')
         Filter: ((dim_anio >= 2015) AND (dim_anio <= 2025))
         Heap Blocks: exact=1400
         ->  Bitmap Index Scan on idx_gold_cont_mes  (actual time=0.2ms rows=10140)
               Index Cond: (dim_contaminante = 'O3')
 Planning Time: 0.189 ms
 Execution Time: 3.994 ms
```

- **3.99 ms** para 3,990 filas sobre 64,858 totales
- El indice `idx_gold_cont_mes` filtra por contaminante en 0.2 ms
- PostgreSQL usa Bitmap Heap Scan (optimo para >1000 filas)

### Indice parcial en Silver

```sql
EXPLAIN ANALYZE
SELECT COUNT(*) FROM silver.rama_horaria_validada
WHERE flag_valido AND estacion = 'TLA' AND contaminante = 'O3';
```

```
 Aggregate (actual time=0.042..0.044ms)
   ->  Index Only Scan using idx_silver_valido_fecha_est_cont
       (actual time=0.022..0.031ms rows=25)
       Index Cond: ((estacion = 'TLA') AND (contaminante = 'O3'))
       Heap Fetches: 0
 Execution Time: 0.098 ms
```

El indice parcial (`WHERE flag_valido`) reduce el indice a solo las filas validas
(~41M de 55M), acelerando las consultas y la transformacion Gold.

## 7. API (FastAPI + asyncpg)

[`docker/api/api_server.py`](../docker/api/api_server.py)

**Endpoint:** `GET /api/data`

| Parametro | Tipo | Descripcion | Ejemplo |
|---|---|---|---|
| `cont` | string | Codigo de contaminante | `NOX` |
| `from` | int | Anio inicio | `2015` |
| `to` | int | Anio fin | `2025` |
| `stations` | string | Lista separada por comas (opcional) | `TLA,MER,UIZ` |

**Respuesta:**

```json
{
  "stations": [
    {
      "dim_fecha": "2015-01-01",
      "dim_anio": 2015,
      "dim_mes": 1,
      "dim_nombre_mes": "Enero",
      "dim_trimestre": 1,
      "dim_estacion_anio": "Invierno",
      "dim_estacion": "ACO",
      "dim_nombre_estacion": "Acolman",
      "dim_alcaldia": "Acolman",
      "dim_lat_lon": "19.635501,-98.912003",
      "dim_contaminante": "NOX",
      "dim_nombre_contaminante": "Oxidos de nitrogeno",
      "mt_valor_mean": 23.98,
      "mt_valor_max": 89.5,
      "mt_valor_p95": 67.3,
      "mt_valor_p98": 74.1,
      ...
      "mt_pct_datos": 95
    }
  ],
  "count": 3039,
  "params": { "cont": "NOX", "from": 2015, "to": 2025 }
}
```

**Ejemplos:**

```bash
# Todos los contaminantes y estaciones, 2015-2025
curl "http://localhost:8080/api/data?cont=O3&from=2015&to=2025"

# Solo 3 estaciones
curl "http://localhost:8080/api/data?cont=PM10&from=2000&to=2020&stations=TLA,MER,UIZ"
```

## 8. Dashboard — Modo Servidor

El dashboard (`data/exposure/rama_dashboard.html`) incluye un toggle en la barra
superior:

```
[📦 Archivo] [🗄️ Servidor]
```

**Modo Archivo (default):** datos embebidos en el HTML (2 MB). Funciona sin
conexion ni servidor. Comportamiento identico al original.

**Modo Servidor:** consulta la API en `http://localhost:8080`. Al hacer clic:

1. Verifica `GET /health` (timeout 5s)
2. Si OK → cambia a modo servidor (indicador verde)
3. Cada cambio de filtro → `GET /api/data?cont=...&from=...&to=...`
4. Las graficas y KPIs se actualizan con datos de PostgreSQL

Si el servidor no esta disponible, muestra un mensaje y permanece en modo Archivo.

## 9. Como usar (completo)

### Primer arranque

```bash
# 1. Clonar e instalar dependencias
uv sync

# 2. Iniciar servicios Docker
docker compose up -d

# 3. Bootstrap de datos (exporta parquet → PostgreSQL, ejecuta transforms)
uv run python scripts/init_postgres.py

# 4. Abrir dashboard
open data/exposure/rama_dashboard.html
# → Click en "Servidor" para usar PostgreSQL
```

### Reconstruir tras cambios en datos

```bash
# Si los datos curados cambiaron:
uv run python scripts/init_postgres.py   # re-ejecuta todo el pipeline

# Si solo cambiaste el dashboard:
uv run python scripts/build_dashboard.py # regenera el HTML
```

### Detener

```bash
docker compose down       # preserva volumen pgdata
docker compose down -v    # borra todo (requiere re-bootstrap)
```

## 10. Comparativa: SQL vs Python

| Aspecto | Python (Polars) | SQL (PostgreSQL) |
|---|---|---|
| **Bronze carga** | `pl.read_parquet()` (~2s) | `COPY FROM CSV` (~30s) |
| **Silver transform** | `df.with_columns(...)` (~3s) | `INSERT INTO ... SELECT` (~45s) |
| **Gold agregacion** | `df.group_by(...).agg(...)` (~2s) | `GROUP BY + PERCENTILE_CONT` (~12s) |
| **Total pipeline** | ~8s | ~90s |
| **Persistencia** | Parquet en disco | Tablas en PostgreSQL |
| **Consultas ad-hoc** | Python + Polars | SQL directo |
| **Concurrencia** | No | Si (multiples dashboards/usuarios) |
| **BI** | Exportar CSV | Conexion directa (Metabase, PowerBI, etc.) |
| **Mantenibilidad** | Codigo Python | DDL + DML estandar |

La velocidad de Python es superior para procesamiento batch, pero PostgreSQL ofrece:

- **Persistencia transaccional** — datos seguros con ACID
- **Consultas SQL ad-hoc** — sin necesidad de Python
- **Concurrencia** — multiples usuarios/dashboards simultaneos
- **Indices** — optimizacion automatica del planificador
- **Ecosistema BI** — compatible con cualquier herramienta que hable SQL
