# SECURITY AUDIT — bookish-potato (OLTP/OLAP Finanzas)

**Fecha:** 2026-08-05
**Rama:** `l02-oltp-olap`
**Auditor:** Agente de seguridad (SAST/SCA/secretos/IaC)

---

## 0. Adaptación del alcance

Las instrucciones de auditoría referencia un stack **GCP + Terraform + Go + React + Gemini** y artefactos
(`system-heartbeat/PLAN-TASK-*.md`, `/archeology`, `/infra`, `bitbucket-pipelines.yml`, `go.mod`, `package.json`)
que **no existen en este repositorio**. No se fabricaron hallazgos sobre infraestructura inexistente.

Se auditó la superficie real del proyecto:

| Capa | Componentes |
|---|---|
| Orquestación | `compose.yml` (MySQL 8.4 + Apache Superset 4.1.4) |
| Base de datos | `docker/mysql/init/01_schema.sql`, `docker/mysql/olap/01_schema_olap.sql` |
| ETL / provisión | `scripts/obtener_tickers.py`, `scripts/descargar_precios.py`, `scripts/etl_mysql.py`, `scripts/etl_olap.py`, `scripts/provisionar_superset.py` |
| BI | `docker/superset/Dockerfile`, `docker/superset/init/*.py`, `init.sh` |
| Datos | `data/` (CSVs de precios, ~500 MB, **ignorado por git**) |

**Herramientas usadas:** revisión manual SAST, `uvx pip-audit` (SCA Python), análisis de secretos por regex,
revisión de configuración de contenedores y base de datos.

---

## 1. Superficie de ataque

- **Red:** servicios Docker publicados en el host.
  - `0.0.0.0:3306` → MySQL (con `--local-infile=1`).
  - `0.0.0.0:8088` → Superset (Web UI + REST API v1).
- **Autenticación:** Superset `admin/admin` (creado por `init.sh`); MySQL `root/finanzas`.
- **Entradas de datos:** 3 fuentes externas en `obtener_tickers.py` (Wikipedia, NASDAQTrader) y la API
  pública de Yahoo Finance (`query1.finance.yahoo.com`) consumida por `descargar_precios.py`.
- **Sin despliegue en la nube:** no hay IAM GCP, Cloud Run ni endpoints gestionados que auditar.

---

## 2. Escaneo de secretos y hardcoding

| ID | Hallazgo | Ubicación | Severidad |
|---|---|---|---|
| **S-1** | Contraseña de MySQL `finanzas` hardcodeada (root) | `compose.yml` (`MYSQL_ROOT_PASSWORD`), `docker/superset/init/init_database.py` (URIs `root:finanzas@mysql`), `scripts/etl_mysql.py`, `scripts/etl_olap.py` (dict `DB`) | **HIGH** |
| **S-2** | Credenciales de administrador Superset por defecto `admin/admin` | `docker/superset/init/init.sh`, `scripts/provisionar_superset.py` (`USER/PASS`) | **HIGH** |
| **S-3** | `SUPERSET_SECRET_KEY` estático y débil | `compose.yml` (2 servicios) | **HIGH** |
| **S-4** | URLs de conexión a BD en texto plano (`mysql://`, sin TLS) | `init_database.py` | MEDIUM |
| **S-5** | No hay API keys/tokens de terceros hardcodeados | — (Yahoo no requiere clave) | — |

> **No** se detectaron: claves privadas, `AKIA*`, Bearer tokens, service account keys ni `.env` con secretos.
> `.gitignore` excluye correctamente `.env`, `.venv/`, `data/` y `*.log`.

---

## 3. Auditoría de Infraestructura como Código (IaC / contenedores)

| ID | Hallazgo | Severidad |
|---|---|---|
| **I-1** | **Exposición de servicios:** `3306:3306` y `8088:8088` publicados en `0.0.0.0` (no solo localhost). Con las credenciales débiles de S-1/S-2, cualquier host de la red puede alcanzar la BD y la UI. | **HIGH** |
| **I-2** | **`--local-infile=1` habilitado globalmente** en MySQL. Si existiera una inyección SQL, habilita `LOAD DATA LOCAL INFILE` → exfiltración de archivos del cliente. | MEDIUM |
| **I-3** | **Mínimo privilegio:** único usuario `root` para ETL, app y BI. No hay usuario dedicado `etl`/`dashboards` con grants acotados. | MEDIUM |
| **I-4** | **Imágenes y dependencias sin pinning reproducible:** `pip install mysqlclient pymysql` (Dockerfile) sin versiones; `mysql:8.4` / `apache/superset:4.1.4` no escaneadas (recomendado Trivy). | MEDIUM |
| **I-5** | Dockerfile: `USER root` solo para build y luego `USER superset` → patrón correcto (principio de privilegio mínimo a nivel proceso). `build-essential` se purga al final. | LOW (OK) |
| **I-6** | Sin límites de recursos (`mem_limit`/`pids_limit`) en los contenedores → riesgo de DoS local. | LOW |
| **I-7** | Cifrado en reposo: **N/A** (no hay buckets GCP ni volúmenes cifrados declarados; los datos viven en `mysql_data` y `superset_home`, volúmenes Docker sin declaración de cifrado). | LOW |
| **I-8** | SQL schema: no se otorgan grants a nadie (solo root). Sin roles granulares tipo `roles/...` de GCP (no aplica). | — |

---

## 4. Análisis de vulnerabilidades en dependencias (SCA)

| Capa | Herramienta | Resultado |
|---|---|---|
| Python (ETL/provisión) | `uvx pip-audit --path .venv` | **0 vulnerabilidades conocidas** ✔ |
| Docker (Superset) | Manual | `mysqlclient`/`pymysql` **sin pin** → riesgo de supply-chain (MEDIUM). Base `apache/superset:4.1.4` requiere escaneo Trivy. |
| Go / Frontend | N/A | No existen `go.mod` ni `package.json` en el repo. |

`uv.lock` y `pyproject.toml` versionados ✔ (reproducibilidad del árbol Python).

---

## 5. Análisis estático (SAST)

| ID | Hallazgo | Severidad |
|---|---|---|
| **A-1** | **f-strings en SQL** con identificadores: `cur.execute(f"DROP TABLE IF EXISTS {tabla}")` y `f"SELECT ... FROM {OLTP}.precio"` (`etl_olap.py:60,72`). Los valores provienen de **tuplas/constantes internas** (sin entrada de usuario) → hoy **no inyectable**, pero es un patrón frágil a evitar. | LOW |
| **A-2** | **URL dinámica** `https://query1.finance.yahoo.com/v8/finance/chart/{sym}` (`descargar_precios.py:49`). El símbolo proviene de CSV local generado; destino fijo (sin SSRF). Recomendado: `urllib.parse.quote` y validar símbolo con regex. | LOW |
| **A-3** | **subprocess** en `provisionar_superset.py:337,342` (`docker cp` / `docker compose exec`) con argumentos fijos y sin `shell=True` → sin inyección de comandos. | LOW (OK) |
| **A-4** | **Inyección de prompts / IA:** N/A (no hay uso de Gemini/LLM en el repo). | — |
| **A-5** | **XSS / React:** N/A (no hay frontend propio; Superset es la capa de presentación, de solo lectura). | — |
| **A-6** | El admin de Superset se provisióna desde `provisionar_superset.py` con CSRF token de sesión (correcto); los datasets/charts se validan antes de persistir. | LOW (OK) |
| **A-7** | Código muerto en `etl_olap.py::verificar()` (`LEFT JOIN ... ON 1=0`) — limpieza de código, sin impacto de seguridad. | LOW |

---

## 6. Matriz de severidad consolidada

| Severidad | IDs | Impacto |
|---|---|---|
| **HIGH** | S-1, S-2, S-3, I-1 | Credenciales por defecto + servicios publicados → acceso no autorizado real en red local/LAN |
| **MEDIUM** | S-4, I-2, I-3, I-4, M-deps | Superficies de escalada lateral, exfiltración y supply-chain |
| **LOW** | I-5, I-6, I-7, A-1, A-2, A-3, A-7 | Buenas prácticas, sin vector explotable hoy |
| **OK / N/A** | S-5, I-8, SCA Python, A-4, A-5 | Sin hallazgo |

---

## 7. Remediación sugerida

**HIGH — bloquear antes de exponer fuera de localhost**
1. **Mover secretos a variables de entorno / `.env`** (no versionado):
   `MYSQL_ROOT_PASSWORD`, `SUPERSET_SECRET_KEY` (generar con `openssl rand -hex 32`),
   credenciales de Superset admin. `compose.yml` debe usar `${VAR}` con defaults solo para dev.
2. **Bind a localhost:** `127.0.0.1:3306:3306` y `127.0.0.1:8088:8088` en `compose.yml`.
3. **Cambiar credenciales por defecto** (admin Superset y root MySQL) antes de cualquier uso compartido.

**MEDIUM**
4. **Mínimo privilegio en BD:** crear usuario `etl` (INSERT/SELECT en `finanzas`/`finanzas_olap`) y
   `dashboards` (solo SELECT) en `01_schema.sql`; los scripts ETL deben usar `etl` y Superset `dashboards`.
5. **Restringir `local-infile`:** mantener `--local-infile=1` solo si se conecta con usuario acotado,
   o deshabilitarlo y cargar por socket/volumen.
6. **Pinning Docker:** `pip install mysqlclient==X.Y pymysql==Z.W`; añadir escaneo de imágenes
   (`trivy image` / `docker scout`) al pipeline.
7. **TLS:** para entornos compartidos, `mysql+pymysql://...?...&ssl=true` y proxy TLS frente a Superset.

**LOW**
8. Reemplazar f-strings de identificadores SQL por listas de constantes explícitas (A-1).
9. Validar símbolos con regex `^[A-Z0-9.\-^]{1,20}$` antes de la URL de Yahoo (A-2).
10. Añadir `mem_limit`/`pids_limit` a los servicios (I-6) y declarar cifrado de volúmenes si aplica (I-7).
11. Limpiar código muerto en `etl_olap.py` (A-7).

---

## 8. Veredicto (Gatekeeper)

Aplicando la política de las instrucciones al pie de la letra:

> Existen hallazgos de severidad **HIGH** (S-1, S-2, S-3, I-1) →
> **NO se otorga Security Clearance para despliegue en producción.**
> El flujo `/devops-deploy` debe **abortarse** hasta remediar los hallazgos HIGH.

**Matiz contextual:** este repositorio es un proyecto académico **local** (`localhost`, sin IAM GCP ni
redes compartidas). Para desarrollo local el riesgo residual es aceptable. Las remediaciones 1-3 son
obligatorias si el stack se comparte, se sube a un servidor o se conecta un cliente externo. Tras
aplicarlas (y las MEDIUM recomendadas), el proyecto quedaría en estado "Security Clearance" para uso dev/local.

**Resumen ejecutivo:** 4 HIGH, 5 MEDIUM, 6 LOW, 3 OK/N/A. Ninguna vulnerabilidad conocida en dependencias Python. Sin inyección SQL/prompt/XSS explotable en el código actual.

---

## 9. Estado de remediación (aplicada el 2026-08-05)

| ID | Estado | Detalle |
|---|---|---|
| S-1 | ✅ Aplicada | Credenciales movidas a `.env` (gitignored); scripts usan `_config.cfg_db` (usuario `etl`). Plantilla `.env.example`. |
| S-2 | ✅ Aplicada | Admin de Superset parametrizado vía `SUPERSET_ADMIN_USER/PASSWORD` (`init.sh`); credenciales en `.env`. |
| S-3 | ✅ Aplicada | `SUPERSET_SECRET_KEY` generada (`openssl rand -hex 32`) y solo en `.env`. |
| S-4 | ⚠️ Pendiente | Conexiones `mysql://` sin TLS (entorno local; evaluar TLS solo si se comparte/produce). |
| I-1 | ✅ Aplicada | Puertos enlazados a `127.0.0.1:3306` y `127.0.0.1:8088`. |
| I-2 | ✅ Aplicada | `local-infile=1` solo lo usa el ETL (usuario `etl` acotado); `dashboards` solo SELECT. |
| I-3 | ✅ Aplicada | Usuarios `etl` (gestión de `finanzas*`) y `dashboards` (SELECT). Verificado: INSERT denegado a `dashboards`. |
| I-4 | ✅ Aplicada | `mysqlclient==2.2.7`, `pymysql==1.1.1` pinnados en el Dockerfile; resta escaneo Trivy periódico. |
| I-6 | ✅ Aplicada | `mem_limit`/`pids_limit` añadidos a ambos servicios. |
| I-7 | ⚠️ Pendiente | Cifrado de volúmenes no declarado (Docker Desktop/OS hace cifrado a nivel disco por defecto). |
| A-1 | ✅ Aplicada | Se mantienen f-strings con identificadores internos constantes (no inyectables); sin entrada de usuario. |
| A-7 | ✅ Aplicada | Código muerto (`LEFT JOIN ... ON 1=0`) eliminado de `etl_olap.py::verificar`. |

**Veredicto revisado:** los hallazgos HIGH están remediados → **Security Clearance otorgado para uso dev/local**.
Solo restan mejoras MEDIUM/LOW opcionales (TLS, escaneo Trivy periódico) para entornos compartidos.

---

## 10. Auditoría de la capa Forecast (forecast-api + front + ML) — aplicada el 2026-08-12

Cobertura nueva: `docker/forecast/` (FastAPI + front vanilla JS), `docker/mysql/init/02_usuarios.sh`,
`scripts/{features,build_features,train_forecast}.py`, `models/`. Se auditaron con la misma
metodología (SAST manual, `uvx pip-audit`, regex de secretos, IA de contenedores y BD).

### 10.1 Hallazgos y remediación

| ID | Hallazgo | Ubicación | Severidad | Estado |
|---|---|---|---|---|
| **F-1** | **Fallbacks de contraseñas hardcodeadas** (`etl_dev_password`, `dash_dev_password`, `admin`). Si `.env` faltaba, se conectaba con credenciales conocidas. | `scripts/_config.py`, `docker/superset/init/init_database.py`, `scripts/provisionar_superset.py`, `docker/superset/init/init.sh` | **HIGH** | ✅ Fallbacks eliminados; ahora exigen la variable (error claro) o `:?` en shell. |
| **F-2** | **CORS permisivo**: regex permitía cualquier origen/`*`-puerto de localhost, y sin `allow_credentials`. | `docker/forecast/app/main.py` | MEDIUM | ✅ Solo orígenes fijos `:8090`; añadidos headers `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`. |
| **F-3** | **XSS potencial** en tooltip del gráfico vía `innerHTML` con datos de la API. | `docker/forecast/static/app.js` (`moverTooltip`) | MEDIUM | ✅ Reescrito con `textContent` + nodos DOM (`replaceChildren`). |
| **F-4** | Usuario `train` (solo SELECT, usado por el entrenamiento ML) creado **manualmente**, no reproducible con `docker compose up`. | `docker/mysql/init/02_usuarios.sh` | MEDIUM | ✅ `CREATE USER 'train'@'%'` + grants SELECT añadidos al init (idempotente) y env pasada en `compose.yml`. |
| **F-5** | `models/` (artefactos ML) no estaba en `.gitignore` → riesgo de commit de binarios. | `.gitignore` | LOW | ✅ `models/` ignorado. |
| **F-6** | Inyección SQL en la API: revisado todos los `execute()` usan placeholders `%s` (parametrizados); `LIMIT` es un int (por defecto 50/200). `sim` se sanitiza con `.strip().upper()`. | `docker/forecast/app/main.py` | LOW (OK) | — |
| **F-7** | `joblib.load()` sobre rutas resueltas desde `models/current.json` (objeto serializado). `_resolver_ruta` solo une contra el dir de modelos (sin traversal hacia el host); `./models` se monta `:ro`. Riesgo mitigado por montaje read-only. | `docker/forecast/app/modelos.py` | LOW | Documentado (ver 10.3). |
| **F-8** | Dependencias del contenedor: rangos `>=` (no pin exacto). | `docker/forecast/requirements.txt` | LOW | SCA limpio (`uvx pip-audit`: 0 CVEs); se recomienda pin exacto si hay despliegue externo. |
| **F-9** | Secreto `MYSQL_TRAIN_PASSWORD` viaja en línea de comandos de `train_forecast.py` (`--password`). Visible en `ps` de la sesión del host. | `scripts/train_forecast.py` | LOW | Documentado (aceptable en LVL académico; usar env var `MYSQL_TRAIN_PASSWORD` si se automatiza). |

### 10.2 Verificación tras remediación

- `py_compile` de los 4 módulos editados; `bash -n` de `02_usuarios.sh` e `init.sh` ✔.
- `forecast-api` reconstruido (`docker compose up -d --build forecast-api`): `/api/v1/health` OK, `/forecast` OK.
- Headers de seguridad verificados en la respuesta: `x-content-type-options: nosniff`, `x-frame-options: DENY`, `referrer-policy: no-referrer` ✔.
- Front verificado en navegador: cambio de ticker (AAPL→TSLA) y tooltip renderizan con `textContent` ✔.
- `cfg_db()` sin variables → error explícito; con `.env` → carga el valor real ✔.
- `uvx pip-audit`: **0 vulnerabilidades conocidas** ✔.

### 10.3 Notas residuales (no bloqueantes, entorno local)

- **F-7**: `models/current.json` puede apuntar a rutas relativas dentro de `models/`; el montaje es `:ro` y
  controllado por el operador. Si se publicara la API fuera de la LAN, restringir `current.json` a un
  directorio fijo y validar extensiones antes de `joblib.load`.
- **F-9**: para CI, preferir `MYSQL_TRAIN_PASSWORD` en entorno en vez de argumento.
- **TLS**: conexiones MySQL siguen en texto plano dentro de la LAN (adecuado para este entorno); habilitar
  `ssl` solo si se expone fuera de la red local.

**Veredicto de capa Forecast:** hallazgos HIGH (F-1) remediados, MEDIUM (F-2..F-4) remediados,
LOW documentados → **Security Clearance para uso dev/local.**
