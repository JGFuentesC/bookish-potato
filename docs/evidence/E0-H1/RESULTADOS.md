# E0-H1-T1 — Árbol de directorios y .gitignore

## Qué se probó

Creación del árbol de directorios de la sección 11 del PRD y actualización del `.gitignore` (E0-H1-T1.1 y T1.2).

## Comandos ejecutados

```
mkdir -p docs/adr docs/mockups docs/evidence config \
  data-platform/src/genbi_data/{contracts,ingest,runner,quality} \
  data-platform/models/{bronze,silver,gold} data-platform/migrations data-platform/tests \
  ai-sidecar/src/genbi_ai/{agent,semantic,compiler,guard,linking,eval,api} \
  ai-sidecar/semantic ai-sidecar/tests \
  backend/cmd/server backend/internal/{domain,application,adapter} backend/tests \
  frontend/src/{app,components,features,lib} frontend/tests \
  infra scripts
```

Se añadió `.gitkeep` a las 33 carpetas vacías para versionarlas.

## Salida relevante

`find . -type d` (excluyendo `.git`, `.venv`, `.agents`) muestra todos los directorios de la sección 11:

- `ai-sidecar/{semantic, src/genbi_ai/{agent,api,compiler,eval,guard,linking,semantic}, tests}`
- `backend/{cmd/server, internal/{adapter,application,domain}, tests}`
- `config`, `docs/{adr,evidence,mockups}`, `frontend/src/{app,components,features,lib}`, `frontend/tests`
- `data-platform/{migrations, models/{bronze,silver,gold}, src/genbi_data/{contracts,ingest,quality,runner}, tests}`
- `infra`, `scripts`

`.gitignore` verificado con `git check-ignore`:

```
lakehouse/gold/x.parquet    → ignorado
node_modules/react/index.js → ignorado
foo.duckdb                  → ignorado
data/raw/data/competitions.json → ignorado
```

## Estado

- [x] E0-H1-T1.1 — árbol de directorios creado y versionado
- [x] E0-H1-T1.2 — `.gitignore` cubre `data/`, `lakehouse/`, `node_modules/`, `.venv/`, `dist/`, `*.duckdb`
- [x] `git status --porcelain` limpio salvo por archivos nuevos/`.gitignore` modificado (correcto: aún sin commit)

Pendiente de VoBo del usuario.