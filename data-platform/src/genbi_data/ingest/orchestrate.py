"""Orquestador de ingesta a OLTP (PRD E1-H3 T3 + T4).

Lee el manifest, ordena por dependencias, carga y registra auditoría
en ingestion_run / ingestion_file.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from genbi_data.contracts.statsbomb import CompetitionSeason, Match, TeamLineup
from genbi_data.ingest.fetch import load_subset
from genbi_data.ingest.flatten import flatten_events
from genbi_data.ingest.loader import (
    EntityCache,
    _ensure_country,
    _ensure_player,
    _insert_lineup,
    _insert_match,
    _insert_match_managers,
    _load_cache,
    _resolve_lineup_masters,
    _resolve_match_masters,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_val(v: Any) -> str:
    if v is None:
        return "\\N"
    if isinstance(v, bool):
        return "t" if v else "f"
    if isinstance(v, uuid.UUID):
        return str(v)
    return str(v)


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _discover_files(raw_root: Path) -> list[dict[str, Any]]:
    data_dir = raw_root / "data"
    files: list[dict[str, Any]] = []

    comp = data_dir / "competitions.json"
    if comp.is_file():
        files.append({"entity": "competitions", "path": comp, "sha": _sha256(comp), "order": 0})

    for sf in sorted((data_dir / "matches").rglob("*.json")):
        rel = sf.relative_to(data_dir)
        cid, sid = int(rel.parts[1]), int(rel.parts[2].replace(".json", ""))
        files.append(
            {
                "entity": "matches",
                "path": sf,
                "sha": _sha256(sf),
                "order": 1,
                "competition_id": cid,
                "season_id": sid,
            }
        )

    for f in sorted((data_dir / "lineups").glob("*.json")):
        files.append(
            {"entity": "lineups", "path": f, "sha": _sha256(f), "order": 2, "match_id": int(f.stem)}
        )

    for f in sorted((data_dir / "events").glob("*.json")):
        files.append(
            {"entity": "events", "path": f, "sha": _sha256(f), "order": 3, "match_id": int(f.stem)}
        )

    return files


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def _create_run(conn: psycopg.Connection, scope: str) -> str:
    row = conn.execute(
        """INSERT INTO oltp.ingestion_run (run_id, started_at, status, scope)
           VALUES (%s, now(), 'running', %s) RETURNING run_id""",
        (str(uuid.uuid4()), scope),
    ).fetchone()
    conn.commit()
    return row[0]  # type: ignore[index]


def _finish_run(
    conn: psycopg.Connection, run_id: str, status: str, files: int, rows: int, errors: list[str]
) -> None:
    conn.execute(
        """UPDATE oltp.ingestion_run
           SET finished_at = now(), status=%s, files_processed=%s,
               rows_written=%s, error_summary=%s
           WHERE run_id=%s""",
        (status, files, rows, "; ".join(errors) if errors else None, run_id),
    )
    conn.commit()


def _record_file(
    conn: psycopg.Connection, run_id: str, path: str, sha: str, entity: str, rows: int, status: str
) -> None:
    conn.execute(
        """INSERT INTO oltp.ingestion_file
           (run_id, source_path, file_sha256, entity, rows, status)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (run_id, path, sha, entity, rows, status),
    )


def _already_processed(conn: psycopg.Connection, sha: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM oltp.ingestion_file WHERE file_sha256=%s AND status='ok'", (sha,)
        ).fetchone()
        is not None
    )


# ---------------------------------------------------------------------------
# Entity loaders (all use cache)
# ---------------------------------------------------------------------------


def _load_competitions(
    conn: psycopg.Connection,
    cache: EntityCache,
    path: Path,
    subset: dict[int, set[int]] | None = None,
) -> int:
    raw: list[dict] = json.loads(path.read_text())
    count = 0
    for item in raw:
        cs = CompetitionSeason.model_validate(item)
        if subset is not None:
            season_ids = subset.get(cs.competition_id)
            if season_ids is None or cs.season_id not in season_ids:
                continue
        _ensure_country(conn, cache, cs.country_name)
        country_id = cache._country[cs.country_name]
        conn.execute(
            """INSERT INTO oltp.competition
               (competition_id, competition_name, country_id, competition_gender, is_youth, is_international)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT (competition_id) DO UPDATE SET competition_name=EXCLUDED.competition_name""",
            (
                cs.competition_id,
                cs.competition_name,
                country_id,
                cs.competition_gender,
                cs.competition_youth,
                cs.competition_international,
            ),
        )
        conn.execute(
            """INSERT INTO oltp.season (season_id, season_name)
               VALUES (%s,%s) ON CONFLICT (season_id) DO UPDATE SET season_name=EXCLUDED.season_name""",
            (cs.season_id, cs.season_name),
        )
        # match_available is timestamptz in DB, str in contract — parse it
        from datetime import datetime

        def _ts(s: str | None) -> datetime | None:
            if not s:
                return None
            try:
                return datetime.fromisoformat(s)
            except ValueError:
                return None

        conn.execute(
            """INSERT INTO oltp.competition_season
               (competition_id, season_id, match_updated, match_available)
               VALUES (%s,%s,%s,%s)
               ON CONFLICT (competition_id, season_id) DO NOTHING""",
            (cs.competition_id, cs.season_id, _ts(cs.match_updated), None),
        )
        count += 1
    return count


def _load_matches_file(conn: psycopg.Connection, cache: EntityCache, path: Path) -> int:
    raw: list[dict] = json.loads(path.read_text())
    rows = 0
    for raw_match in raw:
        m = Match.model_validate(raw_match)
        existing = conn.execute(
            "SELECT 1 FROM oltp.match WHERE match_id=%s", (m.match_id,)
        ).fetchone()
        if existing:
            continue
        _resolve_match_masters(conn, cache, m)
        _insert_match(conn, m)
        _insert_match_managers(conn, m)
        rows += 1
    return rows


def _load_lineups_file(conn: psycopg.Connection, cache: EntityCache, path: Path) -> int:
    match_id = int(path.stem)
    # Verificar que el match exista
    if not conn.execute("SELECT 1 FROM oltp.match WHERE match_id=%s", (match_id,)).fetchone():
        return 0
    raw: list[dict] = json.loads(path.read_text())
    count = 0
    for raw_lu in raw:
        lu = TeamLineup.model_validate(raw_lu)
        _resolve_lineup_masters(conn, cache, lu)
        _insert_lineup(conn, match_id, lu)
        count += 1
    return count


def _upsert_players_from_events(
    conn: psycopg.Connection, cache: EntityCache, raw_events: list[dict]
) -> None:
    """Extrae y upsertea jugadores de los eventos crudos."""
    seen: set[int] = set()
    for raw in raw_events:
        player = raw.get("player")
        if not player or not isinstance(player, dict):
            continue
        pid = player.get("id")
        if not pid or pid in seen or cache._player.get(pid):
            continue
        seen.add(pid)
        pname = player.get("name", f"Player {pid}")
        _ensure_player(conn, cache, pid, pname, None, None)


def _load_event_extras(
    conn: psycopg.Connection, cache: EntityCache, extras: dict[str, list[dict]]
) -> None:
    """Carga event_relation, shot_freeze_frame, tactics_lineup y tactics_player."""
    from io import BytesIO

    # event_relation
    rels = extras.get("relations", [])
    if rels:
        buf = BytesIO()
        for r in rels:
            buf.write(f"{r['event_id']}\t{r['related_event_id']}\n".encode())
        buf.seek(0)
        with (
            conn.cursor() as cur,
            cur.copy(
                "COPY oltp.event_relation (event_id, related_event_id) FROM STDIN WITH (FORMAT text)"
            ) as c,
        ):
            c.write(buf.read())

    # shot_freeze_frame
    ffs = extras.get("freeze_frames", [])
    if ffs:
        buf = BytesIO()
        for f in ffs:
            buf.write(
                (
                    "\t".join(
                        _copy_val(f[k])
                        for k in (
                            "event_id",
                            "frame_idx",
                            "player_id",
                            "is_teammate",
                            "is_actor",
                            "is_keeper",
                            "x",
                            "y",
                        )
                    )
                    + "\n"
                ).encode()
            )
        buf.seek(0)
        with (
            conn.cursor() as cur,
            cur.copy(
                "COPY oltp.shot_freeze_frame "
                "(event_id, frame_idx, player_id, is_teammate, is_actor, is_keeper, x, y) "
                "FROM STDIN WITH (FORMAT text)"
            ) as c,
        ):
            c.write(buf.read())

    # tactics_lineup + tactics_player
    tactics = extras.get("tactics", [])
    if tactics:
        tl_buf = BytesIO()
        tp_buf = BytesIO()
        for t in tactics:
            tl_buf.write(f"{t['event_id']}\t{_copy_val(t['formation_id'])}\n".encode())
            for p in t.get("lineup", []):
                player = p.get("player", {}) or {}
                position = p.get("position", {}) or {}
                pid = player.get("id") if isinstance(player, dict) else None
                if pid is not None:
                    _ensure_player(
                        conn, cache, pid, player.get("name", f"Player {pid}"), None, None
                    )
                tp_buf.write(
                    (
                        "\t".join(
                            _copy_val(v)
                            for v in (
                                t["event_id"],
                                pid,
                                position.get("id"),
                                p.get("jersey_number"),
                            )
                        )
                        + "\n"
                    ).encode()
                )
        tl_buf.seek(0)
        tp_buf.seek(0)
        with (
            conn.cursor() as cur,
            cur.copy(
                "COPY oltp.tactics_lineup (event_id, formation_id) FROM STDIN WITH (FORMAT text)"
            ) as c,
        ):
            c.write(tl_buf.read())
        with (
            conn.cursor() as cur,
            cur.copy(
                "COPY oltp.tactics_player "
                "(event_id, player_id, position_id, jersey_number) FROM STDIN WITH (FORMAT text)"
            ) as c,
        ):
            c.write(tp_buf.read())


def _load_events_file(conn: psycopg.Connection, cache: EntityCache, path: Path) -> int:
    match_id = int(path.stem)
    match_row = conn.execute(
        "SELECT match_date FROM oltp.match WHERE match_id=%s", (match_id,)
    ).fetchone()
    if not match_row:
        return 0
    match_date = str(match_row[0])

    raw_events: list[dict] = json.loads(path.read_text())

    # Upsert players from events (some players only appear in events, not lineups)
    _upsert_players_from_events(conn, cache, raw_events)

    flattened = flatten_events(match_id, raw_events, cache)
    if not flattened:
        return 0

    from io import BytesIO

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

    def _ts(val: str | None) -> str | None:
        if not val:
            return "\\N"
        if "T" in val:
            return val
        return f"{match_date}T{val}"

    buf = BytesIO()
    for ev in flattened:
        row = [
            ev["event_id"],
            ev["match_id"],
            ev["index"],
            ev["period"],
            _ts(ev["timestamp"]),
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
        ]
        buf.write(("\t".join(_copy_val(v) for v in row) + "\n").encode())
    buf.seek(0)

    with (
        conn.cursor() as cur,
        cur.copy(f"COPY oltp.event ({', '.join(columns)}) FROM STDIN WITH (FORMAT text)") as c,
    ):
        c.write(buf.read())

    # Subtipos
    from genbi_data.ingest.flatten import SUBTYPE_COLUMNS, SUBTYPE_TABLE_MAP

    by_table: dict[str, list[dict]] = defaultdict(list)
    for ev in flattened:
        st = ev.get("_subtype")
        if st and st in SUBTYPE_TABLE_MAP:
            by_table[SUBTYPE_TABLE_MAP[st]].append(ev)

    for table, evs in by_table.items():
        if table not in SUBTYPE_COLUMNS:
            continue
        cols = SUBTYPE_COLUMNS[table]
        buf = BytesIO()
        for ev in evs:
            vals = []
            for col in cols:
                if col == "event_id":
                    vals.append(str(ev["event_id"]))
                else:
                    vals.append(_copy_val(ev.get(f"_sub_{col}")))
            buf.write(("\t".join(vals) + "\n").encode())
        buf.seek(0)
        with (
            conn.cursor() as cur,
            cur.copy(f"COPY oltp.{table} ({', '.join(cols)}) FROM STDIN WITH (FORMAT text)") as c,
        ):
            c.write(buf.read())

    # T2.2 + T2.3: event_relation, shot_freeze_frame, tactics_lineup, tactics_player
    from genbi_data.ingest.flatten import extract_event_extras

    inserted_ids = {str(ev["event_id"]) for ev in flattened}
    extras = extract_event_extras(raw_events, inserted_ids)
    _load_event_extras(conn, cache, extras)

    return len(flattened)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


@dataclass
class IngestResult:
    scope: str
    files_processed: int
    matches_loaded: int
    events_loaded: int
    lineups_loaded: int
    skipped: int
    duration_seconds: float
    errors: list[str]


def ingest_data(dsn: str, raw_root: Path, scope: str = "subset", workers: int = 1) -> IngestResult:
    start = time.time()
    errors: list[str] = []

    subset: dict[int, set[int]] | None = None
    if scope == "subset":
        config_path = raw_root.parent.parent / "config" / "subset.yaml"
        subset = {s.competition_id: set(s.season_ids) for s in load_subset(config_path)}

    files = sorted(_discover_files(raw_root), key=lambda f: f["order"])
    logger.info("discovered %d files", len(files))

    with psycopg.connect(dsn) as conn:
        conn.autocommit = False
        run_id = _create_run(conn, scope)
        cache = _load_cache(conn)
        conn.commit()

        fp = 0
        ml = 0
        el = 0
        ll = 0
        sk = 0

        for f in files:
            entity, path, sha = f["entity"], f["path"], f["sha"]
            if _already_processed(conn, sha):
                sk += 1
                continue
            try:
                if entity == "competitions":
                    rows = _load_competitions(conn, cache, path, subset)
                elif entity == "matches":
                    rows = _load_matches_file(conn, cache, path)
                elif entity == "lineups":
                    rows = _load_lineups_file(conn, cache, path)
                elif entity == "events":
                    rows = _load_events_file(conn, cache, path)
                else:
                    rows = 0
                _record_file(conn, run_id, str(path), sha, entity, rows, "ok")
                conn.commit()
                fp += 1
                if entity == "events":
                    el += rows
                    ml += 1
                elif entity == "lineups":
                    ll += rows
                logger.info("[%d/%d] %s %s ok", fp + sk, len(files), entity, path.name)
            except (KeyError, ValueError, TypeError, psycopg.Error) as exc:
                conn.rollback()
                errors.append(f"{entity}/{path.name}: {exc}")
                _record_file(conn, run_id, str(path), sha, entity, 0, "error")
                conn.commit()

        _finish_run(conn, run_id, "success" if not errors else "partial", fp, el + ll + ml, errors)

    dur = time.time() - start
    return IngestResult(scope, fp, ml, el, ll, sk, dur, errors)
