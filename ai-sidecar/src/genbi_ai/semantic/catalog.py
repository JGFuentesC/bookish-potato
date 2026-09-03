"""Catálogo semántico (E3-H2 lite): carga y valida ``semantic/catalog.yaml``.

El catálogo es la allow-list del endpoint de consulta: define qué tablas
gold existen y qué columnas exponen al NLtoSQL.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ColumnInfo(BaseModel):
    name: str
    type: str
    description: str = ""


class TableInfo(BaseModel):
    name: str
    description: str = ""
    grain: str = ""
    columns: list[ColumnInfo] = Field(default_factory=list)


class Catalog(BaseModel):
    version: int = 1
    tables: list[TableInfo] = Field(default_factory=list)

    @property
    def table_names(self) -> set[str]:
        return {t.name for t in self.tables}


def load_catalog(path: Path) -> Catalog:
    """Carga el catálogo YAML; un schema inválido lanza ``ValidationError``."""
    raw = yaml.safe_load(path.read_text())
    return Catalog.model_validate(raw)