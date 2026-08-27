"""Contrato de ``lineups/{match_id}.json`` (StatsBomb Open Data)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from genbi_data.contracts.statsbomb._common import STRICT, Country


class LineupCard(BaseModel):
    model_config = STRICT

    time: str
    card_type: str
    reason: str
    period: int


class LineupPosition(BaseModel):
    model_config = STRICT

    position_id: int
    position: str
    from_: str = Field(alias="from")
    to: str | None = None
    from_period: int
    to_period: int | None = None
    start_reason: str
    end_reason: str


class PlayerLineup(BaseModel):
    model_config = STRICT

    player_id: int
    player_name: str
    player_nickname: str | None = None
    jersey_number: int
    country: Country
    cards: list[LineupCard]
    positions: list[LineupPosition]


class TeamLineup(BaseModel):
    """La alineación de un equipo dentro de un partido (elemento del array)."""

    model_config = STRICT

    team_id: int
    team_name: str
    lineup: list[PlayerLineup]
