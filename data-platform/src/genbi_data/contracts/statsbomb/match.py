"""Contrato de ``matches/{competition_id}/{season_id}.json`` (StatsBomb Open Data)."""

from __future__ import annotations

from pydantic import BaseModel

from genbi_data.contracts.statsbomb._common import STRICT, Country, RefTag


class Manager(BaseModel):
    model_config = STRICT

    id: int
    name: str
    nickname: str | None = None
    dob: str | None = None
    country: Country


class HomeTeam(BaseModel):
    model_config = STRICT

    home_team_id: int
    home_team_name: str
    home_team_gender: str
    country: Country
    managers: list[Manager]
    home_team_group: str | None = None


class AwayTeam(BaseModel):
    model_config = STRICT

    away_team_id: int
    away_team_name: str
    away_team_gender: str
    country: Country
    managers: list[Manager]
    away_team_group: str | None = None


class MatchSeason(BaseModel):
    model_config = STRICT

    season_id: int
    season_name: str


class MatchCompetition(BaseModel):
    model_config = STRICT

    competition_id: int
    competition_name: str
    country_name: str


class MatchMetadata(BaseModel):
    model_config = STRICT

    data_version: str | None = None
    shot_fidelity_version: str | None = None
    xy_fidelity_version: str | None = None


class Referee(BaseModel):
    model_config = STRICT

    id: int
    name: str
    country: Country


class Stadium(BaseModel):
    model_config = STRICT

    id: int
    name: str
    country: Country


class Match(BaseModel):
    """Un partido completo (una fila del array de ``matches/{c}/{s}.json``)."""

    model_config = STRICT

    match_id: int
    match_date: str
    kick_off: str
    competition: MatchCompetition
    season: MatchSeason
    home_team: HomeTeam
    away_team: AwayTeam
    home_score: int
    away_score: int
    match_status: str
    match_week: int | None = None
    competition_stage: RefTag
    stadium: Stadium | None = None
    referee: Referee | None = None
    last_updated: str | None = None
    last_updated_360: str | None = None
    match_status_360: str | None = None
    metadata: MatchMetadata | None = None

    @property
    def competition_id(self) -> int:
        return self.competition.competition_id

    @property
    def season_id(self) -> int:
        return self.season.season_id
