# E0-H2 — Orquestación de contenedores · Resultados

Fecha: 2026-08-19 · Estado: **verificado, pendiente VoBo**

## Qué se hizo

- **T1 Compose** (`infra/docker-compose.yml`): servicios `app`, `ai-sidecar`, `postgres`
  (`pgvector/pgvector:0.8.6-pg17`); volúmenes `pgdata` (named) y `lakehouse` (bind del host
  `./lakehouse` vía `driver_opts type:none`, montado `ro` en app y sidecar); red `genbi_default`;
  healthcheck por servicio + `depends_on: condition: service_healthy`; env interpolada con
  `${VAR:?msg}` (direnv, sin `.env`). Puerto host del app: `8081` (8080 ocupado por proceso ajeno).
- **T2 Imágenes**:
  - `infra/Dockerfile.app` multi-stage Node 22 → Go 1.26.5 → distroless `static-debian12:nonroot`.
    Servidor Go (`backend/cmd/server/main.go`): `GET /healthz`, SPA embebida con fallback y flag
    `-healthcheck` para el HEALTHCHECK (distroless no trae shell). Embed con placeholder
    `backend/cmd/server/dist/.gitkeep` (negación en `.gitignore`).
  - `infra/Dockerfile.sidecar` sobre `python:3.12.14-slim` con uv 0.11.6 (copiado a
    `/usr/local/bin/uv`): `uv sync --frozen --no-dev` + uvicorn. App FastAPI
    `ai-sidecar/src/genbi_ai/api/main.py` con `GET /health`. Build-system hatchling añadido al
    pyproject (paquete instalable) y `__init__.py` en los paquetes.
- **T3 Configuración**: `.envrc` con vars del PRD + `source_env_if_exists .envrc.local` (gitignored);
  `.env.example` como plantilla de documentación (Compose no lee `.env`); `.envrc.local` con
  password dev y `OLLAMA_BASE_URL` de platypy; `README.md` raíz con sección "Ollama externo" y
  atribución StatsBomb; Makefile con `serve/up/down/restart/logs/ps` reales.

## Verificación ejecutable (PRD T1.1–T3.2, criterios y DoD)

| Tarea | Verificación | Resultado |
|---|---|---|
| T1.1 | `docker compose config` válido | OK (bind resuelto a `…/lakehouse`, `read_only: true`) |
| T1.2 | `docker inspect genbi-app-1` / `genbi-ai-sidecar-1` → `/lakehouse RW=false`; `docker run -v genbi_lakehouse:/lakehouse:ro alpine:3 touch /lakehouse/probe` | OK: `Read-only file system`, exit 1 |
| T1.3 | `docker compose ps` | 3 contenedores `healthy` |
| T2.1 | imagen `genbi-app:latest` tamaño | **15.3 MB** (< 80 MB) |
| T2.1 | `GET /healthz` y `GET /` | 200 `{"status":"ok"}`; 200 `text/html` (SPA) |
| T2.2 | `GET http://localhost:8000/health` | 200 `{"status":"ok"}` |
| T3.1 | `docker compose config` sin vars (sin direnv) | error claro: `required variable POSTGRES_USER is missing a value…` |
| T3.2 | `README.md` indica Ollama externo | OK |
| Criterio arranque | `make serve` | 3 contenedores healthy |
| Criterio persistencia | tabla `persistence_probe` en Postgres + archivo en lakehouse, `compose down && make serve` | ambos presentes tras reinicio (tabla `42`, archivo visible vía mount ro) |
| DoD-G | `make verify` | OK (go test, ruff, pytest 4 tests, tsc -b) |

Comandos de prueba adicionales: `make -n serve|up|down|restart|logs|ps` OK.

## Notas

- El healthcheck del app usa `["CMD", "/server", "-healthcheck"]` (exec form) porque distroless no
  incluye shell.
- `docker run alpine` se usó para las pruebas del mount ro porque app/sidecar no traen shell.
- Aviso de deprecación de Starlette (`httpx2`) en el test del sidecar; no bloquea, se revisa en E3.