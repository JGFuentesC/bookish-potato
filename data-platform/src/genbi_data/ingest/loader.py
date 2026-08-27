"""Cargador de datos StatsBomb a OLTP PostgreSQL (PRD E1-H3 T1).

Carga partidos, alineaciones y eventos en oltp con:
- Upsert idempotente de entidades maestras con caché en memoria.
- COPY binario de psycopg3 para eventos (rendimiento).
- Transacción por archivo: confirma todo o revierte.
- Resolución de catálogos dinámicos (event_type, body_part, etc.)
  que pueden traer ids nuevos no semillados.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

import psycopg

from genbi_data.contracts.statsbomb import Match, TeamLineup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entity cache
# ---------------------------------------------------------------------------


@dataclass
class EntityCache:
    """Caché en memoria de entidades maestras para upsert idempotente."""

    _country: dict[str, int] = field(default_factory=dict)  # name -> id
    _team: dict[int, bool] = field(default_factory=dict)  # team_id -> exists
    _player: dict[int, bool] = field(default_factory=dict)  # player_id -> exists
    _manager: dict[int, bool] = field(default_factory=dict)  # manager_id -> exists
    _stadium: dict[int, bool] = field(default_factory=dict)  # stadium_id -> exists
    _referee: dict[int, bool] = field(default_factory=dict)  # referee_id -> exists
    _competition: dict[int, bool] = field(default_factory=dict)  # competition_id -> exists
    _season: dict[int, bool] = field(default_factory=dict)  # season_id -> exists
    _competition_stage: dict[int, bool] = field(default_factory=dict)
    # Catálogos dinámicos: name -> id (para los que pueden traer valores nuevos)
    _event_type: dict[str, int] = field(default_factory=dict)
    _position: dict[str, int] = field(default_factory=dict)
    _play_pattern: dict[str, int] = field(default_factory=dict)
    _body_part: dict[str, int] = field(default_factory=dict)
    _outcome: dict[str, int] = field(default_factory=dict)
    _technique: dict[str, int] = field(default_factory=dict)
    _pass_height: dict[str, int] = field(default_factory=dict)
    _pass_type: dict[str, int] = field(default_factory=dict)
    _shot_type: dict[str, int] = field(default_factory=dict)
    _duel_type: dict[str, int] = field(default_factory=dict)
    _goalkeeper_type: dict[str, int] = field(default_factory=dict)
    _card_type: dict[str, int] = field(default_factory=dict)
    _formation: dict[int, bool] = field(default_factory=dict)


def _load_cache(conn: psycopg.Connection) -> EntityCache:
    """Carga todas las entidades maestras existentes en caché."""
    cache = EntityCache()

    for row in conn.execute("SELECT country_id, country_name FROM oltp.country"):
        cache._country[row[1]] = row[0]
    for row in conn.execute("SELECT team_id FROM oltp.team"):
        cache._team[row[0]] = True
    for row in conn.execute("SELECT player_id FROM oltp.player"):
        cache._player[row[0]] = True
    for row in conn.execute("SELECT manager_id FROM oltp.manager"):
        cache._manager[row[0]] = True
    for row in conn.execute("SELECT stadium_id FROM oltp.stadium"):
        cache._stadium[row[0]] = True
    for row in conn.execute("SELECT referee_id FROM oltp.referee"):
        cache._referee[row[0]] = True
    for row in conn.execute("SELECT competition_id FROM oltp.competition"):
        cache._competition[row[0]] = True
    for row in conn.execute("SELECT season_id FROM oltp.season"):
        cache._season[row[0]] = True
    for row in conn.execute("SELECT competition_stage_id FROM oltp.competition_stage"):
        cache._competition_stage[row[0]] = True

    # Catálogos dinámicos
    for row in conn.execute("SELECT event_type_id, event_type_name FROM oltp.event_type"):
        cache._event_type[row[1]] = row[0]
    for row in conn.execute("SELECT position_id, position_name FROM oltp.position"):
        cache._position[row[1]] = row[0]
    for row in conn.execute("SELECT play_pattern_id, play_pattern_name FROM oltp.play_pattern"):
        cache._play_pattern[row[1]] = row[0]
    for row in conn.execute("SELECT body_part_id, body_part_name FROM oltp.body_part"):
        cache._body_part[row[1]] = row[0]
    for row in conn.execute("SELECT outcome_id, outcome_name FROM oltp.outcome"):
        cache._outcome[row[1]] = row[0]
    for row in conn.execute("SELECT technique_id, technique_name FROM oltp.technique"):
        cache._technique[row[1]] = row[0]
    for row in conn.execute("SELECT pass_height_id, pass_height_name FROM oltp.pass_height"):
        cache._pass_height[row[1]] = row[0]
    for row in conn.execute("SELECT pass_type_id, pass_type_name FROM oltp.pass_type"):
        cache._pass_type[row[1]] = row[0]
    for row in conn.execute("SELECT shot_type_id, shot_type_name FROM oltp.shot_type"):
        cache._shot_type[row[1]] = row[0]
    for row in conn.execute("SELECT duel_type_id, duel_type_name FROM oltp.duel_type"):
        cache._duel_type[row[1]] = row[0]
    for row in conn.execute(
        "SELECT goalkeeper_type_id, goalkeeper_type_name FROM oltp.goalkeeper_type"
    ):
        cache._goalkeeper_type[row[1]] = row[0]
    for row in conn.execute("SELECT card_type_id, card_type_name FROM oltp.card_type"):
        cache._card_type[row[1]] = row[0]
    for row in conn.execute("SELECT formation_id FROM oltp.formation"):
        cache._formation[row[0]] = True

    logger.debug(
        "cache loaded: %d countries, %d teams, %d players",
        len(cache._country),
        len(cache._team),
        len(cache._player),
    )
    return cache


# ---------------------------------------------------------------------------
# Upsert helpers
# ---------------------------------------------------------------------------

# Regiones usadas por competitions.json sin id natural de StatsBomb (agrupan
# competiciones continentales). IDs fijos fuera del rango natural (3-249).
_REGION_COUNTRY_IDS: dict[str, int] = {
    "Africa": 900,
    "Europe": 901,
    "South America": 902,
    "International": 903,
    "North and Central America": 904,
}


def _ensure_country(
    conn: psycopg.Connection, cache: EntityCache, name: str, statsbomb_id: int | None = None
) -> int:
    if name in cache._country:
        return cache._country[name]
    row = conn.execute(
        "SELECT country_id FROM oltp.country WHERE country_name = %s", (name,)
    ).fetchone()
    if row:
        cache._country[name] = row[0]
        return row[0]
    if statsbomb_id is None:
        statsbomb_id = _REGION_COUNTRY_IDS.get(name)
    if statsbomb_id is None:
        raise ValueError(f"country {name!r} sin id natural de StatsBomb")
    conn.execute(
        "INSERT INTO oltp.country (country_id, country_name) VALUES (%s, %s)",
        (statsbomb_id, name),
    )
    cache._country[name] = statsbomb_id
    logger.info("new country: %d = %s", statsbomb_id, name)
    return statsbomb_id


def _ensure_catalog(
    conn: psycopg.Connection,
    cache_dict: dict[str, int],
    table: str,
    id_col: str,
    name_col: str,
    name: str,
) -> int:
    """Upsert genérico para tablas catálogo (id, name)."""
    if name in cache_dict:
        return cache_dict[name]
    row = conn.execute(
        f"SELECT {id_col} FROM oltp.{table} WHERE {name_col} = %s", (name,)
    ).fetchone()
    if row:
        cache_dict[name] = row[0]
        return row[0]
    row = conn.execute(f"SELECT COALESCE(MAX({id_col}), 0) + 1 FROM oltp.{table}").fetchone()
    new_id = row[0]
    conn.execute(
        f"INSERT INTO oltp.{table} ({id_col}, {name_col}) VALUES (%s, %s)",
        (new_id, name),
    )
    cache_dict[name] = new_id
    logger.info("new %s: %d = %s", table, new_id, name)
    return new_id


def _ensure_team(
    conn: psycopg.Connection,
    cache: EntityCache,
    team_id: int,
    team_name: str,
    team_gender: str | None,
    country_name: str,
    country_id: int | None = None,
) -> None:
    if cache._team.get(team_id):
        return
    cid = (
        _ensure_country(conn, cache, country_name, country_id)
        if country_name
        else (country_id or 214)
    )
    conn.execute(
        """INSERT INTO oltp.team (team_id, team_name, team_gender, country_id)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (team_id) DO NOTHING""",
        (team_id, team_name, team_gender, cid),
    )
    cache._team[team_id] = True


def _ensure_player(
    conn: psycopg.Connection,
    cache: EntityCache,
    player_id: int,
    player_name: str,
    player_nickname: str | None,
    country_name: str | None,
    country_id: int | None = None,
) -> None:
    if cache._player.get(player_id):
        return
    cid = (
        _ensure_country(conn, cache, country_name, country_id)
        if country_name
        else (country_id or 214)
    )
    conn.execute(
        """INSERT INTO oltp.player (player_id, player_name, player_nickname, country_id)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (player_id) DO NOTHING""",
        (player_id, player_name, player_nickname, cid),
    )
    cache._player[player_id] = True


def _ensure_manager(
    conn: psycopg.Connection,
    cache: EntityCache,
    manager_id: int,
    name: str,
    nickname: str | None,
    dob: str | None,
    country_name: str | None,
    country_id: int | None = None,
) -> None:
    if cache._manager.get(manager_id):
        return
    cid = (
        _ensure_country(conn, cache, country_name, country_id)
        if country_name
        else (country_id or 214)
    )
    conn.execute(
        """INSERT INTO oltp.manager (manager_id, name, nickname, date_of_birth, country_id)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (manager_id) DO NOTHING""",
        (manager_id, name, nickname, dob, cid),
    )
    cache._manager[manager_id] = True


def _ensure_stadium(
    conn: psycopg.Connection,
    cache: EntityCache,
    stadium_id: int,
    stadium_name: str,
    country_name: str | None,
    country_id: int | None = None,
) -> None:
    if cache._stadium.get(stadium_id):
        return
    cid = (
        _ensure_country(conn, cache, country_name, country_id)
        if country_name
        else (country_id or 214)
    )
    conn.execute(
        """INSERT INTO oltp.stadium (stadium_id, stadium_name, country_id)
           VALUES (%s, %s, %s)
           ON CONFLICT (stadium_id) DO NOTHING""",
        (stadium_id, stadium_name, cid),
    )
    cache._stadium[stadium_id] = True


def _ensure_referee(
    conn: psycopg.Connection,
    cache: EntityCache,
    referee_id: int,
    referee_name: str,
    country_name: str | None,
    country_id: int | None = None,
) -> None:
    if cache._referee.get(referee_id):
        return
    cid = (
        _ensure_country(conn, cache, country_name, country_id)
        if country_name
        else (country_id or 214)
    )
    conn.execute(
        """INSERT INTO oltp.referee (referee_id, referee_name, country_id)
           VALUES (%s, %s, %s)
           ON CONFLICT (referee_id) DO NOTHING""",
        (referee_id, referee_name, cid),
    )
    cache._referee[referee_id] = True


def _ensure_competition(
    conn: psycopg.Connection,
    cache: EntityCache,
    comp: Any,
    country_name: str,
) -> None:
    cid = getattr(comp, "competition_id", None) or comp["competition_id"]
    if cache._competition.get(cid):
        return
    country_id = _ensure_country(conn, cache, country_name)
    cname = getattr(comp, "competition_name", None) or comp["competition_name"]
    cgender = getattr(comp, "competition_gender", None)
    cyouth = getattr(comp, "competition_youth", None)
    cintl = getattr(comp, "competition_international", None)
    conn.execute(
        """INSERT INTO oltp.competition 
           (competition_id, competition_name, country_id, competition_gender, is_youth, is_international)
           VALUES (%s, %s, %s, %s, %s, %s)
           ON CONFLICT (competition_id) DO NOTHING""",
        (cid, cname, country_id, cgender, cyouth, cintl),
    )
    cache._competition[cid] = True


def _ensure_season(conn: psycopg.Connection, cache: EntityCache, season: Any) -> None:
    sid = getattr(season, "season_id", None) or season["season_id"]
    if cache._season.get(sid):
        return
    sname = getattr(season, "season_name", None) or season["season_name"]
    conn.execute(
        """INSERT INTO oltp.season (season_id, season_name)
           VALUES (%s, %s)
           ON CONFLICT (season_id) DO NOTHING""",
        (sid, sname),
    )
    cache._season[sid] = True


def _ensure_competition_stage(
    conn: psycopg.Connection,
    cache: EntityCache,
    stage: Any,
) -> int:
    sid = getattr(stage, "id", None) or stage["id"]
    if cache._competition_stage.get(sid):
        return sid
    sname = getattr(stage, "name", None) or stage["name"]
    conn.execute(
        """INSERT INTO oltp.competition_stage (competition_stage_id, competition_stage_name)
           VALUES (%s, %s)
           ON CONFLICT (competition_stage_id) DO NOTHING""",
        (sid, sname),
    )
    cache._competition_stage[sid] = True
    return sid


# ---------------------------------------------------------------------------
# Master entity resolution from match
# ---------------------------------------------------------------------------


def _resolve_match_masters(conn: psycopg.Connection, cache: EntityCache, m: Match) -> None:
    """Upsert de todas las entidades maestras de un partido."""
    _ensure_competition(conn, cache, m.competition, m.competition.country_name)
    _ensure_season(conn, cache, m.season)
    _ensure_competition_stage(conn, cache, m.competition_stage)

    _ensure_team(
        conn,
        cache,
        m.home_team.home_team_id,
        m.home_team.home_team_name,
        m.home_team.home_team_gender,
        m.home_team.country.name,
        m.home_team.country.id,
    )
    _ensure_team(
        conn,
        cache,
        m.away_team.away_team_id,
        m.away_team.away_team_name,
        m.away_team.away_team_gender,
        m.away_team.country.name,
        m.away_team.country.id,
    )

    for mgr in m.home_team.managers:
        _ensure_manager(
            conn,
            cache,
            mgr.id,
            mgr.name,
            mgr.nickname,
            mgr.dob,
            mgr.country.name if mgr.country else None,
            mgr.country.id if mgr.country else None,
        )
    for mgr in m.away_team.managers:
        _ensure_manager(
            conn,
            cache,
            mgr.id,
            mgr.name,
            mgr.nickname,
            mgr.dob,
            mgr.country.name if mgr.country else None,
            mgr.country.id if mgr.country else None,
        )

    if m.stadium:
        _ensure_stadium(
            conn,
            cache,
            m.stadium.id,
            m.stadium.name,
            m.stadium.country.name if m.stadium.country else None,
            m.stadium.country.id if m.stadium.country else None,
        )
    if m.referee:
        _ensure_referee(
            conn,
            cache,
            m.referee.id,
            m.referee.name,
            m.referee.country.name if m.referee.country else None,
            m.referee.country.id if m.referee.country else None,
        )


def _resolve_lineup_masters(
    conn: psycopg.Connection, cache: EntityCache, lineup: TeamLineup
) -> None:
    """Upsert de entidades maestras de una alineación."""
    _ensure_team(conn, cache, lineup.team_id, lineup.team_name, None, None)  # type: ignore[arg-type]
    for p in lineup.lineup:
        # Ensure country exists first (statsbomb_id from raw data)
        if p.country:
            _ensure_country(conn, cache, p.country.name, p.country.id)
        _ensure_player(
            conn,
            cache,
            p.player_id,
            p.player_name,
            p.player_nickname,
            p.country.name if p.country else None,
            p.country.id if p.country else None,
        )


# ---------------------------------------------------------------------------
# Match insert
# ---------------------------------------------------------------------------


def _insert_match(conn: psycopg.Connection, m: Match) -> None:
    """Inserta el registro del partido (idempotente por match_id)."""
    stage_id = m.competition_stage.id
    stadium_id = m.stadium.id if m.stadium else None
    referee_id = m.referee.id if m.referee else None
    # kick_off viene como "HH:MM:SS.mmm" — combinar con match_date para timestamptz
    kick_off_ts = None
    if m.kick_off and m.match_date:
        kick_off_ts = f"{m.match_date}T{m.kick_off}"
    elif m.kick_off:
        kick_off_ts = f"1970-01-01T{m.kick_off}"
    conn.execute(
        """INSERT INTO oltp.match
           (match_id, competition_id, season_id, home_team_id, away_team_id,
            stadium_id, referee_id, competition_stage_id, match_date, kick_off,
            home_score, away_score, match_week)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (match_id) DO NOTHING""",
        (
            m.match_id,
            m.competition_id,
            m.season_id,
            m.home_team.home_team_id,
            m.away_team.away_team_id,
            stadium_id,
            referee_id,
            stage_id,
            m.match_date,
            kick_off_ts,
            m.home_score,
            m.away_score,
            m.match_week,
        ),
    )


def _insert_match_managers(conn: psycopg.Connection, m: Match) -> None:
    for team, team_id in [
        (m.home_team, m.home_team.home_team_id),
        (m.away_team, m.away_team.away_team_id),
    ]:
        for mgr in team.managers:
            conn.execute(
                """INSERT INTO oltp.match_manager (match_id, team_id, manager_id)
                   VALUES (%s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (m.match_id, team_id, mgr.id),
            )


def _insert_lineup(conn: psycopg.Connection, match_id: int, lineup: TeamLineup) -> None:
    """Inserta alineación de un equipo: match_player + match_player_position + match_player_card."""
    for p in lineup.lineup:
        # match_player
        country_id = p.country.id if p.country else None
        conn.execute(
            """INSERT INTO oltp.match_player (match_id, player_id, team_id, jersey_number, country_id)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (match_id, player_id) DO NOTHING""",
            (match_id, p.player_id, lineup.team_id, p.jersey_number, country_id),
        )
        # match_player_position
        for pos in p.positions:
            conn.execute(
                """INSERT INTO oltp.match_player_position
                   (match_id, player_id, position_id, from_period, from_time)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (match_id, p.player_id, pos.position_id, pos.from_period, _parse_time(pos.from_)),
            )
        # match_player_card
        for i, card in enumerate(p.cards):
            # card_type mapping: "Yellow Card" -> 7, "Red Card" -> 5, "Second Yellow" -> 6
            card_type_map = {"Yellow Card": 7, "Red Card": 5, "Second Yellow": 6}
            card_type_id = card_type_map.get(card.card_type, 7)
            conn.execute(
                """INSERT INTO oltp.match_player_card
                   (match_id, player_id, card_seq, card_type_id, minute, reason)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (match_id, p.player_id, i + 1, card_type_id, None, card.reason),
            )


def _parse_time(time_str: str) -> float | None:
    """Convierte 'MM:SS' a segundos."""
    if not time_str:
        return None
    parts = time_str.split(":")
    if len(parts) == 2:
        try:
            return float(parts[0]) * 60 + float(parts[1])
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Event loading (via flatten.py)
# ---------------------------------------------------------------------------


def _load_events_for_match(
    conn: psycopg.Connection,
    cache: EntityCache,
    match_id: int,
    events_path: Path,
) -> int:
    """Carga eventos de un partido usando COPY binario. Devuelve el conteo."""
    from genbi_data.ingest.flatten import flatten_events

    raw_events: list[dict[str, Any]] = json.loads(events_path.read_text())
    flattened = flatten_events(match_id, raw_events, cache)

    if not flattened:
        return 0

    # COPY binario para event
    event_rows = []
    for ev in flattened:
        event_rows.append(
            (
                uuid.UUID(ev["event_id"]) if isinstance(ev["event_id"], str) else ev["event_id"],
                ev["match_id"],
                ev["index"],
                ev["period"],
                ev["timestamp"],
                ev["minute"],
                ev["second"],
                ev["type_id"],
                ev.get("possession"),
                ev.get("possession_team_id"),
                ev.get("play_pattern_id"),
                ev.get("team_id"),
                ev.get("player_id"),
                ev.get("position_id"),
                ev.get("location_x"),
                ev.get("location_y"),
                ev.get("duration"),
                ev.get("under_pressure"),
                ev.get("off_camera"),
                ev.get("out"),
            )
        )

    columns = [
        "event_id",
        "match_id",
        "index",
        "period",
        "timestamp",
        "minute",
        "second",
        "type_id",
        "possession",
        "possession_team_id",
        "play_pattern_id",
        "team_id",
        "player_id",
        "position_id",
        "location_x",
        "location_y",
        "duration",
        "under_pressure",
        "off_camera",
        "out",
    ]

    with conn.cursor() as cur:
        # Usar COPY para inserción masiva
        buf = BytesIO()
        for row in event_rows:
            line = "\t".join(_copy_val(v) for v in row) + "\n"
            buf.write(line.encode())
        buf.seek(0)
        with cur.copy(f"COPY oltp ({', '.join(columns)}) FROM STDIN WITH (FORMAT text)") as copy:
            copy.write(buf.read())

    # Subtipos
    _load_event_subtypes(conn, flattened)

    return len(event_rows)


def _copy_val(v: Any) -> str:
    """Convierte un valor para COPY text (NULL = \\N)."""
    if v is None:
        return "\\N"
    if isinstance(v, bool):
        return "t" if v else "f"
    if isinstance(v, uuid.UUID):
        return str(v)
    return str(v)


def _load_event_subtypes(conn: psycopg.Connection, flattened: list[dict[str, Any]]) -> None:
    """Inserta subtipos de evento (pass, shot, carry, etc.)."""
    from genbi_data.ingest.flatten import SUBTYPE_TABLE_MAP

    # Agrupar por tabla de subtipo
    by_table: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in flattened:
        subtype = ev.get("_subtype")
        if subtype and subtype in SUBTYPE_TABLE_MAP:
            by_table[SUBTYPE_TABLE_MAP[subtype]].append(ev)

    for table, evs in by_table.items():
        _copy_subtype_table(conn, table, evs)


def _copy_subtype_table(conn: psycopg.Connection, table: str, evs: list[dict[str, Any]]) -> None:
    """Carga filas de una tabla de subtipo via COPY."""
    from genbi_data.ingest.flatten import SUBTYPE_COLUMNS

    if table not in SUBTYPE_COLUMNS:
        return

    cols = SUBTYPE_COLUMNS[table]
    with conn.cursor() as cur:
        buf = BytesIO()
        for ev in evs:
            vals = []
            for col in cols:
                if col == "event_id":
                    vals.append(
                        str(
                            uuid.UUID(ev["event_id"])
                            if isinstance(ev["event_id"], str)
                            else ev["event_id"]
                        )
                    )
                else:
                    v = ev.get(f"_sub_{col}")
                    vals.append(_copy_val(v))
            line = "\t".join(vals) + "\n"
            buf.write(line.encode())
        buf.seek(0)
        with cur.copy(
            f"COPY oltp.{table} ({', '.join(cols)}) FROM STDIN WITH (FORMAT text)"
        ) as copy:
            copy.write(buf.read())


# ---------------------------------------------------------------------------
# Main entry: load one match file
# ---------------------------------------------------------------------------


@dataclass
class LoadResult:
    """Resultado de cargar un archivo de partido."""

    match_id: int
    events_count: int
    lineups_count: int


def load_match_file(
    conn: psycopg.Connection,
    cache: EntityCache,
    match_path: Path,
    events_path: Path | None = None,
    lineups_path: Path | None = None,
) -> LoadResult | None:
    """Carga un partido completo en OLTP (transacción atómica).

    Devuelve None si el match_id ya existe (idempotencia).
    """
    match_data: list[dict[str, Any]] = json.loads(match_path.read_text())
    if not match_data:
        return None

    raw_match = match_data[0]  # Un match por archivo de temporada
    m = Match.model_validate(raw_match)

    # Verificar idempotencia: si el match ya existe, skip
    existing = conn.execute(
        "SELECT 1 FROM oltp.match WHERE match_id = %s", (m.match_id,)
    ).fetchone()
    if existing:
        logger.debug("match %d already loaded, skipping", m.match_id)
        return None

    try:
        # Resolución de entidades maestras
        _resolve_match_masters(conn, cache, m)

        # Insertar match
        _insert_match(conn, m)
        _insert_match_managers(conn, m)

        # Alineaciones
        lineups_count = 0
        if lineups_path and lineups_path.is_file():
            lineups_data: list[dict] = json.loads(lineups_path.read_text())
            for raw_lineup in lineups_data:
                lu = TeamLineup.model_validate(raw_lineup)
                _resolve_lineup_masters(conn, cache, lu)
                _insert_lineup(conn, m.match_id, lu)
                lineups_count += 1

        # Eventos
        events_count = 0
        if events_path and events_path.is_file():
            events_count = _load_events_for_match(conn, cache, m.match_id, events_path)

        return LoadResult(
            match_id=m.match_id,
            events_count=events_count,
            lineups_count=lineups_count,
        )
    except Exception:
        conn.rollback()
        raise
