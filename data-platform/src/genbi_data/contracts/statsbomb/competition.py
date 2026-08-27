"""Contrato del catálogo ``competitions.json`` (StatsBomb Open Data)."""

from __future__ import annotations

from pydantic import BaseModel

from genbi_data.contracts.statsbomb._common import STRICT


class CompetitionSeason(BaseModel):
    """Una fila de ``competitions.json``: competición × temporada disponible."""

    model_config = STRICT

    competition_id: int
    season_id: int
    country_name: str
    competition_name: str
    competition_gender: str
    competition_youth: bool
    competition_international: bool
    season_name: str
    match_updated: str
    match_available: str
    match_updated_360: str | None = None
    match_available_360: str | None = None
