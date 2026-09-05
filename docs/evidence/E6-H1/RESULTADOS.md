# RESULTADOS — E6-H1 Frontend autenticado + reporte con nueva UI + NL2SQL

Incremento: frontend React 19 + shadcn/ui + Tailwind con autenticación email/password
(JWT), endpoints protegidos, PromptInput (ai-chat-input), NL2SQL real (Ollama →
gold) y reporte talk-to-your-data con la nueva UI. Todo desplegado en Docker Compose.

## Qué se probó

### 1. Autenticación (backend Go + JWT)

| Comando | Resultado |
|---|---|
| `curl :8081/healthz` | `{"status":"ok"}` |
| `curl :8081/` (SPA sin token) | 200, sirve index.html |
| `curl :8081/api/me` sin token | 401 `missing or invalid authorization header` |
| `POST /api/login` con `user@genbi.com` / `password123` | 200, devuelve `{"token":"…"}` |
| `POST /api/login` con password incorrecto | 401 `invalid credentials` |

Rutas protegidas (JWT): `POST /api/v1/query`, `POST /api/v1/nl2sql`, `GET /api/me`.
Rutas públicas: SPA, `/healthz`, `/api/login`, `/api/verify`.

### 2. NL2SQL real (preguntas libres)

Endpoint nuevo `POST /api/v1/nl2sql` en el sidecar: traduce la pregunta en español a
SQL con `gemma4:latest` (Ollama platypy vía túnel SSH, `host.docker.internal:11434`),
valida la SQL (guardas SELECT/allow-list/LIMIT del endpoint /query) y la ejecuta
sobre gold; luego resume la respuesta en una frase.

| Pregunta (libre, escrita en la UI) | Respuesta | SQL generado |
|---|---|---|
| "cuantos goles metió thomas muller" | Thomas Müller metió 3 goles | `... WHERE (player_name ILIKE '%Thomas Muller%' OR ... ILIKE '%Thomas Müller%')` |
| "cuántos pases dio Messi en total" | 33,362 pases | `SELECT COUNT(*) FROM fct_pass WHERE player_name ILIKE '%Messi%'` |
| "qué equipo tiene más goles en la liga española" | Barcelona, 1,352 goles | `GROUP BY team_name ORDER BY total_goals DESC` |

Fix de acentos: el prompt del LLM instruye usar `ILIKE` y cubrir grafías con y sin
acento (Müller/Muller) — verificado (antes "thomas muller" daba 0 por `LIKE`).

### 3. UI (Chrome DevTools MCP, http://localhost:8081)

- Login email/password; error en credenciales inválidas; logout limpia el token
  (`localStorage` solo guarda `genbi_auth_token`, **no se guardan preguntas**).
- Dashboard muestra **solo la última pregunta/respuesta** (sin historial acumulado).
- PromptInput completo (modelo/effort/mic/adjuntos/morphing).
- Reporte in-app con 8 preguntas ejecutables vía NL2SQL.

### 4. Escenarios (8/8) verificados contra gold

Messi 508 goles · xG La Liga 0.111 · Messi 33,362 pases · Messi 220 asistencias ·
resultados 2020/21 · 1,095 penales · Messi 1,800 fuera de área · Barcelona 367,725 pases.

Nota de datos: `fct_pass.outcome_name` NULL para pases completados en gold actual →
los escenarios de pases usan "totales".

### 5. Despliegue Docker

3 contenedores healthy: `genbi-app` (:8081), `genbi-ai-sidecar` (:8000, alcanza
Ollama vía `host.docker.internal:11434`), `genbi-postgres` (:5433). El backend Go
proxea `/api/v1/query` y `/api/v1/nl2sql` al sidecar con JWT.

### 6. Verificaciones

- `go test ./...` (backend): ok.
- `uv run pytest` (sidecar): ok (23 tests, incluye CTE/ANSI/extract).
- `pnpm build` (frontend): ok.
- `make verify` global: ok.

### 7. Seguridad de endpoints (pruebas ejecutadas)

| Prueba | Resultado |
|---|---|
| `/api/v1/query` y `/api/v1/nl2sql` sin token | 401 |
| Token `alg=none` | 401 (HS256 fijado) |
| Token con issuer incorrecto | 401 |
| Token expirado | 401 |
| Login fuerza bruta | 429 tras ~10/min |
| Body 2 MB | 413 (límite 1 MB) |
| Sidecar/Postgres en IP LAN | sin respuesta (bind 127.0.0.1) |
| Query / NL2SQL autenticados | 200 con datos gold |

Endurecimiento aplicado: JWT `WithValidMethods(HS256)` + `WithIssuer`, rate
limiter por IP (login 10/min, API 30/min), `MaxBytesReader` 1 MB, sidecar y
Postgres solo loopback, `SIDECAR_URL` interna fija en compose, healthcheck
`-healthcheck` restaurado (contenedor `healthy`).

## Evidencia

- `frames/f1-dashboard.png` — dashboard con PromptInput.
- `frames/f2-muller.png` — pregunta libre NL2SQL respondida.
- `frames/f3-reporte.png` — panel de reporte.
- `ui-demo.gif` — GIF demo (dashboard → pregunta libre → reporte).
- `report.html` — autocontenido (base64) con sidebar navegable (anclajes + scroll
  activo), GIF demo y 8 escenarios; mismo formato que `E2-H1-adk/report.html`.