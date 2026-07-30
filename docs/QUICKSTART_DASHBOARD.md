# Quick Start: Dashboard OLAP

## Setup

```bash
# 1. Levantar contenedores
docker compose up -d

# 2. Cargar datos OLTP (55M filas, ~70 min)
uv run python scripts/ingesta_batch.py

# 3. Construir cubo OLAP (~30-40 min)
uv run python scripts/construir_olap.py

# 4. Abrir dashboard
open http://localhost:8080
```

## Dashboard Features

### Filtros

- **Contaminante** (pills): CO, NO, NO2, NOX, O3, PM10, PM25, PMCO, SO2
- **Alcaldía** (dropdown): 16 CDMX + 12 municipios Edomex (limpiados de HTML entities)
- **Estación** (dropdown): 54 estaciones, dependiente de alcaldía
- **Período** (date range): ISO-8601
- **Granularidad**: Hora (requiere estación, límite 90 días), Día, Mes

### Tabs

| Tab | Contenido |
|-----|-----------|
| **Resumen** | Serie temporal (Plotly), min/max sombreados |
| **Mapa** | Leaflet, estaciones como círculos coloreados por índice (navy → accent) |
| **Rankings** | Top/bottom estaciones por índice normalizado, top contaminantes |
| **Datos** | % completitud por contaminante (explota 18-38% NULLs reales de sensor) |

### KPIs (siempre visibles)

- Índice Promedio (0-100)
- % Completitud
- Estaciones Activas
- Total Mediciones

## API Endpoints

Base URL: `http://localhost:8080/api`

### GET `/dimensiones/{tipo}`

Obtener filtros dinámicos:
```bash
curl http://localhost:8080/api/dimensiones/contaminantes
curl http://localhost:8080/api/dimensiones/alcaldias
curl http://localhost:8080/api/dimensiones/estaciones
curl http://localhost:8080/api/dimensiones/categorias
```

### GET `/kpis`

KPIs agregados filtrable:
```bash
curl 'http://localhost:8080/api/kpis?contaminante=PM25&fecha_inicio=2025-01-01&fecha_fin=2025-07-29'
```

Response:
```json
{
  "periodo": {"fecha_inicio": "2025-01-01", "fecha_fin": "2025-07-29"},
  "promedio_indice_normalizado": 42.3,
  "pct_completitud": 81.4,
  "estaciones_activas": 51,
  "contaminantes_monitoreados": 9,
  "total_mediciones": 3812400
}
```

### GET `/series-tiempo`

Serie temporal con granularidad:
```bash
# Día (default)
curl 'http://localhost:8080/api/series-tiempo?contaminante=PM25&granularidad=dia&fecha_inicio=2025-06-01&fecha_fin=2025-07-29'

# Mes
curl 'http://localhost:8080/api/series-tiempo?contaminante=PM25&granularidad=mes'

# Hora (requiere estación, máx 90 días)
curl 'http://localhost:8080/api/series-tiempo?contaminante=PM25&granularidad=hora&estacion=MER&fecha_inicio=2025-07-01&fecha_fin=2025-07-29'
```

### GET `/mapa-estaciones`

Última lectura por estación:
```bash
curl 'http://localhost:8080/api/mapa-estaciones?contaminante=O3&fecha=2025-07-28'
```

### GET `/ranking/estaciones`

Top/bottom estaciones:
```bash
# Top 10 (default)
curl 'http://localhost:8080/api/ranking/estaciones?contaminante=PM25&orden=desc'

# Bottom 10
curl 'http://localhost:8080/api/ranking/estaciones?contaminante=PM25&orden=asc&limit=10'
```

### GET `/ranking/contaminantes`

Top contaminantes (por estación o global):
```bash
# Global
curl 'http://localhost:8080/api/ranking/contaminantes'

# Por estación
curl 'http://localhost:8080/api/ranking/contaminantes?estacion=MER'

# Por alcaldía
curl 'http://localhost:8080/api/ranking/contaminantes?alcaldia_id=1'
```

### GET `/completitud`

% completitud agrupado:
```bash
# Por contaminante (default)
curl 'http://localhost:8080/api/completitud?agrupar_por=contaminante'

# Por estación
curl 'http://localhost:8080/api/completitud?agrupar_por=estacion'

# Por año
curl 'http://localhost:8080/api/completitud?agrupar_por=anio'
```

## Swagger Docs

Documentación interactiva de la API:
```
http://localhost:8080/docs
```

## Datos Sucios Limpiados

Original en `rama.estacion_periodo.alcaldia`:
- 31 variantes sucias (HTML entities: `&Aacute;`, typos, duplicados)
- 16 alcaldías CDMX
- 12 municipios Edomex

Después de limpieza en `rama_olap.dim_alcaldia`:
- 26 canónicas (nombres sin entidades HTML)
- Deduplicadas (ej. "Álvaro Obregón" = "Alvaro Obregon" = "&Aacute;lvaro Obreg&oacute;n")
- Clasificadas por entidad (CDMX vs. Estado de México)

## Índice Normalizado

Escala 0-100:
```
indice = 100 * (valor - valor_min) / (valor_max - valor_min)
```

Ventaja: agnóstico a unidades (ppm, ppb, µg/m³), comparables entre contaminantes.

Límite: no es IMECA oficial (O3 verificado; demás pendientes).

## NULLs Reales

Completitud por contaminante (% de mediciones con valor válido):
- CO: 78.5%
- NO: 73.4%
- NO2: 75.7%
- NOX: 74.2%
- O3: 81.4%
- PM10: 74.2%
- PM25: 67.5%
- PMCO: 61.7%
- SO2: 79.3%

**Son datos reales**: sensores con fallas, mantenimiento, interrupciones. Dashboard explota como KPI de confiabilidad de datos.

## Performance

- **Queries**: Lee de agregados (agg_medicion_diaria, agg_medicion_mensual), no del fact de 50M filas
- **Guardrail hora**: Limitado a 90 días + requiere estación seleccionada
- **Pool conexiones**: min=2, max=8 psycopg
- **Refresh**: Vistas materializadas refrescables manualmente

```bash
docker exec rama-postgres-oltp psql -U rama -d rama -c \
  "REFRESH MATERIALIZED VIEW rama_olap.agg_medicion_diaria; \
   REFRESH MATERIALIZED VIEW rama_olap.agg_medicion_mensual;"
```
