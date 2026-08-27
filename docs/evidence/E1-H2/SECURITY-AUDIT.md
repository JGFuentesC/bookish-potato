# E1-H2 — SECURITY-AUDIT

Incremento: E1-H2 (contratos Pydantic + descarga + cuarentena) · Fecha: 2026-08-26
Alcance: `data-platform` (contracts/, ingest/{fetch,quarantine}, pyproject, Makefile `data-pull`, config/subset.yaml).

## Superficie de ataque

Módulo de datos Python de ingesta StatsBomb: contratos Pydantic estrictos, descarga
HTTP a URL pública fija (hudl/open-data), cuarentena de registros inválidos.
No se tocaron backend Go, ai-sidecar, frontend ni IaC (compose).

## 1. Secretos / hardcoding

Barrido recursivo de los archivos modificados buscando API keys, tokens, contraseñas,
claves (AKIA*, sk-*, BEGIN PRIVATE KEY, eyJ JWT). **Sin hallazgos.**

## 2. IaC (Terraform/Cloud Run)

No aplica a este incremento (no hay `.tf`/GCP; compose no se modificó).

## 3. SCA — dependencias

`uv audit` sobre el venv del módulo data-platform: `27 paquetes resueltos, sin vulnerabilidades
conocidas` (incluye pydantic 2.13.4, pyyaml 6.0.3, types-PyYAML). **Clear.**

## 4. SAST

- `fetch.py`: descarga vía `urllib` hacia base fija públicos del repositorio `hudl/open-data`;
  sin concatenación de entrada del usuario en la URL (SCOPE lee sólo subset|full sobre lista
  cerrada de entidades). Sin riesgo de inyección.
- `quarantine.py`: la ruta de salida se construye con entidad de lista cerrada
  (`ENTITY_MODEL`) y `file_path.stem`; `PurePath.stem` no puede contener separadores de
  directorio. `error_path`/`error_type` se derivan de `ValidationError` (datos controlados por
  el validado) y se serializan con `json.dumps`; sin inyección.
- Contratos (`extra='forbid'`): cualquier campo no declarado cae en cuarentena — superficie
  de tipeo estricto.
- Sin uso de IA, SQL ni renderizado dinámico en este módulo.

## Matriz de severidad

| ID | Severidad | Hallazgo | Estado |
|----|-----------|----------|--------|
| S1 | LOW | Ruta de cuarentena derivada del nombre de archivo de origen | **Aceptado** |
| S2 | LOW | Descarga por HTTP(S) público no autenticado | **Aceptado** |

- S1: herramienta de desarrollo local; entidad permitida en allow-list y `stem` sin
  separadores → sin traversal. No bloquea.
- S2: dataset público Open Data (licencia no comercial, atribución StatsBomb/Hudl);
  el repositorio fuente es de confianza. Re-evaluar integridad con la verificación por
  SHA-256 registrada en `manifest.json` (ya implementada en `fetch.py`).

## Veredicto

**SECURITY CLEARANCE** — sin hallazgos CRITICAL/HIGH; 2 LOW aceptados y documentados.