# E2-H1 (Gold POC) — Runner de modelos + vista gold + consulta semántica

Incremento re-escopeado por decisión del usuario (velocidad absoluta, POC):
se cancela el pendiente E1-H4-T2.1 (`ingest-360`) y se prioriza una **vista gold
sencilla** para arrancar cuanto antes NLtoSQL / talk-to-your-data.

Alcance entregado:

1. **Runner de modelos** (E2-H1 core): contratos YAML (Pydantic `DataContract`),
   DAG topológico con detección de ciclos, ejecución SQL vía DuckDB, pruebas de
   calidad (`not_null`, `unique`, `accepted_values`, `row_count_min`,
   `expression`) con severidades error/warn, materialización a Parquet
   (`lakehouse/gold/{tabla}/data.parquet`) y reporte JSON por run.
2. **Vista gold sencilla** (6 tablas) leyendo directo de Postgres OLTP:
   `dim_competition_season`, `dim_match`, `dim_player`, `dim_team`,
   `fct_shot`, `fct_pass`.
3. **Capa semántica + consulta**: catálogo `ai-sidecar/semantic/catalog.yaml`
   (generado desde los contratos gold, fuente única) y endpoint
   `POST /api/v1/query` en el sidecar (solo SELECT, allow-list de tablas,
   LIMIT forzado, timeout).

## Comandos ejecutados y salidas

### `make gold`

```
layer gold: 6 modelos construidos
  dim_competition_season   filas=          80    0.0s  tests=5
  dim_match                filas=       3,961    0.0s  tests=4
  dim_player               filas=      11,794    0.0s  tests=4
  dim_team                 filas=         354    0.0s  tests=4
  fct_pass                 filas=   3,835,833   12.5s  tests=6
  fct_shot                 filas=     101,224    9.7s  tests=6
```

- Reporte de calidad `lakehouse/_reports/quality-*.json`: **0 pruebas fallidas**.
- Parquet en `lakehouse/gold/`: fct_pass 119 MB, fct_shot 3.1 MB, dims <1 MB.

### `make model MODEL=fct_shot` (modelo aislado)

```
layer gold: 1 modelos construidos
  fct_shot                 filas=     101,224    9.1s  tests=6
```

### `make lineage`

Genera `docs/lineage.md` (Mermaid) con los 6 modelos gold.

### Endpoint `POST http://localhost:8000/api/v1/query`

| Consulta | Resultado |
|---|---|
| `SELECT player_name, count(*) AS goles FROM fct_shot WHERE is_goal GROUP BY player_name ORDER BY goles DESC LIMIT 3` | Messi 508, Suárez 140, Neymar 89 — 7 ms |
| `SELECT season_name, count(*) AS partidos FROM dim_match GROUP BY season_name` | 3 partidos en 1986 … 31 en 2025 |
| `SELECT pass_height_name, count(*) FROM fct_pass GROUP BY 1 ORDER BY 2 DESC` | Ground Pass 2 486 788, High Pass 835 661 |
| `SELECT * FROM oltp.secret` | 400 `tabla no permitida: secret` |
| `DROP TABLE fct_shot` | 400 `solo se permiten consultas SELECT` |

### Guardas validadas por tests

- `validate_sql`: rechaza DDL/DML y múltiples sentencias; fuerza LIMIT cuando
  falta; respeta LIMIT existente; rechaza tablas fuera de la allow-list.
- Quality: `not_null`/`unique`/`accepted_values`/`row_count_min`/`expression`
  probados sobre DuckDB en memoria; severidad `warn` no aborta.

## Verificación

- `make verify` → exit 0 (go test, pytest data-platform 48 passed, pytest
  ai-sidecar 11 passed, tsc frontend).
- Runner: contratos inválidos abortan antes de ejecutar SQL; ciclo en DAG lanza
  error explícito; test de calidad `error` aborta la capa.
- Consulta gold end-to-end sobre el contenedor real (HTTP, 7 ms).

## Estado

- E2-H1: runner completo en su núcleo (T1 contratos, T2 motor, T3 calidad,
  T4 lineage básico) — pendiente del PRD: `--select` por capa con dependientes,
  bronze/silver (E2-H2/H3) y el esquema estrella completo (E2-H4).
- E1-H4-T2.1 (`ingest-360`): **cancelado por decisión** (POC); las tablas
  `three_sixty_*` quedan vacías y el resto del sistema funciona sin ellas.