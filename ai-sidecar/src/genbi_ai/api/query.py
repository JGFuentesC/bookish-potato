"""Endpoint de consulta sobre gold (POC NLtoSQL, E3).

POST /api/v1/query recibe SQL, valida contra el catálogo semántico
(solo SELECT, solo tablas de la allow-list, LIMIT forzado) y lo ejecuta
sobre el lakehouse en Parquet con DuckDB en solo lectura.
"""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Any

import duckdb
import sqlglot
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from genbi_ai.semantic.catalog import Catalog, load_catalog

router = APIRouter(prefix="/api/v1")

DEFAULT_MAX_ROWS = 1000
DEFAULT_TIMEOUT_MS = 30_000


class QueryRequest(BaseModel):
    sql: str


class QueryResponse(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    duration_ms: int


def _catalog() -> Catalog:
    path = Path(__file__).resolve().parents[3] / "semantic" / "catalog.yaml"
    return load_catalog(path)


def _lakehouse() -> Path:
    env = os.getenv("LAKEHOUSE_PATH")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[3].parent / "lakehouse" / "gold"


def validate_sql(sql: str, catalog: Catalog, max_rows: int | None = None) -> str:
    """Valida el SQL: una sola sentencia SELECT sobre tablas permitidas,
    y fuerza un LIMIT para acotar el resultado."""
    try:
        statements = list(sqlglot.parse(sql, read="duckdb"))
    except sqlglot.errors.ParseError as exc:
        raise HTTPException(status_code=400, detail=f"SQL inválido: {exc}") from exc
    if not statements or len(statements) != 1:
        raise HTTPException(status_code=400, detail="se espera exactamente una sentencia")
    stmt = statements[0]
    if not isinstance(stmt, sqlglot.exp.Select):
        raise HTTPException(status_code=400, detail="solo se permiten consultas SELECT")

    for table in stmt.find_all(sqlglot.exp.Table):
        if not table.name:
            raise HTTPException(status_code=400, detail="tabla-función no permitida")
        if table.name not in catalog.table_names:
            raise HTTPException(
                status_code=400, detail=f"tabla no permitida: {table.name}"
            )

    if stmt.args.get("limit") is None:
        limit = max_rows if max_rows is not None else int(
            os.getenv("MAX_ROWS", str(DEFAULT_MAX_ROWS))
        )
        stmt = stmt.limit(limit)
    return stmt.sql(dialect="duckdb")


def _register_views(con: duckdb.DuckDBPyConnection, catalog: Catalog, lakehouse: Path) -> None:
    for table in catalog.tables:
        files = sorted((lakehouse / table.name).glob("*.parquet"))
        if not files:
            continue
        pattern = (lakehouse / table.name / "*.parquet").as_posix()
        con.execute(
            f'CREATE OR REPLACE VIEW "{table.name}" AS '
            f"SELECT * FROM read_parquet('{pattern}')"
        )


@router.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    catalog = _catalog()
    lakehouse = _lakehouse()
    safe_sql = validate_sql(req.sql, catalog)

    con = duckdb.connect()
    result: dict[str, Any] = {}

    def _run() -> None:
        try:
            res = con.execute(safe_sql)
            result["columns"] = [d[0] for d in res.description]
            result["rows"] = [list(r) for r in res.fetchall()]
        except BaseException as exc:  # noqa: BLE001 — se propaga al hilo principal
            result["error"] = exc

    try:
        _register_views(con, catalog, lakehouse)
        start = time.time()
        timeout_ms = int(os.getenv("QUERY_TIMEOUT_MS", str(DEFAULT_TIMEOUT_MS)))
        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(timeout_ms / 1000)
        if worker.is_alive():
            con.close()
            raise HTTPException(status_code=504, detail="la consulta excedió el timeout")
        if "error" in result:
            raise result["error"]  # type: ignore[misc]
    except duckdb.Error as exc:
        raise HTTPException(status_code=400, detail=f"ejecución fallida: {exc}") from exc
    finally:
        con.close()

    return QueryResponse(
        columns=result["columns"],
        rows=result["rows"],
        row_count=len(result["rows"]),
        duration_ms=int((time.time() - start) * 1000),
    )