# SECURITY-AUDIT — E1-H1 Esquema OLTP 3NF y migraciones

Fecha: 2026-08-26 · Skill: `.agents/skills/cyber-sec/SKILL.md` (SAST/SCA/secretos) + OWASP Top 10 · Veredicto: **SECURITY CLEARANCE**

## Superficie de ataque del incremento

No hay endpoints de red, autenticación ni entrada de usuario en runtime. El incremento añade:
- 8 pares de migraciones SQL estáticas (DDL/DML) aplicadas por golang-migrate en Docker.
- `scripts/derive_catalogs.py` (genera la semilla desde JSON locales) y `scripts/gen_erd.py` (conecta a Postgres local y escribe el ERD).
- `Makefile` (targets `migrate-up`/`migrate-down`) e `infra/docker-compose.yml` (puerto host Postgres `5433`).

## Matriz de severidad

| Severidad | Cantidad |
|---|---|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 0 |
| LOW | 1 (aceptado) |

## Hallazgos

### [LOW] A02 — Credencial visible en la línea de comando de `docker run` (Makefile)
**Archivo:** `Makefile` (targets `migrate-*`)
**CWE:** CWE-214 (Invocation of Process Using Visible Sensitive Information)

**Descripción:** El target `migrate-*` invoca `docker run -e PGPASSWORD=$(POSTGRES_PASSWORD) …`. El valor de la contraseña aparece en la salida verbosa de `make` y, brevemente, en `ps`/historial de shell.

**Compensación:**
1. Es una herramienta de desarrollo local sobre Docker Desktop (sin superficie pública, sin CI/CD de producción en este ciclo).
2. El DSN de golang-migrate va **sin contraseña** (`postgres://$(POSTGRES_USER)@postgres:5432/$(POSTGRES_DB)`); el secreto se inyecta solo vía variable de entorno `PGPASSWORD`, nunca en código ni en el DSN.
3. La contraseña vive en `.envrc.local` (gitignored) o en el `.env` del shell de direnv.

**Re-evaluación:** si en el futuro las migraciones se ejecutan en CI/producción, pasar el secreto vía secretos de CI y ocultar el comando (`@$(MIGRATE) …` o redirigir el comando).

**Remediación:** diferida a cuando exista CI/producción (no bloquea).

## Verificaciones

| Check | Comando | Resultado |
|---|---|---|
| Secretos provider (sk_, ghp_, AKIA, AIza, xox) | `git ls-files \| xargs grep -lE '…'` | 3 coincidencias = falsos positivos (texto de ayuda de una skill y reportes previos que citan los propios patrones). **0 secretos** |
| Passwords hardcoded en código | grep `POSTGRES_PASSWORD`/`password=` fuera de `.env.example`/seed/README | 0 |
| SCA Python (data-platform) | `uv audit` (workdir=data-platform) | 24 paquetes, **sin vulnerabilidades** |
| Inyección SQL | Revisión manual `gen_erd.py` (psycopg con placeholders `%s`), `derive_catalogs.py` (`sql_literal` escapa comillas), migraciones = SQL estático | Sin concatenación de entrada de usuario |
| Secreto en DSN de migraciones | `Makefile` | DSN sin contraseña (solo `PGPASSWORD` env) |
| Prompt injection / IA | N/A en este incremento (sin llamadas a LLM; llegan en E3) |
| XSS / renderizado | N/A en este incremento (sin frontend; llega en E6) |
| IaC / IAM | N/A (sin Terraform/GCP; infra local Docker) |

## Segundo pase (adversarial)

- `gen_erd.py`: la DSN se construye desde `os.environ` y **no se loguea**; no expone el secreto. Puerto `5433` hardcodeado es la convención del repo (documentada en README), no un valor de máquina.
- `derive_catalogs.py`: los INSERTs generados escapan `'` correctamente (`sql_literal`); los archivos de entrada son JSON locales, no entrada de red.
- Migraciones: sin `BEGIN`/`COMMIT` (golang-migrate los maneja); down en orden inverso sin `CASCADE` innecesario → no deja estado inconsistente.
- Sin hallazgos nuevos.

## Conclusión

**SECURITY CLEARANCE** otorgado. 1 hallazgo LOW aceptado con compensaciones documentadas. No hay bloqueos CRITICAL/HIGH.