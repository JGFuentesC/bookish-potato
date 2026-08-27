# E1-H4 — Carga completa + persistencia del contenedor

## Qué se probó

1. Carga completa del repositorio StatsBomb Open Data (`make data-pull SCOPE=full`,
   clon `--depth 1`, 17 GB) e ingesta a OLTP (`make ingest SCOPE=full`).
2. Persistencia: matar el contenedor (`make down`) y relanzar (`make up`) **no borra**
   los datos (volumen nombrado `pgdata`).

## Comandos ejecutados

```bash
make data-pull SCOPE=full          # clon + indexado SHA-256 (8977 JSON)
# reset + migraciones con semilla derivada del dataset completo
docker compose -f infra/docker-compose.yml exec postgres psql -U genbi -d genbi \
  -c "DROP SCHEMA oltp CASCADE; DROP TABLE IF EXISTS schema_migrations;"
make migrate-up
PGHOST=localhost PGPORT=5433 PGUSER=genbi PGDATABASE=genbi PGPASSWORD=****** \
  make ingest SCOPE=full
```

## Salida

```
data-pull full: descargado=0 cacheado=8977 omitido=0
ingest full: archivos=8551 partidos=4235 eventos=13911057 alineaciones=7922 omitidos=0 duración=1818.7s
```

`ingestion_run.status = success`, `files_processed = 8551`, `rows_written = 13923214`, sin errores.

## Conteos finales en OLTP

| Tabla | Filas |
|---|---|
| `oltp.event` | 13 911 057 |
| `oltp.match` | 3 961 |
| `oltp.player` | 11 794 |
| `oltp.team` | 354 |
| `oltp.competition` | 24 |
| `oltp.country` | 158 (155 naturales + 3 regiones) |
| `oltp.event_relation` | 20 459 984 |
| `oltp.shot_freeze_frame` | 1 305 686 |
| `oltp.tactics_lineup` | 18 787 |

## Verificaciones

- **Carga completa**: 8551/8551 archivos `ok`, 0 errores, `status=success`.
- **Idempotencia** (2ª corrida): `archivos=0 ... omitidos=8551`; `count(oltp.event)`
  permanece 13 911 057.
- **Persistencia del contenedor**: `make down` (elimina contenedores y red) →
  `make up` → conteos intactos (event 13 911 057, match 3 961, relation 20 459 984).
  El volumen `genbi_pgdata` es un *named volume*; `make down` NO usa `-v`.
- **Contratos tolerantes al dataset completo** (E1-H2 se amplía): `managers` y
  `kick_off` opcionales en `Match`, `country` opcional en `PlayerLineup`; un
  `three-sixty` corrupto en origen (bytes NUL) se salta en el test de contratos.
- `make verify` verde (ruff + go vet + go test + pnpm lint + pnpm test + pytest:
  data-platform **37 passed**, ai-sidecar **2 passed**).

## Estado

COMPLETO (persistencia garantizada por named volume `pgdata`).
