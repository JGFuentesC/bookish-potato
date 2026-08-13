# SECURITY AUDIT — Preparación del repo para publicación pública

**Fecha:** 2026-08-12 · **Repo:** `JGFuentesC/bookish-potato` (rama `feature/machine-learning`)
**Alcance:** commit a punto de hacerse (12 tracked modificados + untracked nuevos: `deploy/`, `docker/forecast/`, scripts ML, docs).
**Objetivo:** verificar que **ningún identificador de infraestructura real** se publique antes del commit.
**Método:** skill `cyber-sec` (`.agents/skills/cyber-sec/SKILL.md`) — superficie, secretos, IaC/IAM, SCA, SAST, matriz, remediación, veredicto.

---

## 0. Estado del repo (verificado)

- **Historia git limpia:** 2 commits, sin `run.app`, sin IPs LAN, sin `.env` ni tokens en `git log --all` (escaneado `-S "run.app"`, `-S "192.168"`, `-- .env`). ✅
- **Remote:** `git@github.com:JGFuentesC/bookish-potato.git` — rama aún no publicada con estos cambios.
- **`.env` y `deploy/.api_token`:** confirmados como **ignored** (`git check-ignore`). No viajarán. ✅
- **`models/`, `data/`, `deploy/data/`:** ignored. ✅

**Conclusión parcial:** el riesgo está en **archivos que se van a commitear ahora**, no en el historial.

---

## 1. Superficie auditada

| Capa | Artefactos |
|---|---|
| Despliegue GCP | `deploy/Makefile`, `deploy/Dockerfile`, `deploy/requirements.txt`, `deploy/scripts/*`, `deploy/data/` |
| Docs de despliegue | `deploy/INFRA_ATLAS.md`, `deploy/INFRA_ATLAS_LIVE.md`, `deploy/COST_ESTIMATE.md`, `deploy/security/SECURITY_AUDIT_CLOUDRUN.md` |
| Stack local | `compose.yml`, `.env.example`, `docker/mysql/init/02_usuarios.sh`, `docker/superset/init/*` |
| ML | `scripts/{features,build_features,train_forecast}.py`, `docker/forecast/app/{main,storage,modelos}.py`, `docs/PLAN_ML.md` |
| Config personal | `.agents/skills/cyber-sec/SKILL.md` |
| Lectura | `README.md`, `docs/SECURITY_AUDIT.md`, `pyproject.toml`, `uv.lock` |

---

## 2. Hallazgos de exposición de información sensible

> Ninguno son secretos de credenciales (contraseñas/tokens no se publican); **todos son identificadores de infraestructura real** que un atacante usaría para mapear el entorno.

### A. Identificadores de Cloud Run / GCP (proyecto real)

| # | Severidad | Archivo | Dato expuesto |
|---|---|---|---|
| **H-1** | **HIGH** | `deploy/INFRA_ATLAS.md:33` | URL pública real de Cloud Run (host `<servicio>-<hash>-uc.a.run.app`) + alias con número de proyecto |
| **H-2** | **HIGH** | `deploy/INFRA_ATLAS.md:34,36,37` | Ruta real de imagen AR (`us-central1-docker.pkg.dev/<proyecto>/…:<tag>`), SA email, nombre del secret, nº de versiones del secret |
| **H-3** | **HIGH** | `deploy/INFRA_ATLAS_LIVE.md` (todo) | Volcado en vivo: URL real, SA, secret, proyecto. Además es **regenerable** con `make atlas` |
| **H-4** | **MEDIUM** | `deploy/security/SECURITY_AUDIT_CLOUDRUN.md:3,18,19,42` | Proyecto real, SA email, secret name |
| **H-5** | **MEDIUM** | `deploy/COST_ESTIMATE.md:3` | Proyecto + región reales |
| **H-6** | **MEDIUM** | `deploy/Makefile:13,15,19,20` | Defaults hardcoded: `PROJECT=<proyecto-real>`, `REGION=us-central1`, `SA=finanzas-dash-sa`, `SECRET=finanzas-dash-api-token` |

### B. Topología de red local / LAN (hosts internos)

| # | Severidad | Archivo | Dato expuesto |
|---|---|---|---|
| **H-7** | **HIGH** | `compose.yml:20` | Bind LAN real `192.168.x.x:3306:3306` |
| **H-8** | **HIGH** | `compose.yml:78` | Default `MYSQL_HOST: ${MYSQL_HOST:-192.168.x.x}` |
| **H-9** | **MEDIUM** | `scripts/train_forecast.py:23,65` | Default `--host 192.168.x.x` (2×) |
| **H-10** | **MEDIUM** | `docker/forecast/app/storage.py:66` | Default `MYSQL_HOST = "192.168.x.x"` |
| **H-11** | **MEDIUM** | `README.md:295,302,303,309,310` | IP LAN, comando `scp <entrenador>:~…`, detalle de red |
| **H-12** | **MEDIUM** | `docs/PLAN_ML.md:17,37,39,45,102-104,126` | Topología completa: IPs de la máquina de entrenamiento y del host, bind, usuario `train` |
| **H-13** | **LOW** | `docs/SECURITY_AUDIT.md:187,192` | Mención de hostname interno (sin IP) |

### C. Config personal / flujo interno

| # | Severidad | Archivo | Dato expuesto |
|---|---|---|---|
| **H-14** | **MEDIUM** | `.agents/skills/cyber-sec/SKILL.md` | Skill del orquestador que referencia flujo interno (`system-heartbeat/`, `bitbucket-pipelines.yml`, `/infra`, `go.mod`) — no aporta nada al repo público |

### D. Correctamente protegido (confirmado, sin acción)

| Ítem | Estado |
|---|---|
| `.env` (raíz) | ignored ✅ |
| `deploy/.api_token` (token real 48 hex) | ignored vía `deploy/.gitignore` ✅ |
| `deploy/data/` (snapshot 510 MB) | ignored ✅ |
| `models/`, `data/`, `.venv/` | ignored ✅ |
| `.dockerignore` (raíz) | excluye `.env`, `data`, `.agents`, `docs`, `.git` ✅ |
| `docker/forecast/.dockerignore` | excluye `.env` ✅ |
| `.env.example` | solo placeholders `cambiar_*` ✅ |
| Código `main.py`/`app.js`/`storage.py` | sin credenciales; token vía env; placeholder `__API_TOKEN_VAL__` ✅ |

---

## 3. Auditoría IAM / IaC (skill §3)

- SA `finanzas-dash-sa`: roles granulares (verificado, sin `editor`/`owner`). ✅
- `allow-unauthenticated` presente **por PRD** (documentado en la auditoría de deploy). ✅
- Sin buckets ni bases de datos gestionadas; snapshot embebido read-only. ✅
- **Único punto IaC a corregir:** defaults del `Makefile` (H-6) y bind LAN de `compose.yml` (H-7/H-8) — no son privilegios mal asignados, son **identificadores**.

## 4. SCA (skill §4)

- Python imagen Cloud Run (`pip-audit` in-imagen): **0 CVEs**. ✅
- `pyproject.toml`/`uv.lock` local: deps con rangos, sin pin exacto (mejora opcional, no bloqueante). ✅
- Sin `package.json`/`go.mod` en este repo. N/A.

## 5. SAST (skill §5)

- API: SQL parametrizado, `hmac.compare_digest`, `html.escape`, sin `innerHTML`. ✅ (auditado en `SECURITY_AUDIT_CLOUDRUN.md`)
- Scripts nuevos ML (`features/build_features/train_forecast`): solo lecturas SQL parametrizadas a MySQL y `joblib` de `./models` (rutas relativas); sin subprocess con entrada de usuario. ✅
- Sin uso de Gemini/LLM en este repo → sección de prompt-injection N/A.

## 6. Matriz de severidad consolidada

| Severidad | Hallazgos | ¿Bloquea commit público? |
|---|---|---|
| **HIGH** | H-1, H-2, H-3, H-7, H-8 | **SÍ** — URLs/IPs reales del entorno |
| **MEDIUM** | H-4, H-5, H-6, H-9, H-10, H-11, H-12, H-14 | **SÍ** (recomendado antes de publicar) |
| **LOW** | H-13 | No |
| **OK** | §2.D, IAM, SCA, SAST | — |

---

## 7. Remediación sugerida (placeholder en vez de real)

> **ESTADO:** aplicada en su totalidad el 2026-08-12. Verificado con escaneo final (§2.D + rescan
> del working tree): sin URLs reales, sin IPs LAN, sin proyecto/SA reales, sin tokens en código.

1. **`deploy/Makefile`:** defaults → placeholders configurables por env:
   `PROJECT := $(or $(PROJECT_RAW),MI-PROYECTO-GCP)`, `REGION := $(or $(REGION_RAW),us-central1)`, `SA := finanzas-dash-sa`, `SECRET := finanzas-dash-api-token` (nombres genéricos OK si el usuario los redefine).
2. **`deploy/INFRA_ATLAS.md`:** URL → `https://<servicio>-<hash>-uc.a.run.app`, imagen → `…/finanzas-dashboard:<tag>`, proyecto → `<TU_PROYECTO>`; quitar nº de versiones del secret.
3. **`deploy/INFRA_ATLAS_LIVE.md`:** añadir a `deploy/.gitignore` (es volcado en vivo, se regenera con `make atlas`).
4. **`deploy/security/SECURITY_AUDIT_CLOUDRUN.md` y `deploy/COST_ESTIMATE.md`:** proyecto/SA/secret/región → placeholders (`<proyecto>`, `finanzas-dash-sa@<proyecto>.iam…`).
5. **`compose.yml`:** bind → `127.0.0.1:3306:3306` y `MYSQL_HOST: ${MYSQL_HOST:-127.0.0.1}` (el bind LAN fue una modificación local para entrenar).
6. **`scripts/train_forecast.py`:** `--host` default → `127.0.0.1`; docstring sin IP.
7. **`docker/forecast/app/storage.py`:** default host → `127.0.0.1`.
8. **`README.md`:** reemplazar IP LAN/`scp <entrenador>:…` por `$MYSQL_HOST` genérico; quitar IPs.
9. **`docs/PLAN_ML.md`:** sustituir IPs y hostnames por "máquina de entrenamiento" / `<host>`.
10. **`.agents/`:** añadir `.agents/` a `.gitignore` (config personal del asistente, no es contenido del repo).

> Ningún cambio de código funcional: solo defaults y documentación. El despliegue sigue funcionando vía variables env/`gcloud config`.

---

## 8. Veredicto (Gatekeeper)

**NOT READY — NO hacer commit público hasta aplicar §7.**

- No hay **secretos de credenciales** en riesgo (tokens/contraseñas ya están fuera de git). ✅
- Pero hay **9 identificadores HIGH/MEDIUM** (URLs reales, proyecto, SA, IPs LAN) que comprometen el repositorio si se publican tal cual.
- Tras la remediación (§7), el commit es **seguro de publicar**: verificar con `git add -N . && git diff` + el escaneo §2.D.
