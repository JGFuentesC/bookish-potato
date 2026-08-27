# SECURITY-AUDIT — E1-H4

Auditoría post-VoBo del incremento E1-H4 (carga completa + persistencia). Alcance: cambios
en `data-platform` (contratos `match.py`/`lineup.py`, `ingest/{fetch,flatten,loader,orchestrate}.py`,
`tests/test_contracts.py`), migraciones `0001_catalogs.{up,seed}.sql` y `scripts/derive_catalogs.py`.

## Escaneo de secretos

Patrones (API keys, claves privadas, tokens, password/secret hardcoded) en archivos modificados.
Resultado: **sin secretos**. El DSN en `ingest/__main__.py` y `report.py` sigue construyéndose desde
`os.getenv(...)`, sin valores embebidos.

## SCA (dependencias)

| Módulo | Herramienta | Resultado |
|---|---|---|
| data-platform | `pip-audit` | Sin vulnerabilidades conocidas |
| frontend | `pnpm audit` | Sin vulnerabilidades (verificado en E1-H3) |
| backend | `govulncheck` | 5 CVEs stdlib Go 1.26.5→1.26.6 (preexistente, sin cambios en E1-H4) |

## SAST

- **Contratos Pydantic**: relajar `managers`/`kick_off`/`country` a opcionales no introduce
  riesgo; sigue usando `extra="forbid"` (un campo desconocido sigue rechazando el registro).
- **`_git_sync` (fetch.py)**: clona a `raw_root.tmp` y hace `rename` atómico; el `git clone`
  usa `--depth 1` de una URL fija (`hudl/open-data`), sin inyección de comandos (URL hardcoded).
- **`_ensure_country`**: sigue usando consultas parametrizadas (`%s`); el nuevo mapeo de regiones
  (`_REGION_COUNTRY_IDS`) es un dict estático de constantes, no entrada externa.
- **`extract_event_extras`**: el filtro `inserted_ids` elimina `related_event_id` huérfanos
  (integridad referencial), sin concatenación SQL.

## Hallazgos

| # | Severidad | Hallazgo | Remediación |
|---|---|---|---|
| 1 | MEDIUM | `govulncheck`: 5 CVEs stdlib Go 1.26.5 (net/http, net/url, crypto/tls, encoding/asn1), corregidos en go1.26.6. Afecta a `cmd/server/main.go`. | Preexistente; no relacionado con E1-H4. Actualizar toolchain a 1.26.6 en CI/imagen (E5). Aceptado. |
| 2 | LOW | `genbi-data` no está en PyPI → `pip-audit` no lo audita (skip). | Paquete local, sin riesgo. |
| 3 | LOW | `PGPASSWORD` visible en entorno dev (Makefile/docker run). | Ya aceptado en E1-H1; re-evaluar en CI. |

## Veredicto

**Security Clearance** — sin hallazgos CRITICAL/HIGH. El MEDIUM es una vulnerabilidad de stdlib
Go preexistente (no tocada por E1-H4) con corrección en patch release, aplazada a E5.
