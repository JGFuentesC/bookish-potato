# E0-H1 — Evidencia de incrementos

## E0-H1-T1 — Árbol de directorios y .gitignore ✅ (commit c5ae2e7)

### Verificación

`find . -type d` (excluyendo `.git`, `.venv`, `.agents`) muestra todos los directorios de la sección 11. `.gitignore` verificado con `git check-ignore`: `lakehouse/`, `node_modules/`, `*.duckdb`, `data/` → todos ignorados. 33 carpetas con `.gitkeep`.

---

## E0-H1-T2 — Skills de diseño versionadas ✅ (commit a2c571b)

### Verificación

T2.1 — los tres `SKILL.md` existen bajo `.claude/skills/` (symlinks → `.agents/skills/`). T2.2 — `git ls-files .claude/skills | wc -l` = 3. `emil-kowalski` ↔ `emil-design-eng`.

---

## E0-H1-T3 — Inicialización de módulos ✅ (commit afe4084)

### T3.1 — Go

```
cd backend && go mod init github.com/genbi-futbol/backend
go build ./...   →  BUILD_OK
go vet ./...     →  VET_OK
```

- `backend/go.mod` con módulo `github.com/genbi-futbol/backend`.
- `backend/cmd/server/main.go` mínimo (placeholder, se reemplaza en E5-H1).

### T3.2 — Python (uv, 3.12)

```
cd data-platform && uv sync   →  genera data-platform/uv.lock
cd ai-sidecar   && uv sync   →  genera ai-sidecar/uv.lock
```

- `pyproject.toml` en ambos módulos con `requires-python = ">=3.12"`, deps del PRD §10.1/10.2 y grupos dev (pytest, ruff, mypy).
- `.python-version` = `3.12` en ambos; `uv sync` respeta la versión (venv usa `cpython-3.12.11`).

### T3.3 — Frontend (Vite + React + TS + Tailwind + shadcn/ui)

```
cd frontend && pnpm create vite@latest . --template react-ts
pnpm add tailwindcss @tailwindcss/vite
pnpm dlx shadcn@latest init -y -t vite -b base -p nova
pnpm build  →  dist/ generado (built in 402ms)
```

- Vite 8.2.1, React 19.2.8, TypeScript 6.0.3, Tailwind 4.3.3.
- Tailwind v4 vía plugin `@tailwindcss/vite` en `vite.config.ts`.
- shadcn/ui inicializado: `components.json`, `src/components/ui/button.tsx`, `src/lib/utils.ts`; alias `@/` → `./src` en tsconfig y vite.
- TS 6 depreca `baseUrl`; los `paths` se declaran sin `baseUrl` (relativos al tsconfig).

### Verificación T3

```
pnpm build → dist/assets/index-*.js (193 kB, gzip 60 kB) + index.html  ✓
git check-ignore data-platform/.venv frontend/dist → ignorados          ✓
```

---

## E0-H1-T4 — Makefile raíz ✅ (commit ad3569f)

### T4.1 — Metas requeridas

Metas del PRD: `bootstrap`, `verify`, `lint`, `test`, `fmt`, `data-pull`, `ingest`, `bronze`, `silver`, `gold`, `serve`, `eval`, `demo`, `clean`. Extras de AGENTS.md: `report`, `lineage`, `model`, `migrate-up`, `migrate-down`, `ingest-report`, `ingest-360`, `up`, `down`, `restart`, `logs`, `ps`, `help`.

```
for t in bootstrap verify lint test fmt clean data-pull ingest bronze silver gold serve eval demo report lineage model migrate-up migrate-down ingest-report ingest-360 up down restart logs ps help
do make -n "$t" || exit 1; done
→ OK: make -n en todas las metas (ninguna falla)
```

Pipeline, eval, serve y compose son stubs que fallan con mensaje claro y `exit 1` (se implementan en E0-H2/E1/E2/E3/E7). `verify` encadena lint+test de los cuatro módulos.

### T4.2 — make verify

```
make verify → EXIT=0
```

- backend: `go vet ./...` ✓ · `go test ./...` (no test files) ✓
- data-platform: `ruff check` ✓ · `pytest` 1 passed ✓
- ai-sidecar: `ruff check` ✓ · `pytest` 1 passed ✓
- frontend: `oxlint` ✓ (sin warnings) · `tsc -b` ✓

Notas:
- `pytest` sin archivos de test saldría con código 5; se agregó `tests/test_smoke.py` en data-platform y ai-sidecar para dejar `make verify` en 0.
- `frontend/package.json` gana script `test` = `tsc -b` (typecheck; pruebas reales llegan en E6).
- oxlint advertía `react(only-export-components)` por exportar `buttonVariants` desde `button.tsx` (patrón shadcn estándar); se desactiva esa regla en `frontend/.oxlintrc.json` para cumplir DoD-G (linter sin warnings). Exit code era 0 igualmente.
- `make fmt` aplica `go fmt`, `ruff format` (sin formateador de frontend configurado en E0).

---

## E0-H1-T5 — ADR-001 con versiones exactas del stack ⏳ (pendiente VoBo)

### Qué se probó

1. `docs/adr/ADR-001-stack-versions.md` creado con la sección 10 del PRD cerrada a versiones exactas verificadas contra registros oficiales (PyPI, npm, Go proxy, Docker Hub, GitHub releases) con fecha 2026-08-19.
2. Verificación de la subtarea T5.1: ninguna celda del ADR dice "≥" ni "por definir".

### Registro oficial por componente (fuentes consultadas)

| Componente | Versión fijada | Fuente |
|---|---|---|
| PostgreSQL | 17.11 | Docker Hub `library/postgres` |
| pgvector | 0.8.6 | GitHub `pgvector/pgvector` tags |
| Imagen Postgres+pgvector | `0.8.6-pg17` | Docker Hub `pgvector/pgvector` tags |
| golang-migrate | 4.19.1 | GitHub `golang-migrate/migrate` releases |
| Python 3.12 | 3.12.14 | Docker Hub `library/python` tags |
| uv | 0.11.6 | `uv --version` local |
| Ollama | 0.32.14 | GitHub `ollama/ollama` releases |
| Google ADK (Python) | 2.7.1 | PyPI `google-adk` |
| Recharts | 3.10.1 | npm `recharts` (soporte v3 confirmado en shadcn/ui PR #8486) |
| Go | 1.26.5 | `go.mod` / `go version` |
| Docker | 29.6.2 | `docker --version` |
| Docker Compose | v5.3.1 | `docker compose version` |

### Versiones verificadas desde lockfiles (`grep` sobre `uv.lock` / `pnpm-lock.yaml`)

- data-platform: duckdb 1.5.5, polars 1.43.2, pyarrow 25.0.1, psycopg 3.3.4, pydantic 2.13.4.
- ai-sidecar: fastapi 0.141.1, httpx 0.28.1, pydantic 2.13.4, uvicorn 0.52.4, sqlglot 30.17.0, pyyaml 6.0.3, duckdb 1.5.5.
- frontend: react 19.2.8, react-dom 19.2.8, typescript 6.0.3, vite 8.2.1, @vitejs/plugin-react 6.0.5, tailwindcss 4.3.3, @tailwindcss/vite 4.3.3, shadcn 4.18.0, @base-ui/react 1.7.0, oxlint 1.79.0, lucide-react 1.32.0.
- Go deps (Go proxy): chi v5.3.1, pgx v5.10.0, go-duckdb v1.5.5 (motor DuckDB 1.5.5, coherente con Python), koanf v2.3.6, testify v1.12.1, testcontainers-go v0.44.0, otel v1.45.0.

### Verificación de la subtarea T5.1

```
$ rg -n "≥|por definir" docs/adr/ADR-001-stack-versions.md
CLEAN: sin ≥ ni 'por definir'
```

Exit code: 0 (patrón no encontrado). Todas las celdas de "Versión fijada" contienen un valor exacto.

## Estado general

- [x] E0-H1-T1.1 — árbol de directorios creado y versionado
- [x] E0-H1-T1.2 — `.gitignore` cubre `data/`, `lakehouse/`, `node_modules/`, `.venv/`, `dist/`, `*.duckdb`
- [x] E0-H1-T2.1 — tres `SKILL.md` bajo `.claude/skills/`
- [x] E0-H1-T2.2 — `git ls-files .claude/skills | wc -l` = 3 > 0
- [x] E0-H1-T3.1 — `go build ./...` compila
- [x] E0-H1-T3.2 — `uv sync` genera `uv.lock` en data-platform y ai-sidecar (Python 3.12)
- [x] E0-H1-T3.3 — `pnpm build` produce `dist/`
- [x] E0-H1-T4.1 — `make -n <meta>` no falla en ninguna de las metas del PRD
- [x] E0-H1-T4.2 — `make verify` encadena lint+test de los cuatro módulos con código de salida 0
- [x] E0-H1-T5.1 — ADR-001 sin "≥" ni "por definir" (todas las celdas con versión exacta verificada)
- [x] `.gitignore` raíz ignora `backend/server` (binario)