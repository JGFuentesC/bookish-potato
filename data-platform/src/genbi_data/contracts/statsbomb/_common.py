"""Modelos compartidos de los contratos StatsBomb.

Toda la capa de contratos usa ``ConfigDict(extra="forbid")``: un campo no
declarado produce un error de validación tipado (PRD E1-H2 T1.4), nunca silencio.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

STRICT = ConfigDict(extra="forbid", populate_by_name=True)

# Coordenada StatsBomb: [x, y] o [x, y, z] -> tupla de 2-3 flotantes.
Point = Annotated[tuple[float, ...], Field(min_length=2, max_length=3)]


class RefTag(BaseModel):
    """Referencia StatsBomb genérica ``{id, name}``."""

    model_config = STRICT

    id: int
    name: str


class Country(BaseModel):
    """País ``{id, name}``."""

    model_config = STRICT

    id: int
    name: str
