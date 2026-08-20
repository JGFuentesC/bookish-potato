# SECURITY-AUDIT — E0-H1-T5 (ADR-001 + evidencia)

| Campo | Valor |
|---|---|
| Fecha | 2026-08-19 |
| Auditor | cyber-sec (skill `.agents/skills/cyber-sec/SKILL.md`) |
| Incremento | E0-H1-T5 — `docs/adr/ADR-001-stack-versions.md`, `docs/evidence/E0-H1/RESULTADOS.md`, `AGENTS.md` (regla dura de raíz del repo) |
| Tipo de cambio | Documental (Markdown) — sin código Go/Python/TS/React modificado |

## Matriz de severidad

| Severidad | Cantidad | Estado |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 0 | — |
| LOW | 0 | — |
| INFO | 2 | Sin acción requerida (detalle abajo) |

## Qué se chequeó

### 1. Secretos y hardcoding (SAST — barrido de patrones)

`git ls-files | xargs grep -lE 'sk_live|sk_test|ghp_|gho_|ghu_|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z\-_]{35}|sk-ant-|xox[baprs]-|BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY'`

- Resultado: **sin coincidencias** (exit 1). El incremento no introduce secretos ni credenciales. No hay `.env` versionado; se usa `.env.example` por política.

### 2. Dependencias (SCA) — por módulo, sobre el venv/lock del módulo

| Módulo | Comando | Resultado |
|---|---|---|
| `data-platform` | `uv audit` (en `data-platform/`) | 24 paquetes, sin vulnerabilidades conocidas |
| `ai-sidecar` | `uv audit` (en `ai-sidecar/`) | 31 paquetes, sin vulnerabilidades conocidas |
| `frontend` | `pnpm audit` (en `frontend/`) | Sin vulnerabilidades conocidas |

- Nota de proceso: en una corrida previa el comando se ejecutó encadenando `cd` entre módulos y `uv pip audit` (subcomando inexistente en uv 0.11.6). Se reejecutó correctamente por módulo con `workdir` y `uv audit`. Para evitar recurrencia se añadió a `AGENTS.md` la regla dura que prohíbe salir de la raíz del repositorio y exige auditorías con `workdir=<módulo>` sobre el venv/lock propio. (INFO)

### 3. Análisis estático (SAST) en código

- **N/A**: el incremento no modifica código ejecutable (solo Markdown). No hay superficie de inyección SQL, XSS ni comandos. Los componentes auditables (Go, Python, React) llegan en E1+.

### 4. Rutas de máquina y valores de máquina

- El ADR fija versiones verificadas de registros oficiales; no contiene rutas absolutas de máquina ni secretos. La única ruta absoluta es la de la raíz del repositorio en `AGENTS.md` (regla de proceso, no secreto). (INFO)

## Hallazgos

No hay hallazgos de severidad CRITICAL/HIGH/MEDIUM/LOW. Nada bloquea el commit.

## Veredicto

**Security Clearance otorgado.** Commit habilitado para E0-H1-T5.