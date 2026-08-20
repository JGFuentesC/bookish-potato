# E0-H1 — Evidencia de incrementos

## E0-H1-T1 — Árbol de directorios y .gitignore ✅ (commit c5ae2e7)

### Qué se probó

Creación del árbol de directorios de la sección 11 del PRD y actualización del `.gitignore` (E0-H1-T1.1 y T1.2).

### Comandos ejecutados

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

### Salida relevante

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

---

## E0-H1-T2 — Skills de diseño versionadas ✅ (pendiente commit)

### Qué se probó

Versionar las skills de diseño obligatorias (E0-H1-T2.1 y T2.2). El contenido ya vivía versionado en `.agents/skills/` (commit `e54bb80`); T2 crea los puntos de entrada que PRD §11 y E6-H1 referencian bajo `.claude/skills/`.

### Comandos ejecutados

```
mkdir -p .claude/skills
ln -s ../../.agents/skills/emil-design-eng       .claude/skills/emil-kowalski
ln -s ../../.agents/skills/impeccable            .claude/skills/impeccable
ln -s ../../.agents/skills/design-taste-frontend .claude/skills/design-taste-frontend
git add .claude
```

### Salida relevante

T2.1 — los tres `SKILL.md` existen bajo `.claude/skills/`:

```
.claude/skills/design-taste-frontend/SKILL.md   (87 KB)
.claude/skills/emil-kowalski/SKILL.md           (27 KB)  → emil-design-eng
.claude/skills/impeccable/SKILL.md              (21 KB)
```

T2.2 — versionadas en git:

```
git ls-files .claude/skills | wc -l  →  3
git ls-files -s .claude/skills       →  120000 (symlinks, modo git 120000)
```

Los symlinks apuntan a contenido ya versionado en `.agents/skills/`, evitando duplicación. `emil-kowalski` ↔ `emil-design-eng` (alias según AGENTS.md).

---

## Estado general

- [x] E0-H1-T1.1 — árbol de directorios creado y versionado
- [x] E0-H1-T1.2 — `.gitignore` cubre `data/`, `lakehouse/`, `node_modules/`, `.venv/`, `dist/`, `*.duckdb`
- [x] E0-H1-T2.1 — tres `SKILL.md` bajo `.claude/skills/`
- [x] E0-H1-T2.2 — `git ls-files .claude/skills | wc -l` = 3 > 0