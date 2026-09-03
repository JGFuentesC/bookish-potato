# ADK demo — talk-to-your-data (agent genbi_futbol)

Incremento: agente Google ADK 2.0 que responde preguntas en lenguaje natural
sobre la capa gold, usando Ollama local (platypy) como modelo y el endpoint
gold del sidecar como tool de NL2SQL (grounding en Postgres a través del
catálogo semántico).

## Componentes

- `ai-sidecar/adk_agent/agent.py` — `root_agent` (LlmAgent `genbi_futbol`):
  - Modelo: `LiteLlm(model="ollama_chat/gemma4:latest")` (ADR-002), servido por
    Ollama en platypy; acceso vía túnel SSH `localhost:11434`.
  - Tool `query_gold(sql)`: POST a `http://localhost:8000/api/v1/query`
    (sidecar), que valida solo-SELECT + allow-list + LIMIT y ejecuta DuckDB
    sobre `lakehouse/gold/*.parquet` (derivado de Postgres).
  - `instruction` construida desde `ai-sidecar/semantic/catalog.yaml`
    (generado de los contratos gold): esquema + mapeos + reglas de uso.
- `ai-sidecar/adk_agent/.env` — `OLLAMA_API_BASE`, `OLLAMA_LLM_MODEL`,
  `SIDECAR_URL`.
- Corre con `adk web ai-sidecar/adk_agent --port 8001`.

## Fixes de gold durante el demo (importantes)

- `fct_shot`/`fct_pass` no tenían `competition_name` ni `season_name`
  (el modelo fallaba al filtrar por "La Liga": Binder Error). Se añadieron con
  joins a `oltp.competition`/`oltp.season`, se actualizaron los contratos YAML,
  se regeneró el catálogo y se reconstruyeron ambos modelos.
- Verificación tras el fix: `SELECT AVG(xg) FROM fct_shot WHERE
  competition_name='La Liga'` → 0.1110476 (3 ms).

## 8 escenarios probados (adk web + Chrome DevTools MCP)

| # | Pregunta | Respuesta del agente | SQL generado (resumen) |
|---|----------|----------------------|------------------------|
| 1 | ¿Quién es el máximo goleador? | Messi, 508 goles | `COUNT(CASE WHEN is_goal) GROUP BY player` |
| 2 | ¿Promedio de xG por disparo en La Liga? | ~0.111 | `AVG(xg) JOIN dim_match WHERE competition_name LIKE '%La Liga%'` |
| 3 | ¿Cuántos pases completó Messi? | 33,031 | `COUNT(*) fct_pass WHERE player LIKE '%Messi%' AND outcome='Complete'` |
| 4 | ¿Qué jugador dio más asistencias de gol? | Messi, 220 | `COUNT(*) fct_pass WHERE is_goal_assist GROUP BY player` |
| 5 | Resultados temporada 2020/2021 | Granada 4–0 Barca; Real Madrid 2–1 Barca; Barca 1–0 Levante | `SELECT ... FROM dim_match WHERE season_name='2020/2021'` |
| 6 | ¿Cuántos goles de penalty? | 1,095 | `COUNT(*) fct_shot WHERE shot_type='Penalty' AND is_goal` |
| 7 | ¿Quién tiró más desde fuera del área (x>100)? | Messi, 1,800 | `COUNT(*) fct_shot WHERE location_x>100 GROUP BY player` |
| 8 | ¿Qué equipo hizo más pases completados? | Barcelona, 367,725 | `COUNT(*) fct_pass WHERE outcome='Complete' GROUP BY team` |

Todas las respuestas verificadas contra consultas directas al sidecar
(conteos idénticos; p. ej. goles de penalty 1,095, pases de Barcelona 367,725).

## Artefactos

- `report.html` — **HTML autocontenido** (imágenes embebidas en base64,
  1.3 MB) con sidebar de 8 escenarios + canvas con pregunta/SQL/respuesta/
  captura por escenario + GIF de la sesión.
- `ui-demo.gif` — GIF (447 KB, ~22 s) con las capturas de la sesión en los 8
  escenarios, generado con ffmpeg (slideshow de capturas de `adk web`).
- `screenshots/*.jpeg` — capturas por escenario (Chrome DevTools MCP).
- `build_report.py` — generador del report.html.

## Verificación

- `make verify` → exit 0.
- Demo en vivo: `adk web` (ADK 2.8.0) en `http://127.0.0.1:8001/dev-ui/`,
  navegado y operado vía Chrome DevTools MCP; 8/8 preguntas respondidas
  correctamente con tool-call real.

## Notas MVP

- `gemma4:latest` responde con tools sin loops (probado 8/8); si degrada,
  ADK recomienda ajustar el template del modelfile o usar `gemma4-exec`.
- El agente vive en su propia carpeta (`adk_agent/`) y no modifica el sidecar
  de producción (uvicorn en :8000); corre `adk web` de forma independiente.
- El venv de desarrollo (`google-adk`) está fuera del repo (scratch).