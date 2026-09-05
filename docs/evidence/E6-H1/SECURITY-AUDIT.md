# SECURITY-AUDIT — E6-H1 Frontend autenticado + NL2SQL (endpoints)

Auditoría de seguridad de endpoints y del incremento (backend JWT, NL2SQL,
compose). Incluye pruebas ejecutadas contra los endpoints desplegados.

## Superficie de ataque

| Endpoint | Auth | Notas |
|---|---|---|
| `GET /` (SPA) | pública | sirve la app; login embebido |
| `GET /healthz` | pública | healthcheck |
| `POST /api/login` | pública | rate-limit anti fuerza bruta + body limit |
| `GET /api/verify` | pública | valida token (oráculo de validez) |
| `GET /api/me` | JWT | devuelve email del claim |
| `POST /api/v1/query` | JWT | proxy→sidecar (guardas SQL) + rate-limit + body limit |
| `POST /api/v1/nl2sql` | JWT | proxy→sidecar (LLM + guardas SQL) + rate-limit + body limit |
| Sidecar `127.0.0.1:8000` | sin auth | **solo loopback** (no expuesto a la red) |
| Postgres `127.0.0.1:5433` | password | **solo loopback** |

## Pruebas ejecutadas (stack desplegado)

| Prueba | Resultado |
|---|---|
| SPA sin token | 200 |
| `/api/v1/query` y `/api/v1/nl2sql` sin token | 401 |
| Token `alg=none` | 401 (algoritmo fijado a HS256) |
| Token HS256 con issuer distinto | 401 (issuer validado) |
| Token expirado | 401 |
| Login con credenciales inválidas | 401 |
| Login repetido (fuerza bruta) | 429 tras ~10 intentos/min |
| Body de 2 MB a `/api/v1/query` | 413 (MaxBytesReader 1 MB) |
| Sidecar en IP LAN | sin respuesta (solo loopback) |
| Consulta legítima autenticada | 200 con datos gold |

## Hallazgos y remediación

### Aplicados en este incremento

1. **JWT alg confusion (CWE-347)** — MEDIUM → corregido: `jwt.WithValidMethods([HS256])`
   + `jwt.WithIssuer("genbi-futbol")` en `authHandler` y `handleVerify`.
2. **Fuerza bruta en login (CWE-307)** — MEDIUM → mitigado: rate-limiter por IP
   (10/min) sobre `/api/login`.
3. **Abuso de NL2SQL (DoS sobre Ollama) (CWE-770)** — MEDIUM → mitigado:
   rate-limiter por IP (30/min) sobre `/api/v1/query` y `/api/v1/nl2sql`.
4. **Body sin límite (CWE-770)** — LOW → corregido: `MaxBytesReader` 1 MB en
   login y proxies.
5. **Sidecar/Postgres expuestos en `0.0.0.0`** — MEDIUM → corregido: bind a
   `127.0.0.1`. Todo el acceso pasa por el app (`:8081`) con JWT.
6. **Inyección SQL (CWE-89)** — la SQL generada por el LLM y la del usuario pasan
   por `validate_sql` (una sola sentencia SELECT, allow-list, LIMIT forzado,
   tablas-función bloqueadas, alias de CTE ignorados). Sin exposición directa.
7. **Inyección de prompts (CWE-943)** — la pregunta del usuario nunca se
   interpola en SQL: el LLM solo genera SQL que se valida antes de ejecutar.

### Pendientes (aceptados para POC/curso)

- **Token en `localStorage`** (CWE-922) — MEDIUM aceptado: en producción usar
  cookie `httpOnly` + CSP estricta (deferida a E5/E6). El único valor en
  localStorage es `genbi_auth_token`.
- **Rate limit en memoria** (por IP, single-instance) — si hay varios nodos,
  mover a Redis. Aceptado para POC.
- **Login sin bloqueo de cuenta / sin hashing** (credenciales demo por entorno,
  AUTH_EMAIL/AUTH_PASSWORD) — POC de curso; en producción usar bcrypt + store.
- **SCA frontend**: 6 vulns dev-only (CLI `shadcn`) preexistentes, registrado en
  HEARTBEAT.

## Matriz de severidad

| Severidad | Hallazgos |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 4 → corregidos/mitigados (alg confusion, fuerza bruta, abuso LLM, exposición 0.0.0.0) |
| LOW | 2 → corregidos (body limit, JWT hardcodeado/credenciales hardcodeadas) |

## Veredicto

Sin CRITICAL/HIGH en runtime → **Security Clearance**. Endpoints protegidos con
JWT fijado a HS256, rate-limiting, body limit y sidecar/DB solo loopback.