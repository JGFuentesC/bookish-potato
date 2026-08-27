"""Contrato de ``three-sixty/{match_id}.json`` (freeze frames posicionales)."""

from __future__ import annotations

from pydantic import BaseModel

from genbi_data.contracts.statsbomb._common import STRICT, Point


class ThreeSixtyFrame(BaseModel):
    """Un jugador en el frame congelado alrededor de un evento."""

    model_config = STRICT

    teammate: bool
    actor: bool
    keeper: bool
    location: Point


class ThreeSixty(BaseModel):
    """Documento 360 de un evento (elemento del array ``three-sixty/{id}.json``)."""

    model_config = STRICT

    event_uuid: str
    visible_area: list[float]
    freeze_frame: list[ThreeSixtyFrame]
