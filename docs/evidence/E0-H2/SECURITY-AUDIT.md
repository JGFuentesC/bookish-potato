# SECURITY-AUDIT — E0-H2 Orquestación de contenedores

Fecha: 2026-08-19 · Auditor: cyber-sec (SAST/SCA/secretos) · Alcance: cambios del incremento E0-H2
(`infra/`, `backend/cmd/server/`, `ai-sidecar/src/genbi_ai/api/`, `.envrc`, `.env.example`, `Makefile`, `README.md`).

## Matriz de severidad

| Severidad | Cantidad | Hallazgos |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 0 | — |
| MEDIUM | 0 | — |
| LOW | 2 | S-1 contenedor root en sidecar (CORREGIDO) · S-2 sin CSP (diferido con plan) |
| INFO | 1 | S-3 aviso deprecación httpx/Starlette |

**Veredicto: SECURITY CLEARANCE.** Sin hallazgos CRITICAL/HIGH; ambos LOW con remediación documentada.

## Comprobaciones y resultado

### Secretos y hardcoding
- Escaneo recursivo de patrones (provider keys, `BEGIN PRIVATE KEY`, `sk_*`, `AKIA*`, `ghp_*`): **sin coincidencias** en archivos trackeados.
- `.envrc` (commiteable) solo declara variables con defaults vacíos/generic (p. ej. `POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"`): sin valores sensibles.
- `.envrc.local` (password dev + IP de platypy): confirmado **ignorado por git** (`git check-ignore` OK), no se versiona.
- Compose no consume `.env`; interpola desde el entorno de direnv.

### SCA (dependencias) por módulo
- `ai-sidecar`: `uv audit` → "Found no known vulnerabilities… in 31 packages" (sin vulnerabilidades).
- `frontend`: `pnpm audit` → "No known vulnerabilities found".
- `backend`: `go.mod` sin dependencias externas (solo stdlib) → no árbol que auditar; `go vet` limpio.
- Nota: `uv pip audit` no existe en uv 0.11.6; se usó `uv audit`.

### SAST
- `backend/cmd/server/main.go`: sin entrada de usuario, sin SQL, sin `exec`/comandos; únicamente `GET /healthz` y estático SPA. **Clean.**
- `ai-sidecar/src/genbi_ai/api/main.py`: endpoint estático sin input. **Clean.**
- `infra/docker-compose.yml`: montaje del lakehouse `ro` (write denegado verificado), red de stack con egress solo a Ollama externo. **Clean.**
- `infra/Dockerfile.app`: distroless `nonroot`. **Clean.**

## Hallazgos

#### [LOW] S-1 — Sidecar corría como root
**File:** `infra/Dockerfile.sidecar`
**CWE:** CWE-250

**Descripción:** la imagen `python:3.12.14-slim` corre como root; el sidecar era el único contenedor
del stack sin usuario no privilegiado.

**Remediación (CORREGIDA, verificada):**
```dockerfile
RUN useradd --create-home --uid 10001 genbi && chown -R genbi:genbi /app
USER genbi
```
**Verificación:** `docker inspect genbi-ai-sidecar-1 --format '{{.Config.User}}'` → `genbi`; contenedor
`healthy` y `GET /health` → 200 tras rebuild.

#### [LOW] S-2 — Sin Content-Security-Policy en la SPA
**File:** `backend/cmd/server/main.go`
**CWE:** CWE-693

**Descripción:** el servidor no emite CSP. Se añadieron `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY` y `Referrer-Policy` (verificados en `curl -I`), pero una CSP completa requiere
auditar scripts/estilos inline del build de Vite, que aún cambia en E5/E6.

**Remediación:** diferida a E5/E6 (cuando el frontend tenga la SPA real y el bundle final); aplicar
`Content-Security-Policy` con `frame-ancestors 'none'` + `default-src 'self'` ajustada al bundle.
**Trigger de reevaluación:** cierre de E5 (integración app↔frontend).

#### [INFO] S-3 — Deprecación httpx en TestClient
**File:** `ai-sidecar/src/genbi_ai/api/main.py` (test)
**Descripción:** `starlette.testclient` avisa que `httpx` será reemplazado por `httpx2`. No es
vulnerabilidad. Se revisa al pinar dependencias en E3.

## Remediación sugerida (plan priorizado)
1. S-1: aplicada y verificada (no bloqueante).
2. S-2: programada en E5/E6 (no bloqueante; SPA sin contenido de usuario en E0).
3. S-3: al pinar versiones del sidecar en E3.