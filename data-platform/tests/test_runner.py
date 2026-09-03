"""Pruebas del runner de modelos (E2-H1): contratos, DAG y calidad."""

from __future__ import annotations

import duckdb
import pytest
from pydantic import ValidationError

from genbi_data.quality.tests import run_model_tests
from genbi_data.runner.contracts import DataContract
from genbi_data.runner.dag import topological_order


def test_contract_valid() -> None:
    c = DataContract.model_validate(
        {
            "name": "fct_shot",
            "layer": "gold",
            "columns": [{"name": "event_id", "type": "uuid"}],
            "tests": [{"type": "unique", "column": "event_id"}],
        }
    )
    assert c.name == "fct_shot"
    assert c.layer == "gold"


def test_contract_invalid_test_raises() -> None:
    with pytest.raises(ValidationError):
        DataContract.model_validate(
            {"name": "x", "layer": "gold", "tests": [{"type": "not_null"}]}
        )


def test_contract_invalid_layer_raises() -> None:
    with pytest.raises(ValidationError):
        DataContract.model_validate({"name": "x", "layer": "platino"})


def test_topological_order_respects_dependencies() -> None:
    order = topological_order(
        ["a", "b", "c"],
        {"a": [], "b": ["a"], "c": ["a", "b"]},
    )
    assert order.index("a") < order.index("b") < order.index("c")


def test_topological_order_detects_cycle() -> None:
    with pytest.raises(ValueError, match="ciclo"):
        topological_order(["a", "b"], {"a": ["b"], "b": ["a"]})


def test_topological_order_unknown_dependency() -> None:
    with pytest.raises(ValueError, match="no está declarado"):
        topological_order(["a"], {"a": ["ghost"]})


def _quality_contract(tests: list[dict]) -> DataContract:
    return DataContract.model_validate(
        {"name": "t", "layer": "gold", "tests": tests}
    )


def test_quality_not_null() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a INTEGER)")
    con.execute("INSERT INTO t VALUES (1), (NULL)")
    report = run_model_tests(con, "t", _quality_contract([{"type": "not_null", "column": "a"}]))
    assert not report.errors[0].passed
    con.close()


def test_quality_unique() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a INTEGER)")
    con.execute("INSERT INTO t VALUES (1), (1), (2)")
    report = run_model_tests(con, "t", _quality_contract([{"type": "unique", "column": "a"}]))
    assert not report.errors[0].passed
    con.close()


def test_quality_row_count_min_ok() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a INTEGER)")
    con.execute("INSERT INTO t VALUES (1), (2), (3)")
    report = run_model_tests(
        con, "t", _quality_contract([{"type": "row_count_min", "min_rows": 3}])
    )
    assert not report.errors
    con.close()


def test_quality_accepted_values() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a VARCHAR)")
    con.execute("INSERT INTO t VALUES ('H'), ('A'), ('X')")
    report = run_model_tests(
        con,
        "t",
        _quality_contract(
            [{"type": "accepted_values", "column": "a", "values": ["H", "A", "D"]}]
        ),
    )
    assert not report.errors[0].passed
    con.close()


def test_quality_expression_and_severity_warn() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t (a INTEGER)")
    con.execute("INSERT INTO t VALUES (1), (2), (200)")
    report = run_model_tests(
        con,
        "t",
        _quality_contract([{"type": "expression", "expression": "a < 100", "severity": "warn"}]),
    )
    assert report.warnings and not report.errors
    con.close()