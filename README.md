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

Puertos publicados: app `http://localhost:8081`, sidecar `http://localhost:8000/health`, Postgres `localhost:5432`.

## Ollama externo

Ollama corre **fuera** de este stack en una máquina remota (platypy) y debe ser alcanzable por red. La URL se
configura en `OLLAMA_BASE_URL` (`.envrc.local`). El sidecar la usa para el agente; ningún contenedor del stack
levanta su propio modelo.

## Datos

Datos de muestra de [StatsBomb](https://github.com/statsbomb/open-data) (licencia no comercial),
cortesía de StatsBomb y Hudl. Los datos crudos no se versionan: se bajan con `make data-pull` a `data/`.

## Más

PRD completo en `docs/PRD.md`; decisiones de arquitectura en `docs/adr/`; estado del desarrollo en `HEARTBEAT.md`.