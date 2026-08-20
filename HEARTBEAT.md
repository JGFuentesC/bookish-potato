# HEARTBEAT — GenBI Fútbol (bookish-potato)

Estado del desarrollo interactivo del PRD. Se lee antes de desarrollar y se actualiza antes de cada commit.

## Estado actual

- **Fase**: E0 — Fundaciones y entorno
- **Próximo incremento**: E1-H1 — esquema OLTP 3NF y migraciones

## Hecho

- E0-H1-T1 — árbol de directorios + `.gitignore` (commit `c5ae2e7`).
- E0-H1-T2 — skills de diseño en `.claude/skills/` (commit `a2c571b`).
- E0-H1-T3 — módulos inicializados: Go (`go.mod` + main mínimo, `go build` OK), Python 3.12 con `uv.lock` en data-platform y ai-sidecar, frontend Vite+React+TS+Tailwind+shadcn (`pnpm build` → `dist/`). SECURITY-AUDIT: clearance, sin hallazgos. Commit `feat: ...` de E0-H1-T3.
- E0-H1-T4 — Makefile raíz (`bootstrap`, `verify`, `lint`, `test`, `fmt`, `clean` reales; pipeline/serve/compose como stubs hasta E1/E2/E7; metas extras de AGENTS.md: `report`, `lineage`, `model`, `migrate-*`, `up/down/restart/logs/ps`). `make verify` en 0 con smoke tests en ambos módulos Python y `test` = `tsc -b` en frontend; `.oxlintrc.json` silencia `react/only-export-components` (shadcn). SECURITY-AUDIT: clearance, sin hallazgos (SCA: `uv audit` y `pnpm audit` limpios). Commit `feat: E0-H1-T4...`.
- E0-H1-T5 — ADR-001 `docs/adr/ADR-001-stack-versions.md` con la sección 10 del PRD cerrada a versiones exactas verificadas contra registros oficiales (PyPI, npm, Go proxy, Docker Hub, GitHub releases, fecha 2026-08-19); lockfiles (`uv.lock`, `pnpm-lock.yaml`, `go.mod`) como fuente de las ya instaladas. Verificación T5.1: sin "≥" ni "por definir" en el ADR. Notas: Recharts 3.10.1 (shadcn charts ya soporta v3), go-duckdb v1.5.5 alineado con DuckDB Python 1.5.5. SECURITY-AUDIT: clearance, sin hallazgos (secretos: limpio; SCA por módulo con `uv audit`/`pnpm audit` limpio). De paso: regla dura en AGENTS.md que prohíbe `cd`/salir de la raíz y exige auditorías con `workdir=<módulo>`.
- E0-H2 — Orquestación de contenedores: `infra/docker-compose.yml` (app, ai-sidecar, postgres pgvector/pg17; volúmenes `pgdata` + `lakehouse` bind host montado ro en app/sidecar; healthchecks + `depends_on: service_healthy`; env `${VAR:?}` desde direnv, sin `.env`). `Dockerfile.app` multi-stage Node→Go→distroless (imagen 15.3 MB < 80 MB, sirve SPA + `/healthz`, headers de seguridad). `Dockerfile.sidecar` python:3.12.14-slim + uv 0.11.6, usuario no-root `genbi`, `GET /health`. Servidor Go nuevo con SPA embebida y flag `-healthcheck`; FastAPI `genbi_ai.api.main`; build-system hatchling en pyproject. `.envrc` con `source_env_if_exists .envrc.local` (gitignored), `.env.example` plantilla, `README.md` con sección Ollama externo + atribución StatsBomb; Makefile `serve/up/down/restart/logs/ps` reales. Verificación: config válido, error claro sin vars, 3 healthy, persistencia Postgres+lakehouse tras `down && make serve`, `make verify` verde. Puerto app host 8081 (8080 ocupado). SECURITY-AUDIT: clearance, 2 LOW (root corregido, CSP diferido a E5/E6).
- E0-H3 — Verificación del modelo local en platypy + **ADR-002**: candidata `gemma4:latest` (Gemma 4 8B Q4_K_M) carga **entera en GPU** (3.25 GB de 8 GB, `ollama ps` 100% GPU), TTFT mediano 0.48 s (< 3 s), 63.2 tok/s, prompt catálogo (~40 entidades, 578 tok) sin truncar con `num_ctx=8192`. Respaldo `gemma4:e2b-it-q4_K_M` (5.1B) verificado: 1.64 GB, TTFT 0.42 s, 109.2 tok/s. Embeddings `embeddinggemma` (dim 768, 0.175 s/ítem) coexiste con el LLM (4.97/8 GB, sin carga secuencial). `scripts/bench_model.py` + `scripts/prompt_catalogo.txt`; evidencia en `docs/evidence/E0-H3/` (RESULTADOS + 2 JSON bench + SECURITY-AUDIT). Tags fijados en `.env.example` (`OLLAMA_LLM_MODEL`, `OLLAMA_EMBEDDINGS_MODEL`) y ADR-001 actualizado. Nota: platypy corre Ollama 0.30.10 (ADR-001 fija 0.32.14; registrado en ADR-002). `make verify` verde. SECURITY-AUDIT: clearance, 1 LOW aceptado (bench acepta `--host` arbitrario; herramienta local).

## Por hacer (orden canónico)

1. E0-H1-T1 — árbol de directorios + `.gitignore` ✅
2. E0-H1-T2 — copiar skills de diseño a `.claude/skills/` ✅
3. E0-H1-T3 — inicializar módulos ✅
4. E0-H1-T4 — Makefile raíz ✅
5. E0-H1-T5 — ADR-001 con versiones exactas del stack ✅
6. E0-H2 — orquestación de contenedores ✅
7. E0-H3 — verificación del modelo local en platypy (ADR-002) ✅
8. E1-H1 — esquema OLTP 3NF y migraciones
...

## Notas

- Skills: AGENTS.md las referencia en `.agents/skills/` (ya presentes y versionadas). El PRD §11 las ubica en `.claude/skills/`; se reconcilia en E0-H1-T2.
- Sin secretos ni rutas de máquina en código. Datos StatsBomb no se versionan.
