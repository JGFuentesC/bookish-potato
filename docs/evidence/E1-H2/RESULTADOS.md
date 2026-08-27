# E1-H2 — Contratos Pydantic y descarga del dataset

Fecha: 2026-08-26 · Incremento: E1-H2 (PRD §E1-H2) · Estado: **implementado, pendiente VoBo**

## Qué se probó

Subset: La Liga (`competition_id=11`), temporadas 2020/21 (`90`) y 2019/20 (`42`)
⎼ 68 partidos descargados a `data/raw/` y validados al 100%.

### T1 — Contratos Pydantic (`contracts/statsbomb/`)

- T1.1 `competition.py`, `match.py`, `lineup.py`: validan las muestras reales sin error.
- T1.2 `event.py`: modelo base + unión discriminada por `type.id` para los 18 subtipos
  (Pass, Ball Receipt, Carry, Duel, Ball Recovery, Clearance, Shot, Goal Keeper,
  Foul Committed, Foul Won, Miscontrol, Block, Dribble, Bad Behaviour, Interception,
  Substitution, Injury Stoppage, 50/50). Prueba parametrizada por subtipo con muestra real.
- T1.3 `three_sixty.py`: valida una muestra con `visible_area` y `freeze_frame`.
- T1.4 `ConfigDict(extra='forbid')` en toda la capa + `populate_by_name`: un campo
  desconocido produce `ValidationError` tipado, no silencio.

### T2 — Descarga (`ingest/fetch.py` + `make data-pull`)

- T2.1 `fetch.py` descarga a `data/raw/` (vía raw de `hudl/open-data`). SCOPE=subset|full.
- T2.2 lee `config/subset.yaml`; el conteo de eventos coincide con los partidos declarados
  (68 partidos → 68 `events/`, 68 `lineups/`, 35 `three-sixty/`; los 33 sin datos 360 se
  omiten como 404 sin romper el lote).
- T2.3 SHA-256 por archivo registrado en `data/raw/manifest.json` (174 archivos); reejecutar
  no vuelve a descargar (2ª pasada: `descargado=0 cacheado=175 omitido=33`).

### T3 — Cuarentena (`ingest/quarentine.py`)

- Escribe `data/quarantine/{entity}/{file}.jsonl` con `error_path`, `error_type`,
  `raw_record`. Verificado con test que corrompe una muestra (campo desconocido).

## Comandos y salida relevante

### Validación 100% del subset (DoD)
```
competitions ok=80    fail=0  ✔
match        ok=68    fail=0  ✔
lineup       ok=136   fail=0  ✔
three-sixty  ok=128840 fail=0 ✔
event        ok=268088 fail=0 ✔
```

### Descarga (1ª y 2ª pasada — idempotente)
```
$ uv run python -m genbi_data.ingest.fetch --scope subset --workers 8
data-pull subset: descargado=174 cacheado=1 omitido=33
$ uv run python -m genbi_data.ingest.fetch --scope subset --workers 8
data-pull subset: descargado=0 cacheado=175 omitido=33
```

### Cuarentena sobre el subset (cero cuarentena esperado y obtenido)
```
quarantine events:  ok=268088 cuarentena=0
quarantine matches: ok=68     cuarentena=0
quarantine lineups: ok=136    cuarentena=0
```

### make data-pull (target del Makefile)
```
$ make data-pull              # -> subset
$ make data-pull SCOPE=full   # -> clon del repositorio íntegro
```

### make verify — verde (DoD-G #6)
Lint + test de los 4 módulos: `go vet` OK · `ruff check` OK (data-platform, ai-sidecar) ·
`oxlint` OK · `go test` OK · pytest data-platform **37 passed** (incluye 18 subtipos de
evento, extra_forbid, cuarentena, descarga/idempotencia) · pytest ai-sidecar 2 passed ·
frontend `tsc -b` OK.

## Archivos de la historia

- `config/subset.yaml` — ruta crítica (La Liga 11/90 + 11/42).
- `data-platform/src/genbi_data/contracts/statsbomb/{_common,competition,match,lineup,event,three_sixty}.py`
- `data-platform/src/genbi_data/ingest/{fetch,quarantine}.py`
- `data-platform/src/genbi_data/contracts/__init__.py`, `ingest/__init__.py` (+ subpaquetes)
- `data-platform/pyproject.toml` — build hatchling (era un módulo no instalable), `pyyaml`, `types-PyYAML`
- `data-platform/tests/{conftest,test_contracts,test_event_contract,test_fetch,test_quarantine}.py`
- `Makefile` — target `data-pull` real (SCOPE=subset|full)
- `data-platform/scripts/gen_erd.py` — f-string sin placeholder (bloqueaba `make verify`)

## Notas

- Se corrigió de paso que `genbi_data` no era instalable (sin `[build-system]` ni `packages`);
  ahora es un paquete hatchling editable, necesario para importar contratos.
- `_common.Point` admite 2-3 flotantes (algunos `end_location` llevan coordenada z).
- Los 78911 rechazos iniciales de eventos eran eventos tipo 42 sin `ball_receipt`
  (variedad real del dataset); se ajustó la unión: validar el subtipo presente, no exigirlo.
- Datos StatsBomb (atribución Hudl, uso no comercial) no se versionan (Git ignores `data/`).