"""Pruebas del endpoint de consulta gold (E3): validación y ejecución."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from genbi_ai.api.main import app
from genbi_ai.api.query import validate_sql
from genbi_ai.semantic.catalog import Catalog, TableInfo, load_catalog

client = TestClient(app)

CATALOG = Catalog(
    tables=[
        TableInfo(
            name="fct_shot",
            description="Disparos",
            columns=[{"name": "is_goal", "type": "boolean", "description": "gol"}],
        )
    ]
)


def test_catalog_real_loads() -> None:
    catalog = load_catalog(Path(__file__).resolve().parents[1] / "semantic" / "catalog.yaml")
    assert catalog.table_names == {
        "dim_competition_season",
        "dim_match",
        "dim_player",
        "dim_team",
        "fct_pass",
        "fct_shot",
    }


def test_validate_select_ok() -> None:
    sql = validate_sql("SELECT count(*) FROM fct_shot", CATALOG)
    assert "FROM" in sql


def test_validate_forces_limit() -> None:
    sql = validate_sql("SELECT * FROM fct_shot", CATALOG, max_rows=50)
    assert "LIMIT 50" in sql


def test_validate_keeps_existing_limit() -> None:
    sql = validate_sql("SELECT * FROM fct_shot LIMIT 3", CATALOG)
    assert "LIMIT 3" in sql and "LIMIT 50" not in sql


def test_validate_rejects_ddl() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_sql("DROP TABLE fct_shot", CATALOG)
    assert "SELECT" in exc.value.detail


def test_validate_rejects_unknown_table() -> None:
    with pytest.raises(HTTPException) as exc:
        validate_sql("SELECT * FROM secret_table", CATALOG)
    assert "no permitida" in exc.value.detail


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM read_parquet('/etc/passwd')",
        "SELECT * FROM read_csv('/tmp/x.csv')",
        "SELECT * FROM glob('lakehouse/**')",
    ],
)
def test_validate_rejects_table_functions(sql: str) -> None:
    with pytest.raises(HTTPException) as exc:
        validate_sql(sql, CATALOG)
    assert "tabla-función" in exc.value.detail


def test_validate_allows_derived_table() -> None:
    sql = validate_sql(
        "SELECT * FROM (SELECT * FROM fct_shot WHERE is_goal) t", CATALOG, max_rows=10
    )
    assert "LIMIT 10" in sql


def test_validate_rejects_multiple_statements() -> None:
    with pytest.raises(HTTPException):
        validate_sql("SELECT 1; SELECT 2", CATALOG)


def _make_lakehouse(tmp_path: Path) -> Path:
    table = tmp_path / "fct_shot"
    table.mkdir()
    con = duckdb.connect()
    con.execute("CREATE TABLE t (is_goal BOOLEAN, n INTEGER)")
    con.execute("INSERT INTO t VALUES (true, 3), (false, 1)")
    con.execute(f"COPY t TO '{table / 'data.parquet'}' (FORMAT PARQUET)")
    con.close()
    return tmp_path


def test_endpoint_query(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAKEHOUSE_PATH", str(_make_lakehouse(tmp_path)))
    monkeypatch.setenv("MAX_ROWS", "10")
    resp = client.post("/api/v1/query", json={"sql": "SELECT sum(n) AS total FROM fct_shot WHERE is_goal"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["columns"] == ["total"]
    assert body["rows"] == [[3]]


def test_endpoint_rejects_unknown_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAKEHOUSE_PATH", str(_make_lakehouse(tmp_path)))
    resp = client.post("/api/v1/query", json={"sql": "SELECT * FROM oltp.secret"})
    assert resp.status_code == 400
    assert "no permitida" in resp.json()["detail"]