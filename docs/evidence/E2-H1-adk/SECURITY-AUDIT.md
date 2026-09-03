# SECURITY-AUDIT — ADK demo (agente genbi_futbol)

Auditoría del incremento ADK: `ai-sidecar/adk_agent/agent.py`, `.env`,
`docs/evidence/E2-H1-adk/`. No se tocó el sidecar de producción ni gold salvo
el fix de columnas en `fct_shot`/`fct_pass` (SQL YAML, sin superficie de
seguridad nueva).

## Resumen

- Total hallazgos: 2
- Critical: 0 · High: 0 · Medium: 0 · Low: 2 · Info: 0
- Todos LOW, aceptados (herramienta de desarrollo local POC).

## Matriz

| # | Severidad | Categoría | Hallazgo | Estado |
|---|-----------|-----------|----------|--------|
| 1 | LOW | A01/A05 | El agente expone el endpoint gold sin autenticación (heredado del sidecar) | Aceptado |
| 2 | LOW | A09 | El agente puede generar SQL arbitraria en la tool (pero el sidecar la valida) | Aceptado |

---

### [LOW] A01: Endpoint gold accesible sin auth (heredado)
**Archivo:** `ai-sidecar/adk_agent/agent.py` (tool `query_gold`)
**CWE:** CWE-306

**Descripción:** La tool delega en `POST {SIDECAR_URL}/api/v1/query`, endpoint
sin autenticación. Ya auditado en E2-H1 (LOW aceptado).

**Por qué se acepta:** POC de un solo usuario, red local; el sidecar ya limita
a SELECT + allow-list de 6 tablas + LIMIT + timeout; no monta secretos.

---

### [LOW] A09: Tool ejecuta SQL proveniente del LLM
**Archivo:** `ai-sidecar/adk_agent/agent.py`
**CWE:** CWE-943

**Descripción:** `query_gold` recibe SQL generada por el modelo y la envía al
endpoint. El LLM puede generar consultas ineficientes.

**Por qué se acepta:** el endpoint valida solo-SELECT + tablas permitidas +
LIMIT forzado + timeout; el input no llega a SQL crudo sin barrera. El riesgo
residual es solo de rendimiento (consulta pesada), mitigado por el timeout.
Re-evaluar si el agente se expone a usuarios no confiables.

---

## Ítems revisados y limpios

- **Secretos (A02):** sin claves en `agent.py`/`.env` (`OLLAMA_API_BASE` local,
  sin credenciales). `rg` de patrones de clave → limpio.
- **Inyección (A03):** no hay interpolación de SQL en el código del agente; toda
  SQL pasa por la validación del sidecar (sqlglot, allow-list, tabla-función
  bloqueada).
- **SSRF (A10):** `SIDECAR_URL` y `OLLAMA_API_BASE` son fijos de entorno; el
  agente no acepta URLs de usuario.
- **XSS:** el agente no renderiza HTML; `report.html` es estático generado desde
  datos propios (los SQL/respuestas se escapan por construcción al ser texto
  embebido en `<code>`; el HTML lo genera el script local, no el agente).