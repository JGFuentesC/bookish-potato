"""Pruebas de los contratos de entidades (competition, match, lineup, 360).

Validan contra muestras reales del subset descargado por ``make data-pull``
(si no hay datos, se marcan como skipped, no rotas).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, ValidationError

from genbi_data.contracts.statsbomb import CompetitionSeason, Match, TeamLineup, ThreeSixty


def _load_json(path: Path) -> list[dict[str, object]]:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        # Archivo corrupto en origen (p. ej. three-sixty con bytes NUL):
        # no es un problema de contrato, se cuarentena en ingesta.
        return []


def _validate_all(root: Path, files: list[Path], model: type[BaseModel]) -> None:
    for path in files:
        for record in _load_json(path):
            model.model_validate(record)


def test_competitions_valid(subset_root: Path | None) -> None:
    if subset_root is None:
        pytest.skip("sin data/raw: ejecutar make data-pull")
    _validate_all(subset_root, [subset_root / "competitions.json"], CompetitionSeason)


def test_matches_valid(subset_root: Path | None) -> None:
    if subset_root is None:
        pytest.skip("sin data/raw")
    _validate_all(subset_root, sorted((subset_root / "matches").glob("*/*.json")), Match)


def test_lineups_valid(subset_root: Path | None) -> None:
    if subset_root is None:
        pytest.skip("sin data/raw")
    _validate_all(subset_root, sorted((subset_root / "lineups").glob("*.json")), TeamLineup)


def test_three_sixty_valid(subset_root: Path | None) -> None:
    if subset_root is None:
        pytest.skip("sin data/raw")
    _validate_all(subset_root, sorted((subset_root / "three-sixty").glob("*.json")), ThreeSixty)


def test_competition_extra_forbid_nulo() -> None:
    """T1.4: un campo desconocido produce error tipado, no silencio."""
    raw = {
        "competition_id": 11,
        "season_id": 90,
        "country_name": "Spain",
        "competition_name": "La Liga",
        "competition_gender": "male",
        "competition_youth": False,
        "competition_international": False,
        "season_name": "2020/2021",
        "match_updated": "x",
        "match_available": "y",
        "match_available_360": None,
        "brand_new_field": 1,
    }
    with pytest.raises(ValidationError) as info:
        CompetitionSeason.model_validate(raw)
    assert "Extra inputs are not permitted" in str(info.value)


def test_match_fields_default_nulos() -> None:
    """Campos opcionales (referee/metadata/360) toleran ausencia y None."""
    raw = {
        "match_id": 1,
        "match_date": "2020-09-12",
        "kick_off": "17:00:00.000",
        "competition": {
            "competition_id": 11,
            "competition_name": "La Liga",
            "country_name": "Spain",
        },
        "season": {"season_id": 90, "season_name": "2020/2021"},
        "home_team": {
            "home_team_id": 206,
            "home_team_name": "Deportivo Alavés",
            "home_team_gender": "male",
            "home_team_group": None,
            "country": {"id": 214, "name": "Spain"},
            "managers": [],
        },
        "away_team": {
            "away_team_id": 217,
            "away_team_name": "Real Madrid",
            "away_team_gender": "male",
            "away_team_group": None,
            "country": {"id": 214, "name": "Spain"},
            "managers": [],
        },
        "home_score": 0,
        "away_score": 1,
        "match_status": "available",
        "match_week": 1,
        "competition_stage": {"id": 1, "name": "Regular Season"},
        "stadium": {"id": 348, "name": "Estadio", "country": {"id": 214, "name": "Spain"}},
        "referee": None,
        "last_updated": None,
        "last_updated_360": None,
        "match_status_360": None,
        "metadata": None,
    }
    match = Match.model_validate(raw)
    assert match.competition_id == 11
    assert match.season_id == 90
    assert match.referee is None
