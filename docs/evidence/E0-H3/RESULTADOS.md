# E0-H3 — Verificación del modelo local en platypy (ADR-002)

Fecha: 2026-08-19 · Estado: **completado, en espera de VoBo**

## Qué se probó

Candidata LLM `gemma4:latest` (Gemma 4 8B instruct, Q4_K_M) y respaldo `gemma4:e2b-it-q4_K_M` (5.1B), embeddings `embeddinggemma`, sobre Ollama de platypy (RTX 3070 Laptop, 8 GiB VRAM). Bench: `scripts/bench_model.py` (VRAM vía `/api/ps`, TTFT, tokens/s, ventana de contexto).

## Comandos y salidas relevantes

- Inventario: `ollama list` en `lab-ollama` → `gemma4:latest` (9.6 GB disco), `gemma4:e2b-it-q4_K_M` (7.2 GB, descargado en esta sesión), `embeddinggemma` (621 MB).
- Acceso: sin conectividad directa a `11434` (IP Tailscale cambió a `IP_INTERNA`); se usó túnel SSH `-L 11434:127.0.0.1:11434 platypy`.
- Bench candidata (20 × 512 tokens, `num_ctx=8192`, `temperature=0`, `seed=42`, prompt catálogo ~40 entidades):
  - `fully_in_vram: true` — `size == size_vram` = 3.25 GB; `ollama ps` `PROCESSOR 100% GPU`; `nvidia-smi` 4.1 GiB con solo LLM.
  - TTFT: min 0.45 s · **mediana 0.48 s** · max 0.50 s → cumple < 3 s.
  - tokens/s: min 59.8 · **mediana 63.2** · max 64.5.
  - Prompt de 578 tokens: `prompt_fits_in_window: true` (sin truncado).
- Bench respaldo (5 × 512 tokens): `fully_in_vram` (1.64 GB), TTFT mediano 0.42 s, 109.2 tok/s.
- Embeddings: batch de 20 → dim 768, 3.49 s (0.175 s/ítem).
- Coexistencia: `ollama ps` con LLM (3.3 GB) + embeddings (681 MB) cargados a la vez, ambos 100% GPU; `nvidia-smi` 4966 MiB / 8192 MiB. No se necesita carga secuencial.
- Salidas JSON: `bench_gemma4_latest.json`, `bench_gemma4_e2b.json` (misma carpeta).

## Resultado

- **Escenario 1 (modelo en presupuesto)**: ✅ pasa — `gemma4:latest` queda entero en GPU, TTFT mediano 0.48 s < 3 s, prompt sin truncar.
- **Escenario 2 (degradación)**: no aplicó; `gemma4:e2b-it-q4_K_M` queda verificado como respaldo.
- DoD: tag fijado en `.env.example` (`OLLAMA_LLM_MODEL=gemma4:latest`, `OLLAMA_EMBEDDINGS_MODEL=embeddinggemma`) y en ADR-002.

## Artefactos

- `scripts/bench_model.py`, `scripts/prompt_catalogo.txt`
- `docs/adr/ADR-002-local-model-selection.md` (decisiones + evidencia)
- `docs/adr/ADR-001-stack-versions.md` (filas LLM/embeddings cerradas)
- `.env.example`, `README.md`

## Notas

- platypy ejecuta Ollama **0.30.10** en el contenedor `lab-ollama`; ADR-001 fija 0.32.14 como objetivo de plataforma. Se registra la discrepancia en ADR-002; no afecta al tag ni a los parámetros.
- `ollama ps` en este 0.30.10 no expone el campo `processor` por API; la verificación de offload 100% GPU usa `size == size_vram` + `ollama ps` CLI (columna PROCESSOR) + `nvidia-smi`.