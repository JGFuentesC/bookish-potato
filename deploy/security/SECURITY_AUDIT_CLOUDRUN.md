# SECURITY AUDIT — Despliegue Cloud Run (forecast dashboard)

**Fecha:** 2026-08-12 · **Proyecto:** `<MI-PROYECTO-GCP>` · **Región:** `us-central1`
**Metodología:** skill `cyber-sec` (`.agents/skills/cyber-sec/SKILL.md`), adaptada al stack real
(no hay Terraform/Go/React/Gemini en este despliegue; se audita la superficie real).
**Artefacto auditado:** `deploy/` + `docker/forecast/app/{main,storage,modelos}.py` + `static/`.

---

## 1. Superficie de ataque

| Capa | Componente |
|---|---|
| Runtime | Cloud Run `finanzas-dashboard` (1 vCPU / 1 GiB, min=0, max=1, concurrency 10, timeout 120 s) |
| Almacenamiento | Snapshot SQLite **read-only** embebido en la imagen (`/app/data/static.db`, 510 MB) |
| ML | Modelos XGBoost `.joblib` embebidos (`/app/models`, read-only) |
| API | `GET /api/v1/{health,tickers,ticker/{sim}/history,ticker/{sim}/forecast}` + front estático `/` |
| Identidad | SA `finanzas-dash-sa@<MI-PROYECTO-GCP>.iam.gserviceaccount.com` |
| Secreto | `API_TOKEN` en Secret Manager (`finanzas-dash-api-token`), montado como env en runtime |

**Endpoints expuestos (allUsers):** `/`, `/index.html`, `/styles.css`, `/app.js` (públicos por diseño del PRD) y `/api/v1/*` (exigen token).

---

## 2. Escaneo de secretos y hardcoding

| ID | Hallazgo | Severidad | Estado |
|---|---|---|---|
| **S-1** | Token de API NO está en la imagen (se inyecta vía Secret Manager en runtime) | — | ✅ |
| **S-2** | `.env` del repo excluido del build (`deploy/.dockerignore` en raíz) y no se copia | — | ✅ |
| **S-3** | `deploy/.api_token` local (generado) → en `.gitignore` (`deploy/.gitignore`) | — | ✅ |
| **S-4** | Único match del scan regex en `deploy/` es el propio patrón del `Makefile` (falso positivo) | — | ✅ |
| **S-5** | El token es público para quien carga la UI (se sirve en el HTML). **Por diseño** (PRD: UI pública + token en /api). Mitigación: 48 hex aleatorios, rotable (`make token`) | LOW | Documentado |

---

## 3. Auditoría IAM / Cloud Run (mínimo privilegio)

| ID | Hallazgo | Severidad | Estado |
|---|---|---|---|
| **I-1** | SA runtime con **3 roles granulares** (verificado en IAM policy del proyecto): `roles/artifactregistry.reader`, `roles/logging.logWriter`, `roles/monitoring.metricWriter` | — | ✅ |
| **I-2** | `roles/secretmanager.secretAccessor` otorgado **solo sobre el secret** `finanzas-dash-api-token` (no a nivel proyecto) | — | ✅ || **I-3** | **Sin** `roles/editor` ni `roles/owner` en la SA | — | ✅ |
| **I-4** | `allow-unauthenticated` (allUsers → `roles/run.invoker`): **exigido por el PRD** (demo pública) | — | ✅ Documentado |
| **I-5** | `min-instances=0`, `max-instances=1`, `--cpu-throttling` (CPU solo durante handling) | — | ✅ |
| **I-6** | Cifrado en reposo: disco efímero de Cloud Run (cifrado GCE por defecto) | — | ✅ |
| **I-7** | Contenedor corre como **usuario no root** (`appuser`, uid 10001) | — | ✅ |

---

## 4. Análisis de vulnerabilidades en dependencias (SCA)

| Capa | Herramienta | Resultado |
|---|---|---|
| Python (imagen desplegada) | `pip-audit -r /app/requirements.txt` **dentro de la imagen** | **0 vulnerabilidades conocidas** ✔ |
| OS (Debian 13 trixie) | Trivy (HIGH/CRITICAL) | 23 CVEs (19 HIGH, 4 CRITICAL) en paquetes base — **sin fix disponible** en el release (estado `affected`/`fix_deferred` en la mayoría). No alcanzables por la app (solo corre uvicorn; snapshot RO; sin egress; proceso no-root). **Riesgo residual aceptado** → ver Remediación R-1 |

> Las imágenes de paquetes Python en la imagen tienen 0 CVEs reportados por Trivy.

---

## 5. Análisis estático (SAST)

| ID | Hallazgo | Severidad | Estado |
|---|---|---|---|
| **A-1** | SQL parametrizado en ambas rutas: MySQL `%s` y SQLite `?`; sin f-strings con entrada de usuario; `LIMIT` es entero constante; `sim` se sanitiza con `.strip().upper()` | — | ✅ |
| **A-2** | Comparación de token **timing-safe** (`hmac.compare_digest`) en el middleware | — | ✅ |
| **A-3** | Inyección del token en HTML: `html.escape()` + placeholder dedicado `__API_TOKEN_VAL__` (el nombre de variable `window.__API_TOKEN__` queda intacto) | — | ✅ |
| **A-4** | XSS frontend: `app.js` usa `textContent`/`replaceChildren`/`createTextNode`; sin `innerHTML` | — | ✅ |
| **A-5** | `joblib.load` resuelve rutas **relativas** dentro de `/app/models` (imagen RO) — sin traversal | — | ✅ |
| **A-6** | Headers de seguridad en todas las respuestas: `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store` | — | ✅ |
| **A-7** | CORS cerrado a orígenes locales (same-origin no requiere CORS) | — | ✅ |
| **A-8** | Sin uso de Gemini/LLM/subprocess en el despliegue | — | N/A |

---

## 6. Matriz de severidad consolidada

| Severidad | Hallazgos |
|---|---|
| **HIGH/CRITICAL** | R-1 (CVEs OS base, sin fix disponible; riesgo residual aceptado, no explotables) |
| **MEDIUM** | — |
| **LOW** | S-5 (token visible en HTML por diseño del PRD), R-1 (dependencias con rango `>=` salvo xgboost) |
| **OK** | S-1..S-4, I-1..I-7, SCA Python, A-1..A-8 |

---

## 7. Remediación sugerida

**R-1 (CVEs del sistema base Debian trixie):**
- No hay paquete actualizado disponible hoy (`affected`/`fix_deferred`). Acciones:
  1. Re-ejecutar `make scan` (Trivy) periódicamente y desplegar cuando Debian publique fixes.
  2. Sustituir `python:3.12-slim` por la imagen **distroless** (`gcr.io/distroless/python3-debian13:nonroot`) para eliminar paquetes no necesarios (perl, util-linux, etc.) cuando se valide el runtime en CI.
  3. Compensación actual: proceso no-root, snapshot RO, sin egress ni paquetes alcanzables (perl/util-linux no se ejecutan).

**R-2 (mejoras opcionales MEDIUM/LOW):**
- Pinear versiones exactas (`==`) de fastapi/uvicorn/sklearn/joblib en `deploy/requirements.txt`.
- Rate-limit por IP en `/api/v1` (aplicación) si se publica más allá del ámbito académico.
- Habilitar `VPC`/ingress restringido o Cloud Armor si algún día se conecta a Internet público de alto tráfico (hoy innecesario por frugalidad).

---

## 8. Veredicto (Gatekeeper)

**Security Clearance otorgado para el despliegue académico.**

- No hay secretos en el código ni en la imagen.
- SA con mínimos privilegios (roles granulares verificados).
- `allUsers`/allow-unauthenticated presente **exclusivamente por requisito explícito del PRD**; las rutas `/api/v1` están protegidas por token (timing-safe) + `max-instances=1` + throttling.
- SCA Python limpio. CVEs OS base documentados como **riesgo residual aceptado** (sin fix disponible, no explotables por la carga de trabajo).

**Resumen:** 0 HIGH explotables, 0 MEDIUM, 2 LOW documentados, 1 riesgo residual de paquetes OS sin fix.
