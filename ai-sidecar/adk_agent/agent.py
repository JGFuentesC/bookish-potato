"""Agente ADK para talk-to-your-data sobre la capa gold (GenBI Fútbol).

Tool: ``query_gold(sql)`` ejecuta SELECT sobre el endpoint gold del sidecar
(http://localhost:8000/api/v1/query), que ya valida allow-list + LIMIT.
Modelo: Ollama local en platypy (gemma4:latest, ADR-002).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib import request

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from genbi_ai.semantic.catalog import load_catalog

SIDECAR_URL = os.getenv("SIDECAR_URL", "http://localhost:8000")
MODEL = os.getenv("OLLAMA_LLM_MODEL", "gemma4:latest")


def _load_catalog() -> dict[str, object]:
    return load_catalog(Path(__file__).resolve().parents[1] / "semantic" / "catalog.yaml")  # type: ignore[arg-type]


def _build_instruction() -> str:
    catalog = _load_catalog()
    blocks: list[str] = []
    for table in catalog.tables:  # type: ignore[union-attr]
        cols = ", ".join(c.name for c in table.columns)
        blocks.append(f"- {table.name} ({table.grain or '—'}): {cols}")
    schema = "\n".join(blocks)

    return (
        "Eres un analista de datos de fútbol (StatsBomb). Respondes en español.\n\n"
        "Dispones de una herramienta `query_gold(sql: str)` que ejecuta un SELECT "
        "sobre la capa gold y devuelve filas. Reglas:\n"
        "- Escribe SOLO consultas SELECT, una sola sentencia.\n"
        "- Usa ÚNICAMENTE las tablas de la allow-list (ver esquema).\n"
        "- Añade siempre LIMIT (máx. 100) a tus consultas.\n"
        "- Tras recibir filas, resume la respuesta en una frase clara en español; "
        "  incluye cifras concretas (no inventes).\n"
        "- Si la consulta devuelve error, reformula la SQL y vuelve a llamar.\n"
        "- No respondas preguntas que no puedas contestar con estas tablas.\n\n"
        "Esquema gold (tabla: columnas):\n"
        f"{schema}\n\n"
        "Mapeos útiles: shot_type_name ∈ {Open Play, Penalty, Free Kick, Kick Off, Corner}; "
        "play_pattern_name ∈ {Regular Play, From Corner, From Free Kick, From Throw In, "
        "From Counter, From Goal Kick, From Keeper, From Kick Off, Other}; "
        "home_result ∈ {H, A, D} (victoria local, visitante, empate); "
        "is_goal / is_assist / is_shot_assist / is_goal_assist son booleanos."
    )


def query_gold(sql: str) -> dict[str, object]:
    """Ejecuta una consulta SELECT sobre la capa gold del sidecar.

    Args:
        sql: Sentencia SELECT (DuckDB) sobre tablas gold permitidas.

    Returns:
        dict con claves: columns (list[str]), rows (list[list]), row_count (int),
        duration_ms (int). Si hay error, devuelve ``{"error": str}``.
    """
    payload = json.dumps({"sql": sql}).encode()
    req = request.Request(
        f"{SIDECAR_URL}/api/v1/query",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode())
    except Exception as exc:  # noqa: BLE001 — se reporta al LLM
        return {"error": f"{type(exc).__name__}: {exc}"}

    if "detail" in body:
        return {"error": str(body["detail"])}

    rows = body.get("rows", [])
    preview = rows[:20]
    return {
        "columns": body.get("columns", []),
        "row_count": body.get("row_count", len(rows)),
        "rows": preview,
        "truncated": len(rows) > len(preview),
        "duration_ms": body.get("duration_ms"),
    }


root_agent = Agent(
    model=LiteLlm(model=f"ollama_chat/{MODEL}"),
    name="genbi_futbol",
    description="Analista de fútbol que responde preguntas sobre la capa gold (StatsBomb).",
    instruction=_build_instruction(),
    tools=[query_gold],
)