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
├── download_rama.sh     # Descarga paralela de ZIPs anuales
├── curate.py            # Pipeline de curacion (XLS -> Parquet tidy)
├── audit.py             # Auditoria estadistica (SPA con Plotly)
├── ge_audit.py          # Great Expectations (validacion declarativa)
├── pyproject.toml       # Dependencias (uv)
├── uv.lock              # Lockfile reproducible
├── scripts/             # Scripts de la capa de exposure y dashboard
│   ├── scrape_stations.py       # Scraper de coordenadas SEDEMA
│   ├── generate_exposure.py     # Generador de tabla agregada mensual
│   ├── build_dashboard.py       # Generador del dashboard HTML
│   └── dashboard_template.html  # Plantilla del dashboard
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

## Licencia

MIT. Los datos son propiedad del Gobierno de la Ciudad de Mexico (SEDEMA)
y se distribuyen como datos abiertos.
