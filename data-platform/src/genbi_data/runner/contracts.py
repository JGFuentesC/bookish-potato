"""Contratos de datos de modelos (PRD E2-H1-T1).

Un contrato YAML describe un modelo: nombre, capa, dependencias,
columnas y pruebas de calidad. Se valida todo al arranque del runner.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Layer = Literal["bronze", "silver", "gold"]
Severity = Literal["error", "warn"]
TestType = Literal[
    "not_null",
    "unique",
    "accepted_values",
    "row_count_min",
    "expression",
]


class TestSpec(BaseModel):
    """Una prueba de calidad declarada en el contrato."""

    __test__ = False  # evita que pytest la coleccione como test

    type: TestType
    column: str | None = None
    severity: Severity = "error"
    min_rows: int | None = None
    values: list[str | int | float] | None = None
    expression: str | None = None

    @model_validator(mode="after")
    def _check_args(self) -> TestSpec:
        if self.type in {"not_null", "unique", "accepted_values"} and not self.column:
            raise ValueError(f"test '{self.type}' requiere 'column'")
        if self.type == "row_count_min" and self.min_rows is None:
            raise ValueError("test 'row_count_min' requiere 'min_rows'")
        if self.type == "expression" and not self.expression:
            raise ValueError("test 'expression' requiere 'expression'")
        return self


class ColumnSpec(BaseModel):
    """Definición de una columna del modelo."""

    name: str
    type: str
    description: str | None = None


class DataContract(BaseModel):
    """Contrato de un modelo SQL (``name``, ``layer``, ``grain``,
    ``depends_on``, ``columns``, ``tests``)."""

    name: str
    layer: Layer
    description: str | None = None
    grain: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    columns: list[ColumnSpec] = Field(default_factory=list)
    tests: list[TestSpec] = Field(default_factory=list)