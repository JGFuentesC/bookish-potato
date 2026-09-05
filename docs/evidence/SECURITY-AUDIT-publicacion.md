# SECURITY-AUDIT — Preparación para publicación

Auditoría transversal (secretos + historial + remoto + dependencias) antes de
hacer público el repositorio. Revisión solicitada por el usuario: `.envrc`,
historial completo, remote de `talk-to-your-data`.

Fecha: 2026-09-02 · Rama auditada: `talk-to-your-data` (+ remoto `origin`).

## Resumen

- Total hallazgos: 6 activos + 1 crítico/pendiente
- Critical: 0 · High: 1 (secreto en historial/remoto) · Medium: 1 · Low: 4
- **1 High**: password local de Postgres (valor redactado, antes `<password-dev>`) estaba en 2 evidencias y ya
  estaba **pusheada a GitHub** (`origin/talk-to-your-data`) → redactada en HEAD,
  **historial purgado localmente**, pendiente **force-push** para limpiar el remoto.

## Matriz de hallazgos

| # | Sev | Hallazgo | Estado |
|---|-----|----------|--------|
| 1 | HIGH | `PGPASSWORD=******` (password local de la BD de dev, valor redactado) estaba en `docs/evidence/{E1-H3,E1-H4}/RESULTADOS.md`, presente en HEAD **y en el remoto** (commit `a1b6b61` en `origin/talk-to-your-data`) | Redactado en HEAD + historial purgado (filter-repo). **Pendiente force-push** |
| 2 | MEDIUM | `.envrc` trackeado en git (no ignorado). Sin secretos (solo defaults + `source_env_if_exists .envrc.local`), pero no debe publicarse | Corregido: eliminado del índice, `.envrc` añadido a `.gitignore`, plantilla `.envrc.example` versionada; README actualizado |
| 3 | LOW | Ruta absoluta de máquina `REPO_ROOT` en `AGENTS.md` | Corregido: generalizada a `<repo-root>` |
| 4 | LOW | Hostname interno "platypy" referenciado en PRD/README/ADR/HEARTBEAT/agent.py (sin IP ni credenciales; la IP real `<ip-interna>` NO está versionada) | Aceptado: alias interno sin valor sensible; el PRD lo usa como nombre del host Ollama externo |
| 5 | LOW | SCA frontend: 6 vulns (4 high, 2 moderate) en deps **dev-only** (CLI `shadcn` → `@modelcontextprotocol/sdk` → `express`/`ajv`/`fast-uri`/`qs`) | Aceptado: build-time/dev-only, no llegan al bundle de producción; re-auditar al publicar. SCA de data-platform (26) y ai-sidecar (31): limpios |
| 6 | LOW | Defaults `localhost:11434` en `.env.example`/`.envrc.example` | Aceptado: placeholder no sensible |

## Detalle

### [HIGH] #1 — Credencial local en historial y remoto
**Archivos:** `docs/evidence/E1-H3/RESULTADOS.md:19`, `docs/evidence/E1-H4/RESULTADOS.md:18`
**CWE:** CWE-798

**Descripción:** El password local de Postgres Docker (valor redactado) quedó
registrado en la transcripción de comandos de dos evidencias. Aunque es una
credencial de desarrollo (docker-local, sin valor en prod), es un secreto y el
repo estaba preparándose para publicarse. Además **ya se encontraba en el
remoto** `origin/talk-to-your-data` (commit `a1b6b61`, anterior al push de las
2 últimas entregas).

**Remediación aplicada (local):**
1. Redactado a `******` en ambos `RESULTADOS.md` (commit `5af61d9`).
2. Historial reescrito con `git-filter-repo --replace-text` (mapeo
   del valor del password → `******`), limitado a `talk-to-your-data` (única
   rama que contiene los commits afectados; `main` y las ramas `feature/*`,`l0*` NO).
3. Verificación: `git log` sobre la rama con el patrón del password → 0
   coincidencias; `git grep` sobre todos los commits de la rama → limpio.

**Pendiente (requiere aprobación del usuario):**
```sh
git push --force-with-lease origin talk-to-your-data
```
Reemplaza en GitHub la ref `origin/talk-to-your-data` (actualmente en `a1b6b61`
con el secreto) por la historia reescrita. Tras el push, actualizar el ref local
(`git fetch -p origin`) y opcionalmente `git gc --prune=now` para descartar los
objetos viejos locales. NOTA: si alguien ya clonó con el commit viejo, el secreto
siguió expuesto para él; con un repo privado el riesgo es bajo.

**Controles compensatorios:** credencial de desarrollo local efímera (valor
redactado), no usada en producción ni en CI.

### [MEDIUM] #2 — `.envrc` versionado
`git ls-files` incluía `.envrc`. Su contenido era seguro (defaults vacíos +
`source_env_if_exists .envrc.local`), y `.envrc.local` (que SÍ contiene
`POSTGRES_PASSWORD` y `OLLAMA_BASE_URL` con IP de platypy) ya estaba ignorado.
Aun así, para publicación el `.envrc` se saca del repo.

**Remediación:** `git rm --cached .envrc`; `.gitignore` += `.envrc`;
`.envrc.example` versionado como plantilla; README documenta
`cp .envrc.example .envrc` + overrides en `.envrc.local`.

### [LOW] #5 — SCA frontend (dev-only)
`pnpm audit` → `fast-uri@3.1.5` y `qs@6.15.3` vía `shadcn@4.18.0` →
`@modelcontextprotocol/sdk@1.30.0` → (`express@5.2.1`/`ajv@8.20.0`). El CLI
`shadcn` solo se ejecuta en desarrollo (scaffolding de componentes); nada de ese
árbol entra en el `dist/` que sirve el backend Go. Aceptado como riesgo de
herramienta dev; re-auditar antes de un release público formal.

## Ítems revisados y limpios

- **Provider keys/tokens en TODO el historial** (todas las ramas): `sk_`,
  `ghp_`, `AKIA`, `AIza`, `xox`, `BEGIN PRIVATE KEY` → 0 secretos reales
  (solo un placeholder `sk-ant-oat01-…` en una skill y reportes que citan los
  propios patrones).
- **IP real de platypy** (`<ip-interna>`): no aparece en ningún archivo
  trackeado ni en el historial; solo el alias textual "platypy".
- **Bench E0-H3** (JSON): solo conteos de tokens, sin credenciales.
- **`docs/llms-full.txt` / `docs/adk-docs.txt`**: documentación ADK, sin datos
  del proyecto.
- **Endpoint/agente**: URL base de Ollama y sidecar apuntan a localhost;
  ningún secreto en `agent.py`/`.envrc.example`.
- **SCA**: `uv audit` data-platform (26) y ai-sidecar (31) → 0 vulnerabilidades;
  `pnpm audit` frontend → solo dev-only (ver #5).

## Remediación pendiente (acciones con aprobación)

1. **Force-push** de la historia reescrita a `origin/talk-to-your-data`
   (limpia el secreto del remoto). →
   `git push --force-with-lease origin talk-to-your-data && git fetch -p origin`
2. (Opcional) `git gc --prune=now` para descartar objetos viejos locales.
3. Backup de restauración disponible: `githuba-backup.bundle` (temporal, fuera
   del repo) por si se requiere revertir antes del push.