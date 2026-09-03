# SECURITY-AUDIT — E2-H1 (Gold POC)

Auditoría post-VoBo del incremento E2-H1 (runner de modelos + vista gold +
endpoint de consulta semántica). Alcance: código nuevo en
`data-platform/src/genbi_data/{runner,quality}`, `data-platform/models/gold/*`,
`data-platform/scripts/gen_catalog.py`, `ai-sidecar/src/genbi_ai/{api/query.py,
semantic/catalog.py}`, `ai-sidecar/semantic/catalog.yaml`, cambios en
`Makefile`, `infra/docker-compose.yml`, `infra/Dockerfile.sidecar`.

## Resumen

- Total hallazgos: 2
- Critical: 0 · High: 0 · Medium: 1 · Low: 1 · Info: 0
- 1 MEDIUM corregido en este incremento (verificado por test + HTTP).

## Matriz de hallazgos

| # | Severidad | Categoría | Hallazgo | Estado |
|---|-----------|-----------|----------|--------|
| 1 | MEDIUM | A03 Inyección | Tabla-función DuckDB (`read_parquet`/`read_csv`/`glob`) evadía la allow-list del endpoint y permitía leer archivos arbitrarios del contenedor | **Corregido** |
| 2 | LOW | A05 Config | Endpoint `/api/v1/query` sin autenticación (POC, red local) | Aceptado |

---

### [MEDIUM] A03: Tabla-función DuckDB evade allow-list (lectura de archivos)
**Archivo:** `ai-sidecar/src/genbi_ai/api/query.py` (`validate_sql`)
**CWE:** CWE-98 (Improper Control of Filename for Include/Require) / CWE-706

**Descripción:** La validación solo inspeccionaba nodos `exp.Table` del AST
(`find_all`). Una consulta como `SELECT * FROM read_parquet('/etc/passwd')`
se parsea como tabla-función (`ReadParquet`), no como `Table`, y pasaba la
allow-list; en el contenedor (mount del lakehouse `:ro`) el atacante podía
enumerar archivos y volcar su contenido vía el endpoint sin autenticación.

**Código vulnerable:**
```python
for table in stmt.find_all(sqlglot.exp.Table):
    if table.name not in catalog.table_names:
        raise HTTPException(...)
```

**Remediación:** rechazar tablas-función (parsean como `Table` de nombre vacío):
```python
for table in stmt.find_all(sqlglot.exp.Table):
    if not table.name:
        raise HTTPException(status_code=400, detail="tabla-función no permitida")
    if table.name not in catalog.table_names:
        raise HTTPException(status_code=400, detail=f"tabla no permitida: {table.name}")
```

**Verificación:** test `test_validate_rejects_table_functions` (3 payloads) +
HTTP real:
```sh
curl -X POST localhost:8000/api/v1/query -d '{"sql":"SELECT * FROM read_parquet('\''/etc/passwd'\'')"}'
# -> {"detail":"tabla-función no permitida"}
```

---

### [LOW] A05: Endpoint sin autenticación
**Archivo:** `ai-sidecar/src/genbi_ai/api/query.py`
**CWE:** CWE-306 (Missing Authentication for Critical Function)

**Descripción:** `/api/v1/query` es un POST abierto que ejecuta SQL sobre el
lakehouse gold.

**Por qué se acepta:**
- **No aplica corrección**: es una herramienta de POC de una sola persona; no
  hay usuarios externos ni datos sensibles en gold (datos públicos StatsBomb).
  El PRD no define autenticación para el sidecar en E3.
- **Controles compensatorios**: solo SELECT + allow-list de 6 tablas + LIMIT
  forzado + timeout; el contenedor no monta secretos y el lakehouse va `:ro`;
  el servicio solo escucha en la red local del host (puerto 8000).
- **Re-evaluación**: se exige autenticación (API key o similar) cuando el
  sidecar se exponga fuera del host, se agreguen datos no públicos o haya más
  de un usuario. Queda anotado para E6/E7 (integración con el frontend).

---

## Ítems revisados y limpios

- **Secretos (A02)**: `rg` de claves/prefijos conocidos (`sk-`, `AKIA`, `ghp_`,
  `password=` etc.) sobre archivos nuevos → sin hallazgos. El DSN de Postgres
  se construye desde variables de entorno y nunca se loguea.
- **Inyección SQL clásica (A03)**: el runner materializa SQL de modelos
  versionados (fuente de confianza) con `CREATE TABLE ... AS` sin interpolación
  de input de usuario. El endpoint valida/reescribe con sqlglot y solo ejecuta
  sobre vistas de Parquet permitidas.
- **SSRF (A10)**: el endpoint no hace peticiones HTTP; OLLAMA_BASE_URL es fija
  por config y no acepta URL de usuario en este incremento.
- **Logging (A09)**: no se registran sentencias SQL ni credenciales; solo
  conteos y nombres de modelo.
- **SCA (A06)**: dependencias sin cambios en este incremento (fastapi, duckdb,
  sqlglot, pydantic ya presentes y auditar en CI; `uv audit` pendiente de CI).
- **XSS (A03)**: sin renderizado HTML en este incremento.