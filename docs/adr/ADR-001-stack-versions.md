# ADR-001 — Versiones exactas del stack

| Campo | Valor |
|---|---|
| Estado | Aprobado |
| Fecha | 2026-08-19 |
| Decisión | Fijar las versiones exactas de la sección 10 del PRD, verificadas contra el registro oficial de cada componente |
| Alcance | E0-H1-T5 (E0-H1) |

## Contexto

El PRD §10 fija versiones mínimas (rangos abiertos con "mayor o igual") para el stack. Ninguna versión puede asumirse: trabajar con rangos abiertos hace que dos máquinas resuelvan dependencias distintas y que el desarrollo avance sobre supuestos divergentes. Este ADR cierra cada componente a una versión exacta verificada contra su registro oficial (PyPI, npm, Go proxy, Docker Hub, GitHub releases) al 2026-08-19.

Las versiones marcadas con `(lock)` están ya resueltas y congeladas en un archivo de bloqueo versionado del repositorio (`uv.lock` / `pnpm-lock.yaml`); las demás se fijan aquí como destino y se verificarán al instalarlas en sus historias correspondientes.

## Opciones consideradas

- **No fijar versiones (dejar rangos abiertos)** — rechazada: viola RNF-16 (reproducibilidad) y la política de E0-H1.
- **Fijar por archivo de bloqueo** — adoptada para dependencias de Python y frontend ya instaladas (`uv.lock`, `pnpm-lock.yaml`), que son la fuente de verdad definitiva de la resolución.
- **Fijar versiones máximas conocidas (verificadas hoy)** — adoptada para componentes que aún no se instalan (Go deps, frontend analítico, imágenes Docker, Ollama), con registro de la fecha de verificación.

## Decisión

### 10.1 Datos

| Componente | Elección | Versión fijada | Registro verificado |
|---|---|---|---|
| Base OLTP | PostgreSQL | 17.11 | Docker Hub `library/postgres` tag `17.11` |
| Extensión vectorial | pgvector | 0.8.6 | GitHub `pgvector/pgvector` tag `v0.8.6` |
| Imagen Postgres+pgvector | `pgvector/pgvector` | `0.8.6-pg17` | Docker Hub `pgvector/pgvector` tag `0.8.6-pg17` |
| Migraciones | golang-migrate | 4.19.1 | GitHub `golang-migrate/migrate` release `v4.19.1` |
| Motor analítico | DuckDB | 1.5.5 `(lock)` | PyPI `duckdb` (resuelto en `uv.lock` de data-platform y ai-sidecar) |
| Formato lakehouse | Apache Parquet | Sin versión (formato de archivo) | — |
| Ingesta / ELT | Python | 3.12.14 | Docker Hub `library/python` tag `3.12.14-slim` |
| Gestor de paquetes | uv | 0.11.6 | Herramienta local verificada (`uv --version`) |
| Validación | Pydantic | 2.13.4 `(lock)` | `uv.lock` de ambos módulos Python |
| Manipulación | Polars | 1.43.2 `(lock)` | `uv.lock` data-platform |
| Manipulación | PyArrow | 25.0.1 `(lock)` | `uv.lock` data-platform |
| Driver Postgres | psycopg | 3.3.4 `(lock)` | `uv.lock` data-platform |
| Orquestación | GNU Make | Sin versión (herramienta del sistema) | — |

### 10.2 IA

| Componente | Elección | Versión fijada | Registro verificado |
|---|---|---|---|
| Servidor de modelos | Ollama | 0.32.14 | GitHub `ollama/ollama` release `v0.32.14` |
| LLM (Gemma Q4 ≤ 8 GB VRAM) | `gemma4:latest` (8B Q4_K_M) | ADR-002 | medido en platypy (3.25 GB VRAM, TTFT med. 0.48 s) |
| Embeddings | `embeddinggemma` (dim 768) | ADR-002 | medido en platypy (0.175 s/ítem, coexiste con LLM) |
| Framework de agente | Google ADK (Python) | 2.7.1 | PyPI `google-adk` |
| API del sidecar | FastAPI | 0.141.1 `(lock)` | `uv.lock` ai-sidecar |
| Contratos | Pydantic v2 | 2.13.4 `(lock)` | `uv.lock` ai-sidecar |
| Cliente HTTP | httpx | 0.28.1 `(lock)` | `uv.lock` ai-sidecar |
| Servidor ASGI | uvicorn | 0.52.4 `(lock)` | `uv.lock` ai-sidecar |
| SQL transpilador/parser | sqlglot | 30.17.0 `(lock)` | `uv.lock` ai-sidecar |
| YAML | pyyaml | 6.0.3 `(lock)` | `uv.lock` ai-sidecar |

### 10.3 Backend (Go)

| Componente | Elección | Versión fijada | Registro verificado |
|---|---|---|---|
| Lenguaje | Go | 1.26.5 | `go.mod` (`go 1.26.5`) y `go version` |
| Router | chi | v5.3.1 | Go proxy `github.com/go-chi/chi/v5` |
| Driver Postgres | pgx | v5.10.0 | Go proxy `github.com/jackc/pgx/v5` |
| DuckDB | marcboeker/go-duckdb | v1.5.5 | Go proxy `github.com/marcboeker/go-duckdb` (motor DuckDB 1.5.5, coherente con Python) |
| Configuración | koanf | v2.3.6 | Go proxy `github.com/knadh/koanf/v2` |
| Logs | `log/slog` (stdlib) | Sin versión (stdlib de Go) | — |
| Trazas | OpenTelemetry Go SDK | v1.45.0 | Go proxy `go.opentelemetry.io/otel` |
| Pruebas | testify | v1.12.1 | Go proxy `github.com/stretchr/testify` |
| Pruebas de integración | testcontainers-go | v0.44.0 | Go proxy `github.com/testcontainers/testcontainers-go` |

### 10.4 Frontend

| Componente | Elección | Versión fijada | Registro verificado |
|---|---|---|---|
| Framework | React | 19.2.8 `(lock)` | `pnpm-lock.yaml` |
| Renderizado | react-dom | 19.2.8 `(lock)` | `pnpm-lock.yaml` |
| Lenguaje | TypeScript | 6.0.3 `(lock)` | `pnpm-lock.yaml` (`strict: true`) |
| Empaquetador | Vite | 8.2.1 `(lock)` | `pnpm-lock.yaml` |
| Plugin React | @vitejs/plugin-react | 6.0.5 `(lock)` | `pnpm-lock.yaml` |
| Estilos | Tailwind CSS | 4.3.3 `(lock)` | `pnpm-lock.yaml` |
| Plugin Tailwind Vite | @tailwindcss/vite | 4.3.3 `(lock)` | `pnpm-lock.yaml` |
| Componentes | shadcn/ui | 4.18.0 `(lock)` | `pnpm-lock.yaml` (CLI `shadcn`) |
| Primitivas | @base-ui/react | 1.7.0 `(lock)` | `pnpm-lock.yaml` |
| Datos remotos | TanStack Query | 5.101.4 | npm `@tanstack/react-query` |
| Gráficas | Recharts | 3.10.1 | npm `recharts` (shadcn/ui charts usa Recharts v3) |
| Estado de UI | Zustand | 5.0.15 | npm `zustand` |
| Formularios | react-hook-form | 7.85.0 | npm `react-hook-form` |
| Validación | zod | 4.4.3 | npm `zod` |
| Pruebas | Vitest | 4.1.11 | npm `vitest` |
| Pruebas | @testing-library/react | 16.3.2 | npm `@testing-library/react` |
| E2E | Playwright | 1.62.1 | npm `@playwright/test` |
| Linter | oxlint | 1.79.0 `(lock)` | `pnpm-lock.yaml` |
| Iconos | lucide-react | 1.32.0 `(lock)` | `pnpm-lock.yaml` |
| Mockups | Google Stitch | Sin versión (herramienta externa de diseño) | — |

### 10.6 Infraestructura

| Componente | Elección | Versión fijada | Registro verificado |
|---|---|---|---|
| Contenedores | Docker | 29.6.2 | `docker --version` (mínimo exigido por RNF-15: Docker 24 o superior) |
| Compose | Docker Compose | v5.3.1 | `docker compose version` |
| Imagen `app` | Node → Go → distroless | Sin versión propia (multi-stage, E0-H2) | — |
| Imagen `ai-sidecar` | Python 3.12 slim con uv | `python:3.12.14-slim` | Docker Hub `library/python` tag `3.12.14-slim` |
| Imagen `postgres` | pgvector | `pgvector/pgvector:0.8.6-pg17` | Docker Hub tag `0.8.6-pg17` |
| Ollama | Externo en platypy | servidor 0.32.14 | GitHub release `v0.32.14` |
| CI | GitHub Actions | Ubuntu 24.04 (runner `ubuntu-24.04`) | Documentación de GitHub Actions |

## Consecuencias

- **Positivas**: reproducibilidad (RNF-16) sin asumir versiones; los lockfiles versionados (`uv.lock`, `pnpm-lock.yaml`) y el `go.mod` son la prueba de resolución; cualquier actualización de versión exige un nuevo ADR/commit con evidencia.
- **Neutras**: el LLM y los embeddings se decidieron en ADR-002 (E0-H3) mediante medición sobre VRAM real de platypy: LLM `gemma4:latest`, embeddings `embeddinggemma`.
- **Negativas / riesgos**: Recharts 3.10.1 exige componentes shadcn/ui charts actualizados a la versión con soporte Recharts v3 (PR #8486); go-duckdb debe mantenerse alineado con la versión de DuckDB del lado Python (ambos 1.5.5). Docker local 29.6.2 supera el mínimo RNF-15 (24 o superior), por lo que el compose no debe usar sintaxis exclusiva de versiones posteriores.

## Verificación

- Cada celda de "Versión fijada" contiene un valor exacto y no hay rangos abiertos ni valores pendientes de decidir en el cuerpo del ADR.
- Las versiones `(lock)` se confirman con `grep` sobre `uv.lock` / `pnpm-lock.yaml`.
- Las versiones de destino se confirman contra el registro indicado en la columna "Registro verificado" (fecha de verificación 2026-08-19).