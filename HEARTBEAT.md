# HEARTBEAT — GenBI Fútbol (bookish-potato)

Estado del desarrollo interactivo del PRD. Se lee antes de desarrollar y se actualiza antes de cada commit.

## Estado actual

- **Fase**: E0 — Fundaciones y entorno
- **Próximo incremento**: E0-H1-T3 (VoBo pendiente) → E0-H1-T4 Makefile raíz

## Hecho

- E0-H1-T1 — árbol de directorios + `.gitignore` (commit `c5ae2e7`).
- E0-H1-T2 — skills de diseño en `.claude/skills/` (commit `a2c571b`).
- E0-H1-T3 — módulos inicializados: Go (`go.mod` + main mínimo, `go build` OK), Python 3.12 con `uv.lock` en data-platform y ai-sidecar, frontend Vite+React+TS+Tailwind+shadcn (`pnpm build` → `dist/`). SECURITY-AUDIT: clearance, sin hallazgos. Commit `feat: ...` de E0-H1-T3.

## Por hacer (orden canónico)

1. E0-H1-T1 — árbol de directorios + `.gitignore` ✅ (verificación: estructura coincide con sección 11)
2. E0-H1-T2 — copiar skills de diseño a `.claude/skills/` (verificar ubicación vs `.agents/skills/`)
3. E0-H1-T3 — inicializar módulos (Go, uv en data-platform y ai-sidecar, frontend Vite)
4. E0-H1-T4 — Makefile raíz (`bootstrap`, `verify`, `lint`, `test`, ...)
5. E0-H1-T5 — ADR-001 con versiones exactas del stack
6. E0-H2 — orquestación de contenedores
7. E0-H3 — verificación del modelo local en platypy (ADR-002)
8. E1-H1 — esquema OLTP 3NF y migraciones
...

## Notas

- Skills: AGENTS.md las referencia en `.agents/skills/` (ya presentes y versionadas). El PRD §11 las ubica en `.claude/skills/`; se reconcilia en E0-H1-T2.
- Sin secretos ni rutas de máquina en código. Datos StatsBomb no se versionan.
