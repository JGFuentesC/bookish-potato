# E0-H1 — Evidencia de incrementos

## E0-H1-T1 — Árbol de directorios y .gitignore ✅ (commit c5ae2e7)

### Verificación

`find . -type d` (excluyendo `.git`, `.venv`, `.agents`) muestra todos los directorios de la sección 11. `.gitignore` verificado con `git check-ignore`: `lakehouse/`, `node_modules/`, `*.duckdb`, `data/` → todos ignorados. 33 carpetas con `.gitkeep`.

---

## E0-H1-T2 — Skills de diseño versionadas ✅ (commit a2c571b)

### Verificación

T2.1 — los tres `SKILL.md` existen bajo `.claude/skills/` (symlinks → `.agents/skills/`). T2.2 — `git ls-files .claude/skills | wc -l` = 3. `emil-kowalski` ↔ `emil-design-eng`.

---

## E0-H1-T3 — Inicialización de módulos ⏳ (pendiente VoBo)

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

## Estado general

- [x] E0-H1-T1.1 — árbol de directorios creado y versionado
- [x] E0-H1-T1.2 — `.gitignore` cubre `data/`, `lakehouse/`, `node_modules/`, `.venv/`, `dist/`, `*.duckdb`
- [x] E0-H1-T2.1 — tres `SKILL.md` bajo `.claude/skills/`
- [x] E0-H1-T2.2 — `git ls-files .claude/skills | wc -l` = 3 > 0
- [x] E0-H1-T3.1 — `go build ./...` compila
- [x] E0-H1-T3.2 — `uv sync` genera `uv.lock` en data-platform y ai-sidecar (Python 3.12)
- [x] E0-H1-T3.3 — `pnpm build` produce `dist/`
- [x] `.gitignore` raíz ignora `backend/server` (binario)