# GenBI Fútbol

Asistente de inteligencia de negocio para análisis de fútbol: pregunta en lenguaje natural sobre datos de
partidos y obtén tablas y visualizaciones a partir de un lakehouse en Parquet con capa semántica y LLM local.

## Módulos

- `backend/` — API Go hexagonal (domain → application → adapter), sirve la SPA embebida.
- `data-platform/` — ingesta y lakehouse bronze/silver/gold (Python, contratos Pydantic).
- `ai-sidecar/` — FastAPI: agente ADK, capa semántica YAML y compilador NL→SQL.
- `frontend/` — React 19 + Vite + Tailwind + shadcn/ui + TanStack Query.

## Requisitos

- Docker (24+) y Docker Compose.
- `direnv` para las variables de entorno (copiar overrides locales a `.envrc.local`, gitignored).
- Ollama **externo** en una máquina remota (ver abajo).

## Arranque

```sh
direnv allow .
make serve     # construye y levanta app, ai-sidecar y postgres (espera healthchecks)
make ps        # estado de los contenedores
make logs      # logs (make logs SERVICE=app)
make down      # detiene el stack
```

Puertos publicados: app `http://localhost:8081`, sidecar `http://localhost:8000/health`, Postgres `localhost:5433` (5432 suele estar ocupado por otros Postgres locales).

## Ollama externo

Ollama corre **fuera** de este stack en una máquina remota (platypy) y debe ser alcanzable por red. La URL se
configura en `OLLAMA_BASE_URL` (`.envrc.local`). El sidecar la usa para el agente; ningún contenedor del stack
levanta su propio modelo. Modelos fijados en ADR-002 (E0-H3): LLM `gemma4:latest` y embeddings `embeddinggemma`
(variables `OLLAMA_LLM_MODEL` y `OLLAMA_EMBEDDINGS_MODEL`, ver `.env.example`).

## Datos

Datos de muestra de [StatsBomb](https://github.com/statsbomb/open-data) (licencia no comercial),
cortesía de StatsBomb y Hudl. Los datos crudos no se versionan: se bajan con `make data-pull` a `data/`.

## Lakehouse y consulta (gold)

El pipeline materializa una capa gold sencilla (dims + hechos) desde Postgres a Parquet con el runner
propio (contratos YAML, DAG y pruebas de calidad):

```sh
make gold                       # construye las 6 tablas gold (dims + fct_shot + fct_pass)
make model MODEL=fct_shot       # reconstruye un solo modelo
make lineage                    # diagrama Mermaid del DAG en docs/lineage.md
```

La capa gold se consulta por la capa semántica del sidecar (allow-list de tablas, solo SELECT, LIMIT
forzado) en `POST http://localhost:8000/api/v1/query`:

```sh
curl -s -X POST http://localhost:8000/api/v1/query -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT player_name, count(*) AS goles FROM fct_shot WHERE is_goal GROUP BY player_name ORDER BY goles DESC LIMIT 3"}'
```

El catálogo semántico (`ai-sidecar/semantic/catalog.yaml`) se regenera desde los contratos gold con
`uv run python scripts/gen_catalog.py` (fuente única de verdad).

## Más

PRD completo en `docs/PRD.md`; decisiones de arquitectura en `docs/adr/`; estado del desarrollo en `HEARTBEAT.md`.