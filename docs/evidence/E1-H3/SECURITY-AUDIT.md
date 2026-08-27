# SECURITY-AUDIT — E1-H3

Auditoría post-VoBo del incremento E1-H3 (cargador a OLTP). Alcance: código nuevo/modificado
de `data-platform/src/genbi_data/ingest/`, migraciones, scripts y `Makefile`.

## Superficie revisada

- `data-platform/src/genbi_data/ingest/{loader,orchestrate,flatten,report,__main__}.py`
- `data-platform/scripts/derive_catalogs.py`
- `data-platform/migrations/0001_catalogs.{up,seed}.sql`
- `Makefile` (targets `ingest`, `ingest-report`)

## Escaneo de secretos

Patrones buscados (API keys, claves privadas, tokens, password/secret hardcoded) en archivos
modificados. Resultado: **sin secretos**. El único match es la construcción del DSN en
`__main__.py` desde `os.getenv(...)` (variables de entorno), sin valores embebidos.

## SCA (dependencias)

| Módulo | Herramienta | Resultado |
|---|---|---|
| data-platform | `pip-audit` | Sin vulnerabilidades conocidas |
| ai-sidecar | `pip-audit` | Sin vulnerabilidades conocidas |
| frontend | `pnpm audit` | Sin vulnerabilidades conocidas |
| backend | `govulncheck` | 5 vulnerabilidades stdlib Go (ver abajo) |

## SAST (inyección SQL)

- Todo acceso a Postgres usa `psycopg` con parámetros (`%s`) o `COPY ... FROM STDIN` con
  valores escapados vía `_copy_val` (nulos `\N`, UUID/booleano normalizados). Sin
  concatenación de valores de usuario en SQL.
- Los nombres de tabla/columna interpolados provienen de constantes internas
  (`SUBTYPE_COLUMNS`, `SUBTYPE_TABLE_MAP`), no de entrada externa.
- `_ensure_catalog` interpola `table/id_col/name_col` de un mapa de constantes de catálogo
  (hardcoded), no de datos crudos.

## Hallazgos

| # | Severidad | Hallazgo | Remediación |
|---|---|---|---|
| 1 | MEDIUM | `govulncheck` reporta 5 CVEs en la **stdlib de Go 1.26.5** (net/http, net/url, crypto/tls, encoding/asn1), corregidos en **go1.26.6**. Afecta a `cmd/server/main.go` (healthcheck usa `http.Client.Get`). | Actualizar toolchain Go a 1.26.6 en CI/imagen. No relacionado con E1-H3 (código backend no tocado). Aceptado para este incremento; registrado para corregir en E5. |
| 2 | LOW | `genbi-data`/`genbi-ai` no están en PyPI, por lo que `pip-audit` no los audita (skip). | Paquetes locales; sin riesgo. |
| 3 | LOW | `PGPASSWORD` visible en variables de entorno del Makefile/docker run (dev local). | Ya aceptado en E1-H1; re-evaluar en CI. |

## Veredicto

**Security Clearance** — sin hallazgos CRITICAL/HIGH. El único MEDIUM es una vulnerabilidad
de stdlib Go preexistente (no tocada por este incremento) con corrección disponible en un
patch release, aplazada a E5.
