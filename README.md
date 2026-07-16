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
└── data/                # (ignorado por git)
    ├── raw/
    │   ├── zips/        # Archivos originales descargados
    │   └── files/       # XLS extraidos
    ├── curated/         # rama_historica.parquet
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

## Licencia

MIT. Los datos son propiedad del Gobierno de la Ciudad de Mexico (SEDEMA)
y se distribuyen como datos abiertos.
