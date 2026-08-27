# E1-H3 — Cargador paralelo e idempotente a OLTP

## Qué se probó

Carga del subset StatsBomb (La Liga 2020/21 `11/90` + 2019/20 `11/42`, 68 partidos)
desde `data/raw/data/` al esquema OLTP (`oltp.*`), con idempotencia por SHA-256,
auditoría en `ingestion_run`/`ingestion_file` y aplanado de eventos (base + subtipos +
relation/freeze/tactics).

## Comandos ejecutados

```bash
# 1. Reset + migraciones (semilla derivada de datos crudos)
docker compose -f infra/docker-compose.yml exec postgres psql -U genbi -d genbi \
  -c "DROP SCHEMA oltp CASCADE; DROP TABLE IF EXISTS schema_migrations;"
make migrate-up

# 2. Ingesta
PGHOST=localhost PGPORT=5433 PGUSER=genbi PGDATABASE=genbi PGPASSWORD=****** \
  make ingest SCOPE=subset
```

## Salida (1ª corrida)

```
ingest subset: archivos=139 partidos=68 eventos=268088 alineaciones=136 omitidos=0 duración=16.2s
```

`ingestion_run.status = success`, `files_processed = 139`, `rows_written = 268292`.

## Conteos finales en OLTP

| Tabla | Filas |
|---|---|
| `oltp.event` | 268 088 |
| `oltp.match` | 68 |
| `oltp.match_player` | 2 823 |
| `oltp.player` | 700 |
| `oltp.country` | 64 |
| `oltp.competition` | 1 (La Liga, subset) |
| `oltp.event_pass` | 77 494 |
| `oltp.event_shot` | 1 591 |
| `oltp.event_relation` | 394 540 |
| `oltp.shot_freeze_frame` | 22 237 |
| `oltp.tactics_lineup` | 277 |
| `oltp.tactics_player` | 3 047 |

## Verificaciones ejecutables

- **Carga del subset**: 139/139 archivos `ok`, 0 errores. `status=success`.
- **Idempotencia** (2ª corrida): `archivos=0 ... omitidos=139 duración=0.3s`;
  `count(oltp.event)` permanece **268 088** (sin cambios); `event_relation` y
  `shot_freeze_frame` también idénticos (394 540 / 22 237).
- **T2.2 integridad de `related_event_id`**: 0 huérfanos
  (`NOT EXISTS` sobre `oltp.event` → 0).
- **T2.3 conteos coinciden con JSON**: `event_relation`/`shot_freeze_frame`/`tactics_*`
  pobladas.
- **Semilla derivada**: `oltp.country` = 64 países con IDs naturales StatsBomb
  (3–249), sin colisiones `MAX+1`.
- **Subset filtrado**: `oltp.competition` = 1 (solo La Liga), regiones irrelevantes
  (Africa/Europe/…) excluidas.
- `make verify` verde: ruff+go vet+go test+pnpm lint+pnpm test+pytest
  (data-platform **37 passed**, ai-sidecar **2 passed**).
- `make ingest-report` imprime corridas, archivos y totales.

## Estado

COMPLETO.
