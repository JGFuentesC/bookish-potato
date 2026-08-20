# ADR-002 — Selección del modelo local y parámetros

- **Estado**: Aceptado
- **Fecha**: 2026-08-19
- **Decisiones previas**: ADR-001 (sección 10.2 IA), ADR-002 referenciado como pendiente de medición en platypy.
- **PRD**: E0-H3 — Verificación del modelo local en platypy.

## Contexto

El sidecar de IA (agente ADK NL2SQL) necesita un LLM local y un modelo de embeddings servidos por Ollama en platypy (NVIDIA RTX 3070 Laptop, **8 GiB de VRAM**, 31 GB RAM). El PRD §7.2 (RF) exige una variante de **Gemma instruida cuantizada Q4 que quepa entera en 8 GB**, `temperature=0`, con política de degradación a la variante menor si la candidata no cabe. ADR-001 dejó el tag deliberadamente abierto hasta medir sobre VRAM real.

## Alternativas consideradas

| Tag (registro Ollama) | Params | Cuantización | Tamaño disco | Tamaño VRAM cargado | TTFT mediano | tokens/s |
|---|---|---|---|---|---|---|
| `gemma4:latest` (= `gemma4:e4b-it-q4_K_M`, digest `c6eb396dbd59`) | 8.0B | Q4_K_M | 9.6 GB | 3.25 GB | 0.48 s | 63.2 |
| `gemma4:e2b-it-q4_K_M` (digest `7fbdbf8f5e45`) | 5.1B | Q4_K_M | 7.2 GB | 1.64 GB | 0.42 s | 109.2 |

Ventana de contexto máxima declarada por ambos: 131072. Embeddings evaluado: `embeddinggemma` (arquitectura gemma3, 307.58M, dim 768, BF16, num_ctx 2048).

## Evidencia de medición (platypy, 2026-08-19)

Hardware: NVIDIA GeForce RTX 3070 Laptop GPU (8192 MiB). Ollama **0.30.10** en contenedor `lab-ollama` (nota: ADR-001 fijó 0.32.14 como versión objetivo del registro; la instancia real de platypy ejecuta 0.30.10. La decisión de tag no depende de esa diferencia de patch). Salidas crudas: `docs/evidence/E0-H3/bench_gemma4_latest.json`, `docs/evidence/E0-H3/bench_gemma4_e2b.json`.

### Escenario 1 — candidata `gemma4:latest` dentro del presupuesto

Bench `scripts/bench_model.py`, 20 generaciones × 512 tokens, `num_ctx=8192`, `temperature=0`, `seed=42`, prompt representativo del catálogo semántico (~40 entidades + pregunta):

- **VRAM**: `size == size_vram` = 3.25 GB → **carga completa en GPU**. `ollama ps` confirma `PROCESSOR 100% GPU`; `nvidia-smi` 4.1 GiB usados durante la carga del LLM solo.
- **TTFT (latencia primera respuesta)**: min 0.45 s · **mediana 0.48 s** · max 0.50 s → < 3 s ✅
- **Throughput**: min 59.8 · **mediana 63.2** · max 64.5 tokens/s.
- **Ventana de contexto efectiva**: prompt de 578 tokens; `prompt_fits_in_window=true` con `num_ctx=8192` → sin truncado ✅

### Escenario 2 — respaldo `gemma4:e2b-it-q4_K_M` (no aplicó degradación)

5 generaciones × 512 tokens, mismas opciones: carga completa en GPU (1.64 GB), TTFT mediano 0.42 s, 109.2 tokens/s. Queda documentado como respaldo operativo si la candidata dejara de caber (p. ej. al crecer el catálogo).

### Embeddings (T3)

- **Dimensión**: 768 (batch de 20 textos).
- **Latencia por lote**: 3.49 s para 20 ítems → 0.175 s/ítem.
- **Coexistencia en VRAM**: LLM (3.3 GB) + `embeddinggemma` (681 MB) cargados simultáneamente, ambos 100% GPU, 4.97 GiB / 8 GiB. No se necesita política de carga secuencial.

## Decisión

1. **LLM**: tag concreto **`gemma4:latest`** (digest `c6eb396dbd59`, Gemma 4 8B instruct, Q4_K_M) en Ollama de platypy.
2. **Embeddings**: **`embeddinggemma`** (dim 768).
3. **Parámetros de generación** (fijos, `temperature=0` como exige el PRD):
   - `temperature=0`
   - `top_p=0.95` (default del modelfile)
   - `top_k=64` (default del modelfile)
   - `num_ctx=8192`
   - `seed=42` (fijo para reproducibilidad; revisar si el agente necesita variación)
4. **Política de degradación** (si la candidata no cupiera en el futuro): cargar `gemma4:e2b-it-q4_K_M` (5.1B, 1.64 GB VRAM, 109 tok/s), que ya pasó la misma verificación.

## Consecuencias

- El tag queda fijado en `.env.example` (`OLLAMA_LLM_MODEL=gemma4:latest`, `OLLAMA_EMBEDDINGS_MODEL=embeddinggemma`) y en ADR-001 sección 10.2 IA.
- La capa semántica del sidecar y el agente usarán `num_ctx=8192`; el catálogo (~40 entidades) cabe con margen. Si el catálogo crece, medir de nuevo antes de subir `num_ctx`.
- No se requiere política de carga secuencial LLM/embeddings: coexisten en 8 GB.
- Plataforma medida: Ollama 0.30.10; ADR-001 fija 0.32.14 como objetivo. La migración de plataforma no cambia el tag ni los parámetros.