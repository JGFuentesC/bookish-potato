# RESULTADOS — E1-H1 Esquema OLTP 3NF y migraciones

Fecha: 2026-08-26 · Estado: **verificado** (pendiente VoBo)

## Qué se construyó

- `make migrate-up` / `make migrate-down` reales (golang-migrate v4.19.1 vía imagen `migrate/migrate:v4.19.1`, red del compose, DSN interno `postgres:5432`). El puerto host de Postgres pasó a `5433` (5432 estaba ocupado por otro Postgres local).
- Migraciones en `data-platform/migrations/` (8 pares up/down):
  - `0001_catalogs`: 15 tablas de referencia + **semilla derivada del dataset real** (StatsBomb open-data, La Liga 2020/21 + Champions 2015/16) por `scripts/derive_catalogs.py`.
  - `0002_master` → `0006_positional`: maestros, match, event, 18 especializaciones, posicionales.
  - `0007_audit`, `0008_pgvector`: auditoría + `CREATE EXTENSION vector` y `semantic_embedding`.
- `scripts/derive_catalogs.py`: deriva catálogos desde `data/raw/data/`.
- `scripts/gen_erd.py`: genera `docs/erd-oltp.md` (Mermaid) desde el esquema real.
- `docs/erd-oltp.md`: ERD con 56 tablas y 94 FKs.

## Verificaciones ejecutadas

| # | Verificación (subtarea) | Comando | Resultado |
|---|---|---|---|
| T1.1 | `\dt oltp.*` lista las 15 tablas | `psql -c '\dt oltp.*'` | 15 filas: body_part, card_type, competition_stage, country, duel_type, event_type, formation, goalkeeper_type, outcome, pass_height, pass_type, play_pattern, position, shot_type, technique |
| T1.2 | `event_type` > 30 | `SELECT count(*) FROM oltp.event_type` | **33** (>30) |
| T1.2 | semilla completa | counts por catálogo | country=1, competition_stage=2, play_pattern=9, position=24, body_part=11, outcome=35, technique=11, pass_height=3, pass_type=7, shot_type=3, duel_type=2, goalkeeper_type=11, card_type=3, formation=10 |
| T2.2 | todas las tablas con PK y FK | `information_schema` | **56 tablas**, **94 FK** |
| T2.3 | prueba negativa de FK | `INSERT INTO oltp.event (event_id, match_id, ...) VALUES (..., 999999999, ...)` | `ERROR: insert or update on table "event" violates foreign key constraint "event_match_id_fkey"` · exit 1 |
| T2.3 | `EXPLAIN` filtro por match_id usa índice | `SET enable_seqscan=off; EXPLAIN SELECT ... WHERE match_id=3773386` | `Bitmap Index Scan on idx_event_match_index` |
| T3.2 | extensión vector | `SELECT extname FROM pg_extension WHERE extname='vector'` | `vector` |
| DoD | ciclo completo | `make migrate-up && make migrate-down && make migrate-up` | 8/u → 8/d → 8/u, exit 0 |
| DoD-G | lint+test 4 módulos | `make verify` | verde (go vet/test, ruff, pytest 2/2, tsc -b) |
| T4.1 | ERD renderiza y cubre todo | `rg` por entidad vs `information_schema` | 56/56 tablas presentes |

## Muestras usadas

Semilla derivada de `data/raw/data/` (StatsBomb open-data, 2026-08-26):
- `competitions.json` (80 competiciones), `matches/11/90.json` (La Liga 2020/21, 35 partidos), `matches/16/27.json` (Champions 2015/16), lineups/events de los 36 partidos, three-sixty de 11.

## Notas

- Postgres host: `localhost:5433` (puerto ajustado por conflicto con 5432 local).
- Datos StatsBomb en `data/` no versionados (licencia no comercial, atribución en README).