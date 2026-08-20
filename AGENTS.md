# AGENTS.md — GenBI Fútbol (bookish-potato)

Implementación incremental del PRD (`docs/PRD.md`) para clase. Todo el desarrollo es interactivo: un agente trabaja, el usuario da VoBo, se asegura y se commitea. Incrementos pequeños y tangibles: si un paso tarda más de ~1 bloque corto, se rompe en pedacitos verificables.

## Fuentes de verdad

- Producto: `docs/PRD.md` (épicas E0→E7, historias, tareas con verificación ejecutable). Si algo contradice este archivo, gana el PRD.
- Google ADK: **`docs/adk-docs.txt` es la única fuente de verdad** para APIs, imports y comandos de ADK. No inventar APIs de memoria ni consultar la web.
- ADRs en `docs/adr/` (001 stack, 002 modelo, 003 NL2SQL). E3-H1 tiene compuerta: ninguna historia posterior de E3 arranca sin ADR-003 firmado.
- Skills en el repo (`.agents/skills/`, versionadas): `emil-design-eng`, `impeccable`, `design-taste-frontend`, `cyber-sec`. El PRD las nombra a veces como `emil-kowalski` (= `emil-design-eng`). Son obligatorias para frontend (E6-H1) y para la auditoría post-VoBo.

## Cómo comerse el backlog

- **Jerarquía del PRD**: Épica → Historia → Tarea → Subtarea. Se avanza en ese orden: cada historia indica sus dependencias; no se arranca nada cuyas dependencias no estén cerradas (orden canónico: E0→E1→E2→E3→E4→E5→E7; E6 puede ir en paralelo a E3 con datos simulados contra el contrato de API y se integra al cerrar E5).
- **Compuertas**: E3-H1 es compuerta — nada posterior de E3 arranca sin ADR-003 firmado. Antes de E2 debe existir el subset ingerido (E1-H3).
- **Incremento = subtarea** (o pedazo de ella). Cada subtarea del PRD trae su **archivo objetivo** y su **verificación ejecutable**. Regla: una subtarea sin verificación ejecutada no está terminada. Si una subtarea es L/XL o tomaría más de ~1 bloque corto, se parte en pedacitos cada uno verificable por separado (nunca se parte eliminando la verificación).
- **RF y criterios de aceptación**: los RF citados en cada historia y sus escenarios Gherkin son la especificación; las pruebas de la historia se escriben contra ellos. Antes de desarrollar, leer la historia completa (criterios + tareas) para no programar contra supuestos.
- **DoD-G** (aplica a toda historia, ver PRD §12.1): código formateado sin warnings, pruebas nuevas en verde cubriendo criterios, verificación de cada subtarea ejecutada con salida esperada, sin secretos/rutas de máquina, docs tocadas si cambian contratos o comandos, y `make verify` no roto.
- **Estimaciones**: S ≤1h · M 1-3h · L 3-6h · XL >6h. XL es candidata a división antes de empezar.

## Checkpoints de frontend (Google Stitch)

Al llegar a E6-H1 (dirección de diseño y mockups), antes de escribir componentes:

1. El agente redacta los prompts de Google Stitch (uno por pantalla: tablero, explorador, chat) y los copia al clipboard con `pbcopy`, uno a la vez, para que el usuario los pegue.
2. **Se espera al usuario**: no se avanza hasta recibir los mockups y el `DESIGN.md`.
3. El usuario devuelve: mockups (a `docs/mockups/`) y `DESIGN.md` (= `docs/design-direction.md` del PRD: paleta 4-6 hex nombrados, tipografía con roles, layout, elemento distintivo).
4. Con eso, el agente implementa el armazón (tokens Tailwind, AppShell, estados) siguiendo `.agents/skills/{emil-design-eng,impeccable,design-taste-frontend}` y el mapeo componente↔mockup.

## Flujo de desarrollo (sin excepción)

1. **Leer `HEARTBEAT.md`** (raíz) para saber el estado y el próximo incremento.
2. Desarrollar el componente atómico (una subtarea del PRD, con su archivo objetivo).
3. Ejecutar la verificación ejecutable de la subtarea + pruebas según aplique (unitarias, integración, e2e, Playwright, Chrome DevTools MCP).
4. Guardar evidencia en `docs/evidence/<incremento>/` (ver sección Evidencia).
5. **Pedir VoBo al usuario** — esperar confirmación explícita en chat. No continuar sin ella.
6. Con VoBo: auditoría cyber-sec (skill en `.agents/skills/cyber-sec/SKILL.md`) → remediar hallazgos → reporte en `docs/evidence/<incremento>/SECURITY-AUDIT.md`.
7. **Actualizar `HEARTBEAT.md`** con lo hecho y lo que sigue.
8. Commit (conventional commits, descripción en español, estilo del historial: `chore: initial commit...`).
9. **Verificación post-commit**: `git status --porcelain` debe quedar vacío. Si queda algún archivo `M`/`??` sin commitear, el commit está mal: corregirlo antes de continuar.

## Reglas duras

- **Prohibido el comando `sleep`** en cualquier contexto. Para esperar: `--wait`, timeouts propios de la herramienta, polling condicional sin sleep, o seguir con otra tarea.
- **Prohibido salir de la raíz del repositorio**: todo comando Bash se ejecuta con el parámetro `workdir` apuntando a una carpeta dentro de la raíz (`REPO_ROOT`). Prohibido `cd` en los comandos, rutas absolutas fuera del repo, `~`, `../` que escape de la raíz, y referencias a `/tmp` u otras carpetas externas. Cualquier verificación o auditoría (p. ej. `uv pip audit`, `pnpm audit`) se corre por módulo con `workdir=<módulo>` y sobre el venv/lock de ese módulo — jamás sobre el `.venv/` raíz (scratch), entornos globales del sistema ni cualquier recurso fuera del repo.
- **`git add` explícito y verificado**: nunca silenciar errores de `git add` (`2>/dev/null`). Stagear cada archivo/ruta por su nombre real y comprobar `git status --porcelain` antes de commitear para confirmar que todo lo esperado está en el index y nada quedó fuera.
- **HEARTBEAT.md**: se lee antes de desarrollar y se actualiza antes de cada commit. Sin excepción.
- **Comunicación mínima**: reportes al grano, sin preámbulos ni postales. Reportar: qué se hizo, verificación, resultado. 
- No commit sin VoBo + cybersec + HEARTBEAT actualizado.
- Datos StatsBomb: no versionar en git (van a `data/`), atribución StatsBomb/Hudl en pie de pantalla y README (licencia no comercial).
- Sin secretos ni valores de máquina en código; `.env` ignorado, usar `.env.example`.

## Estructura y stack

Módulos (PRD §11): `backend/` (Go hexagonal: domain → application → adapter, test de arquitectura rompe el build si domain importa adapter), `data-platform/` (Python: contratos Pydantic, runner DAG, modelos bronze/silver/gold en SQL+YAML), `ai-sidecar/` (Python: FastAPI, capa semántica YAML, compilador, guardas, agente ADK), `frontend/` (React 19 + Vite + Tailwind + shadcn/ui + TanStack Query).

- **Variables de entorno se gestionan con `direnv`**
- **Python se gestiona con `uv`** (Python 3.12, `pyproject.toml` + `uv.lock` por módulo). El `.venv/` de la raíz es Python 3.13 y es scratch: no usarlo para los módulos.
- Nada consulta gold directamente: todo pasa por la capa semántica (`ai-sidecar/semantic/*.yaml`).
- Lakehouse `lakehouse/{bronze,silver,gold}/` en Parquet, DuckDB solo lectura, `LIMIT` forzado, allow-list desde catálogo.
- Ollama es externo en platypy (`ssh platypy`; modelo local ≤ 8 GB VRAM, `temperature=0`). E0-H3 fija el tag exacto en ADR-002.
- Postgres 17 + pgvector en compose; migraciones con golang-migrate en `data-platform/migrations/`.

## Comandos (Makefile raíz)

Pipeline: `make data-pull SCOPE=subset|full` → `ingest` → `bronze` → `silver` → `gold` → `serve`; `make eval`, `make demo`, `make report`, `make lineage`, `make model MODEL=fct_shot`, `make migrate-up|migrate-down`, `make ingest-report`, `make ingest-360`, `make verify` (lint+test de los 4 módulos), `make bootstrap`, `make clean`.

Compose (requerido, `infra/docker-compose.yml` con servicios `app`, `ai-sidecar`, `postgres` y healthchecks):
- `make up` — levanta todo (equivalente a `docker compose up -d`)
- `make down` — mata todo
- `make restart` — `docker compose restart`
- `make logs [SERVICE=]` — `docker compose logs -f`
- `make ps` — estado de contenedores

Verificaciones rápidas: `go test ./...` (backend), `uv run pytest` (data-platform, ai-sidecar), `pnpm test` (frontend), `pnpm build`. Contratos: `uv run python -m genbi_data.contracts` / validación al arranque del runner y sidecar.

## Evidencia (auditable, obligatoria)

Cada incremento deja `docs/evidence/<incremento>/` (p. ej. `docs/evidence/E2-H1/`):

- `RESULTADOS.md` — qué se probó, comandos ejecutados, salida relevante, estado.
- **Frontend**: GIFs que demuestren la funcionalidad. Playwright graba `.webm`; convertir con ffmpeg (`ffmpeg -i in.webm -vf "fps=10,scale=900:-1" out.gif`). Vale también screenshots clave.
- **Backend/data**: transcripción comando + salida (exit code, conteos, reportes JSON).
- `SECURITY-AUDIT.md` — reporte cyber-sec con matriz de severidad y remediación.

## Ciberseguridad (post-VoBo)

Usar la skill `.agents/skills/cyber-sec/SKILL.md` (auditor SAST/SCA/secretos). Sus rutas `system-heartbeat/` no aplican aquí: el reporte va a `docs/evidence/<incremento>/SECURITY-AUDIT.md`. Hallazgos CRITICAL/HIGH bloquean el commit hasta remediar o documentar la aceptación. Chequear: secretos en código, inyección SQL en guardas, XSS en renderizado, dependencias vulnerables.
