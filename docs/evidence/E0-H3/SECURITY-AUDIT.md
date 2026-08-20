# SECURITY-AUDIT — E0-H3 (verificación del modelo local, ADR-002)

Auditoría post-VoBo (skill cyber-sec adaptada: el reporte vive aquí, no en `system-heartbeat/`). Alcance: `scripts/bench_model.py`, `scripts/prompt_catalogo.txt`, `docs/adr/ADR-002-local-model-selection.md`, ediciones a ADR-001, `.env.example`, `README.md`, `docs/evidence/E0-H3/`.

## Superficie de ataque

- `scripts/bench_model.py`: cliente HTTP (stdlib `urllib`) contra el Ollama remoto de platypy; escribe JSON local.
- `prompt_catalogo.txt`: texto estático.
- `.env.example`: plantilla, sin secretos reales.
- Docs: ADR-001/002, README, evidencia.

## Resultados

### Secretos / hardcoding

- Escaneo de patrones (API keys, tokens, passwords, claves privadas) sobre los archivos del incremento: **sin hallazgos**. Los matches de `tokens/s`, `token` y `seed` son métricas de benchmark, no credenciales.
- `.env.example` solo añade `OLLAMA_LLM_MODEL` y `OLLAMA_EMBEDDINGS_MODEL` (identificadores de modelo, no secretos). No se versiona ningún `.env` ni `.envrc.local`.

### SAST

- **Go**: sin cambios en este incremento.
- **Python (`bench_model.py`)**: sin `subprocess`/`os.system` → sin inyección de comandos. Sin SQL → sin inyección SQL. No interpola entradas del usuario en prompts: `--prompt`/`--prompt-file` se envían tal cual al modelo (herramienta de benchmark de operación manual, no un servicio expuesto). Sin XSS (no hay renderizado web).
- **React**: sin cambios en este incremento.

### SCA

- No se añadieron dependencias: `bench_model.py` usa solo stdlib (`urllib`, `statistics`, `argparse`, `json`, `time`). Backend Go, ai-sidecar y frontend no tocaron sus lockfiles. `make verify` (lint+test de los 4 módulos) verde.

## Matriz de severidad

| Severidad | Hallazgo | Estado |
|---|---|---|
| CRITICAL | — | — |
| HIGH | — | — |
| MEDIUM | — | — |
| LOW | `bench_model.py` acepta `--host` arbitrario (SSRF potencial si se usara como servicio; hoy es una herramienta local de benchmark) | Aceptado: herramienta de operación, no se expone |

## Remediación

- LOW: documentado como aceptado. Si en el futuro `bench_model.py` se promueve a servicio, validar el host contra una allow-list y no aceptar destinos del operador sin control.

## Veredicto

**Security Clearance otorgado.** Sin hallazgos CRITICAL/HIGH que bloqueen el commit.