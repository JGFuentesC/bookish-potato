"""Pruebas de calidad sobre modelos materializados (PRD E2-H1-T3).

Tipos: ``not_null``, ``unique``, ``accepted_values``, ``row_count_min``
y ``expression``. Severidades: ``error`` (aborta la capa) y ``warn``
(registra y continúa).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb

from genbi_data.runner.contracts import DataContract, TestSpec


@dataclass
class TestResult:
    """Resultado de una prueba de calidad."""

    model: str
    test_type: str
    column: str | None
    severity: str
    passed: bool
    message: str | None = None


@dataclass
class QualityReport:
    """Reporte de calidad de un modelo (y de la capa)."""

    model: str
    results: list[TestResult] = field(default_factory=list)

    @property
    def errors(self) -> list[TestResult]:
        return [r for r in self.results if not r.passed and r.severity == "error"]

    @property
    def warnings(self) -> list[TestResult]:
        return [r for r in self.results if not r.passed and r.severity == "warn"]


def run_model_tests(con: duckdb.DuckDBPyConnection, table: str, contract: DataContract) -> QualityReport:
    """Ejecuta las pruebas del contrato contra la tabla materializada."""
    report = QualityReport(model=contract.name)
    for test in contract.tests:
        passed, message = _run_test(con, table, test.type, test.column, test)
        report.results.append(
            TestResult(
                model=contract.name,
                test_type=test.type,
                column=test.column,
                severity=test.severity,
                passed=passed,
                message=message,
            )
        )
    return report


def _run_test(
    con: duckdb.DuckDBPyConnection,
    table: str,
    test_type: str,
    column: str | None,
    test: TestSpec,
) -> tuple[bool, str | None]:
    col = test.column or ""
    if test_type == "not_null":
        n = con.execute(f'SELECT count(*) FROM {table} WHERE {col} IS NULL').fetchone()[0]
        ok = n == 0
        return ok, None if ok else f"{n} nulos en {col}"
    if test_type == "unique":
        n = con.execute(f'SELECT count(*) - count(DISTINCT {col}) FROM {table}').fetchone()[0]
        ok = n == 0
        return ok, None if ok else f"{n} duplicados en {col}"
    if test_type == "accepted_values":
        vals = test.values or []
        placeholders = ", ".join("?" for _ in vals)
        n = con.execute(
            f'SELECT count(*) FROM {table} WHERE {col} NOT IN ({placeholders})',
            [v for v in vals],
        ).fetchone()[0]
        ok = n == 0
        return ok, None if ok else f"{n} valores fuera de lista en {col}"
    if test_type == "row_count_min":
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        ok = n >= (test.min_rows or 0)
        return ok, None if ok else f"{n} filas < mínimo {test.min_rows}"
    if test_type == "expression":
        n = con.execute(f"SELECT count(*) FROM {table} WHERE NOT ({test.expression})").fetchone()[0]
        ok = n == 0
        return ok, None if ok else f"{n} filas violan la expresión"
    return False, f"tipo de prueba desconocido: {test_type}"