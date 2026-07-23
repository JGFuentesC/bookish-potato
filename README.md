# RAMA — Datos historicos de calidad del aire (CDMX)

Pipeline de extraccion, curacion y auditoria de calidad para los datos de la
**Red Automatica de Monitoreo Atmosferico** de la Ciudad de Mexico.

Fuente: [aire.cdmx.gob.mx](https://www.aire.cdmx.gob.mx) — Datos abiertos SEDEMA.

## Datos

- **Periodo:** enero 1986 - presente
- **Contaminantes:** CO, NO, NO2, NOX, O3, PM10, PM2.5, PMCO, SO2
- **Estaciones:** 54 a lo largo de la historia (~13 en 1986, ~36 en 2026)
- **Resolucion:** horaria
- **Formato original:** `.xls` (archivos ZIP anuales)
- **Formato curado:** Parquet con compresion zstd (~43 MB, 55M filas)

## Estructura

```
.
├── download_rama.sh        # Descarga paralela de ZIPs anuales
├── curate.py               # Pipeline de curacion (XLS -> Parquet tidy)
├── audit.py                # Auditoria estadistica (SPA con Plotly)
├── ge_audit.py             # Great Expectations (validacion declarativa)
├── pyproject.toml          # Dependencias (uv)
├── uv.lock                 # Lockfile reproducible
├── compose.yml             # Docker Compose: postgres + api (FastAPI)
├── .env.example            # Template de variables de entorno
├── docker/
│   ├── api/
│   │   ├── Dockerfile      # Imagen Python 3.13-slim no-root
│   │   └── api_server.py   # FastAPI asyncpg (GET /api/data, /health)
│   └── postgres/init/      # Init SQL para arquitectura medallon
│       ├── 01_schemas.sql
│       ├── 02_tables_bronze.sql
│       ├── 03_tables_silver.sql
│       ├── 04_tables_gold.sql
│       ├── 05_load_catalogos.sql
│       └── 06_indexes.sql
├── scripts/
│   ├── scrape_stations.py       # Scraper de coordenadas SEDEMA
│   ├── generate_exposure.py     # Generador de tabla agregada mensual
│   ├── build_dashboard.py       # Generador del dashboard HTML
│   ├── dashboard_template.html  # Plantilla del dashboard
│   ├── init_postgres.py         # Bootstrap: Parquet → PostgreSQL
│   ├── transform_silver.sql     # Bronze → Silver (validaciones)
│   └── transform_gold.sql       # Silver → Gold (agregacion mensual)
└── data/                # (ignorado por git)
    ├── raw/
    │   ├── zips/        # Archivos originales descargados
    │   └── files/       # XLS extraidos
    ├── curated/         # rama_historica.parquet
    ├── exposure/        # Capa de BI
    │   ├── rama_mensual.csv         # Tabla maestra mensual (CSV)
    │   ├── rama_mensual.parquet     # Idem en Parquet
    │   ├── rama_dashboard.html      # Dashboard interactivo autoncontenido
    │   └── stations_catalog.json    # Catalogo de estaciones con lat/lon
    └── audit/           # Reportes HTML generados
```

## Uso

### 1. Descargar datos

```bash
bash download_rama.sh
```

### 2. Curar y consolidar

```bash
uv run python curate.py
```

Genera `data/curated/rama_historica.parquet` con esquema:

| Columna | Tipo | Descripcion |
|---|---|---|
| FECHA | date | Dia de la medicion |
| HORA | i8 (0-23) | Hora del dia |
| estacion | str | Codigo de 3 letras de la estacion |
| contaminante | str | CO, NO, NO2, NOX, O3, PM10, PM25, PMCO, SO2 |
| valor | f32 (nullable) | Concentracion medida |

### 3. Auditoria estadistica

```bash
uv run python audit.py
```

Genera `data/audit/calidad_rama.html` — SPA navegable con:
- Series de tiempo con cartas de control (±2σ, ±3σ)
- Campanas de Gauss (bell curves) con curvas normales teoricas
- Boxplots mensuales para detectar estacionalidad
- Pruebas de hipotesis: Shapiro-Wilk, Anderson-Darling, Mann-Kendall

### 4. Validacion con Great Expectations

```bash
uv run python ge_audit.py
```

Genera `data/audit/great_expectations/expectations_report.html` con 40
expectations sobre el dataset curado: tipos, rangos, nulos, valores unicos,
y limites fisicos por contaminante.

## Dependencias

- Python 3.13+
- [polars](https://pola.rs) — procesamiento de datos
- [plotly](https://plot.ly) — graficos interactivos
- [scipy](https://scipy.org) — pruebas estadisticas
- [Great Expectations](https://greatexpectations.io) — validacion de datos
- [pydantic](https://docs.pydantic.dev) — modelos y validacion

## Capa de exposicion (BI)

### 5. Generar tabla agregada mensual

```bash
uv run python scripts/generate_exposure.py
```

Lee `data/curated/rama_historica.parquet`, enriquece con coordenadas de estaciones
y agrega a nivel mensual por estacion y contaminante. Genera:

- `data/exposure/rama_mensual.parquet` (~1.1 MB, 76K filas) — 24 columnas con
  prefijos `dim_` (dimensiones) y `mt_` (metricas), optimizado para Looker Studio.
- `data/exposure/rama_mensual.csv` (~13 MB) — mismo esquema en CSV.

**Esquema:**

| Columna | Tipo | Descripcion |
|---|---|---|
| dim_fecha | date | Primer dia del mes |
| dim_anio | i16 | Año |
| dim_mes | i8 | 1–12 |
| dim_nombre_mes | str | Enero, Febrero... |
| dim_trimestre | i8 | 1–4 |
| dim_estacion_del_anio | str | Invierno, Primavera, Verano, Otoño |
| dim_estacion | str | Codigo de 3 letras |
| dim_nombre_estacion | str | Nombre completo |
| dim_alcaldia | str | Delegacion o municipio |
| dim_lat_lon | str | `"19.529,-99.205"` (formato Looker geo) |
| dim_contaminante | str | CO, NO, NO2... |
| dim_nombre_contaminante | str | Nombre completo |
| mt_valor_mean | f32 | Media mensual |
| mt_valor_max | f32 | Maximo mensual |
| mt_valor_min | f32 | Minimo mensual |
| mt_valor_std | f32 | Desviacion estandar |
| mt_valor_p50 | f32 | Mediana |
| mt_valor_p95 | f32 | Percentil 95 |
| mt_valor_p98 | f32 | Percentil 98 |
| mt_horas_validas | i32 | Lecturas con dato en el mes |
| mt_horas_esperadas | i32 | Total esperado (24 × dias del mes) |
| mt_dias_con_dato | i16 | Dias con al menos 1 lectura |
| mt_dias_esperados | i8 | Dias del mes |
| mt_pct_datos | f32 | % completitud (0–100) |

## Arquitectura medallon (PostgreSQL)

Ademas del pipeline Python, los datos se pueden cargar en PostgreSQL con
arquitectura medallon (Bronze → Silver → Gold) para consultas SQL directas,
concurrencia y conexion con herramientas BI.

### Docker Compose

```bash
docker compose up -d
```

Inicia dos servicios:
- `postgres` — pgvector/pgvector:pg16 en `:5433` (`rama`/`rama`/`rama`)
- `api` — FastAPI + asyncpg en `:8080`

Variables configurables via `.env` (ver `.env.example`).

### Bootstrap de datos

```bash
uv run python scripts/init_postgres.py
```

Exporta `rama_historica.parquet` a CSV, carga 55M filas en Bronze mediante
`COPY`, ejecuta las transformaciones SQL y crea indices. Resultado:

| Capa | Tabla | Filas | Descripcion |
|---|---|---|---|
| Bronze | `bronze.rama_horaria` | 55.3M | Datos horarios crudos, sin validaciones |
| Silver | `silver.rama_horaria_validada` | 55.3M | Con flags de calidad (rango fisico, hora24) |
| Gold | `gold.rama_mensual_bi` | 64.9K | Agregacion mensual, 24 columnas dim_*/mt_* |

### API REST

```bash
# O3, 2015-2025, todas las estaciones
curl "http://localhost:8080/api/data?cont=O3&from=2015&to=2025"

# PM10, 2000-2020, solo 3 estaciones
curl "http://localhost:8080/api/data?cont=PM10&from=2000&to=2020&stations=TLA,MER,UIZ"
```

Validacion de entrada: contaminante contra catalogo, `from <= to`, SQL injection
prevenido con queries parametrizadas (`$1`, `$2`, ...).

### Indices y rendimiento

7 indices B-tree compuestos + 1 indice parcial en Silver (`WHERE flag_valido`).
Consulta tipica del dashboard (O3, 2015-2025):

```
Execution Time: 3.994 ms  (3990 filas, 64.9K totales)
```

### 6. Dashboard interactivo

Abre `data/exposure/rama_dashboard.html` en el navegador (archivo autocontenido,
solo requiere internet para CDN de Plotly, Leaflet y tiles cartograficos).

**Funcionalidades:**

- **Filtros globales:** contaminante (pills), rango de años (slider), selector de
  estaciones con busqueda
- **KPIs dinamicos:** media, pico, estaciones activas, cobertura, variacion vs
  periodo equivalente anterior
- **5 pestañas:** Tendencias (serie mensual/anual), Mapa (Leaflet con puntos/calor),
  Estaciones (ranking + heatmap), Estacionalidad (mes×año + boxplots),
  Calidad de datos (cobertura)
- **Responsive:** adaptado a escritorio y movil

**Modo de datos dual:** El dashboard incluye un toggle en la barra superior
que permite alternar entre:
- **Archivo** (default) — datos embebidos en el HTML, sin dependencias externas
- **Servidor** — consulta la API PostgreSQL en `http://localhost:8080` via
  `fetch()` con AbortController (timeout 5s health, 8s datos)

Si el servidor no esta disponible, el dashboard permanece en modo Archivo.

**Regenerar** tras actualizar datos curados:

```bash
uv run python scripts/build_dashboard.py
```

### 7. Catalogo de estaciones

```bash
uv run python scripts/scrape_stations.py
```

Obtiene coordenadas (lat/lon) de las 54 estaciones RAMA desde las paginas de
detalle de SEDEMA y las guarda en `data/exposure/stations_catalog.json`.
Las 35 estaciones activas se obtienen por scraping; las 19 historicas tienen
coordenadas documentadas.

## Seguridad

- Las credenciales de base de datos se configuran via `.env` (gitignorado)
  con defaults seguros para desarrollo local. Ver `.env.example`.
- La API valida contaminantes contra un catalogo fijo (`CONT_VALIDOS`)
  y rechaza parametros invalidos con HTTP 400.
- SQL injection prevenido con queries parametrizadas (`$1`, `$2`, ...).
- El contenedor API ejecuta como usuario no-root (`app`, uid 1001).
- CORS restringido a `localhost:8080` y `file://`.
- Puerto PostgreSQL (5433) expuesto solo en localhost; en entornos
  compartidos, cambiarlo a `127.0.0.1:5433:5432` en compose.yml.
- Los scripts SQL de inicializacion crean 3 esquemas aislados
  (bronze/silver/gold) que separan logicamente datos crudos, validados
  y agregados.

## Licencia

MIT. Los datos son propiedad del Gobierno de la Ciudad de Mexico (SEDEMA)
y se distribuyen como datos abiertos.
