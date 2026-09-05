"""Endpoint de pregunta en lenguaje natural (NL2SQL) sobre la capa gold.

POST /api/v1/nl2sql recibe una pregunta en español, la traduce a SQL con un
modelo Ollama local (ADR-002), valida la SQL contra el catálogo semántico
(guardas del endpoint /query) y la ejecuta sobre el lakehouse. Después genera
una respuesta en lenguaje natural a partir de las filas obtenidas.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from genbi_ai.api.query import execute_sql
from genbi_ai.semantic.catalog import Catalog, load_catalog

router = APIRouter(prefix="/api/v1")

DEFAULT_MODEL = "gemma4:latest"
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT_MS", "120000")) / 1000
MAX_ATTEMPTS = 2
_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


class Nl2SqlRequest(BaseModel):
    question: str


class Nl2SqlResponse(BaseModel):
    sql: str
    answer: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    duration_ms: int


def _ollama_chat(system: str, user: str, *, temperature: float = 0.0) -> str:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_LLM_MODEL", DEFAULT_MODEL)
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {"temperature": temperature, "num_ctx": 8192},
    }
    try:
        resp = httpx.post(f"{base}/api/chat", json=payload, timeout=OLLAMA_TIMEOUT)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail=f"modelo no disponible: {type(exc).__name__}"
        ) from exc
    content = resp.json().get("message", {}).get("content", "").strip()
    if not content:
        raise HTTPException(status_code=502, detail="el modelo no devolvió contenido")
    return content


def _extract_sql(text: str) -> str:
    """Extrae la primera sentencia SQL del texto generado por el LLM.

    Limpia códigos ANSI (algunos modelos emiten resaltado), prefiere bloques
    entre ```sql``` y, si no hay fences, toma desde el primer WITH/SELECT.
    """
    text = _ANSI_RE.sub("", text)

    fenced = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1)
    else:
        match = re.search(r"\b(WITH|SELECT)\b", text, re.IGNORECASE)
        if not match:
            raise HTTPException(status_code=502, detail="el modelo no generó SQL válido")
        candidate = text[match.start() :]

    sql = candidate.strip().rstrip(";").strip()
    if not re.match(r"^(WITH|SELECT)\b", sql, re.IGNORECASE):
        raise HTTPException(status_code=502, detail="el modelo no generó SQL válido")
    return sql


def _catalog() -> Catalog:
    from pathlib import Path

    return load_catalog(Path(__file__).resolve().parents[3] / "semantic" / "catalog.yaml")


def _schema_block(catalog: Catalog) -> str:
    blocks: list[str] = []
    for table in catalog.tables:
        cols = ", ".join(c.name for c in table.columns)
        blocks.append(f"- {table.name} ({table.grain or '—'}): {cols}")
    return "\n".join(blocks)


def _sql_system(catalog: Catalog, previous_error: str | None = None) -> str:
    base = (
        "Eres un analista de datos de fútbol (StatsBomb). Traduces preguntas en "
        "español a SQL DuckDB sobre la capa gold.\n\n"
        "Reglas:\n"
        "- Devuelve SOLO la sentencia SQL (una sola), sin markdown, sin texto y "
        "sin códigos de escape.\n"
        "- Puedes usar WITH (CTEs) y agrupaciones; el resultado debe compilar en "
        "DuckDB.\n"
        "- Usa ÚNICAMENTE las tablas del esquema (allow-list).\n"
        "- Añade siempre LIMIT (máx. 100).\n"
    )
    base += (
        "- Los nombres de jugadores/equipos se buscan con ILIKE (insensible a "
        "mayúsculas) y %texto%.\n"
        "- IMPORTANTE: los nombres en los datos llevan acentos y diéresis "
        "(Müller, Fernández, Alcácer). Si el usuario escribe sin acento, cubre "
        "ambas grafías, p. ej. (player_name ILIKE '%Muller%' OR player_name "
        "ILIKE '%Müller%').\n"
        "- Goles de un jugador: COUNT(CASE WHEN is_goal=TRUE THEN 1 ELSE NULL END) "
        "sobre fct_shot filtrado por player_name.\n"
        "- 'goles' se refiere a fct_shot.is_goal; 'pases' a fct_pass; "
        "'asistencias' a fct_pass.is_goal_assist.\n"
        "- FORMATOS EXACTOS: season_name usa 'YYYY/YYYY' (p. ej. '2020/2021'); "
        "competition_name usa 'La Liga'. Filtra con ILIKE '%2020/2021%'.\n\n"
        "Esquema gold (tabla: columnas):\n"
        f"{_schema_block(catalog)}\n\n"
        "Mapeos útiles: shot_type_name ∈ {Open Play, Penalty, Free Kick, Kick Off, "
        "Corner}; play_pattern_name ∈ {Regular Play, From Corner, From Free Kick, "
        "From Throw In, From Counter, From Goal Kick, From Keeper, From Kick Off, "
        "Other}; home_result ∈ {H, A, D}; is_goal / is_assist / is_shot_assist / "
        "is_goal_assist son booleanos."
    )
    if previous_error:
        base += (
            f"\n\nLa consulta anterior NO compiló y este fue el error: "
            f"{previous_error}. Genera de nuevo una sentencia SQL válida que "
            "responda la misma pregunta."
        )
    return base


def _answer_system() -> str:
    return (
        "Eres un analista de datos de fútbol. Responde la pregunta del usuario en "
        "una sola frase clara en español, usando ÚNICAMENTE las filas y columnas "
        "entregadas. Incluye cifras concretas. No inventes datos."
    )


def _summarize(question: str, columns: list[str], rows: list[list[Any]]) -> str:
    preview = {"columns": columns, "rows": rows[:10]}
    user = (
        f"Pregunta: {question}\n\n"
        f"Resultado de la consulta (JSON):\n{json.dumps(preview, ensure_ascii=False)}\n\n"
        "Responde en una frase."
    )
    return _ollama_chat(_answer_system(), user, temperature=0.0)


@router.post("/nl2sql", response_model=Nl2SqlResponse)
def nl2sql(req: Nl2SqlRequest) -> Nl2SqlResponse:
    question = req.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="pregunta vacía")

    catalog = _catalog()

    last_error: str | None = None
    result: dict[str, Any] = {}
    sql = ""
    for _ in range(MAX_ATTEMPTS):
        generated = _ollama_chat(_sql_system(catalog, last_error), f"Pregunta: {question}")
        sql = _extract_sql(generated)
        try:
            candidate = execute_sql(sql)
        except HTTPException as exc:
            last_error = str(exc.detail)
            continue
        if not candidate["rows"]:
            last_error = (
                "la consulta no devolvió resultados; revisa los filtros "
                "(season_name usa 'YYYY/YYYY', competition_name 'La Liga', "
                "y los nombres llevan acentos)"
            )
            continue
        result = candidate
        break
    else:
        raise HTTPException(status_code=502, detail=f"no se pudo responder la pregunta: {last_error}")

    rows = result["rows"]
    if not rows:
        answer = "La consulta no devolvió resultados."
    else:
        answer = _summarize(question, result["columns"], rows)

    return Nl2SqlResponse(
        sql=sql,
        answer=answer,
        columns=result["columns"],
        rows=rows,
        row_count=result["row_count"],
        duration_ms=result["duration_ms"],
    )