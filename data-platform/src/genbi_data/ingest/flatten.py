"""Aplanado de eventos StatsBomb a esquema OLTP (PRD E1-H3 T2).

Separa el evento base de su especialización (18 subtipos + tactics),
resuelve entidades maestras y prepara las filas para COPY.
"""

from __future__ import annotations

from typing import Any

from genbi_data.contracts.statsbomb import (
    SUBTYPE_BY_TYPE,
    TACTICS_TYPES,
    Event,
)

# ---------------------------------------------------------------------------
# Mapeo subtipo -> tabla OLTP
# ---------------------------------------------------------------------------

SUBTYPE_TABLE_MAP: dict[str, str] = {
    "pass": "event_pass",
    "shot": "event_shot",
    "carry": "event_carry",
    "duel": "event_duel",
    "dribble": "event_dribble",
    "clearance": "event_clearance",
    "interception": "event_interception",
    "goalkeeper": "event_goalkeeper",
    "foul_committed": "event_foul_committed",
    "foul_won": "event_foul_won",
    "block": "event_block",
    "miscontrol": "event_miscontrol",
    "ball_receipt": "event_ball_receipt",
    "bad_behaviour": "event_bad_behaviour",
    "substitution": "event_substitution",
    "50_50": "event_50_50",
    "injury_stoppage": "event_half_start",  # Mapeo simplificado
}

# Columnas por tabla de subtipo
SUBTYPE_COLUMNS: dict[str, list[str]] = {
    "event_pass": [
        "event_id",
        "pass_length",
        "pass_angle",
        "pass_height_id",
        "pass_type_id",
        "technique_id",
        "body_part_id",
        "outcome_id",
        "recipient_id",
        "is_assist",
        "is_shot_assist",
        "is_goal_assist",
    ],
    "event_shot": [
        "event_id",
        "xg",
        "is_goal",
        "shot_type_id",
        "body_part_id",
        "technique_id",
        "outcome_id",
        "first_time",
        "open_goal",
        "deflected",
    ],
    "event_carry": ["event_id", "end_location_x", "end_location_y"],
    "event_duel": ["event_id", "duel_type_id", "outcome_id"],
    "event_dribble": ["event_id", "outcome_id", "overrun", "nutmeg", "no_touch"],
    "event_clearance": ["event_id", "body_part_id", "outcome_id", "under_pressure"],
    "event_interception": ["event_id", "outcome_id"],
    "event_goalkeeper": [
        "event_id",
        "goalkeeper_type_id",
        "outcome_id",
        "technique_id",
        "body_part_id",
    ],
    "event_foul_committed": [
        "event_id",
        "card_type_id",
        "foul_type",
        "advantage",
        "penalty",
    ],
    "event_foul_won": ["event_id", "defensive", "advantage", "penalty"],
    "event_block": ["event_id", "body_part_id", "deflection", "offensive", "saved_shot"],
    "event_miscontrol": ["event_id", "outcome_id"],
    "event_ball_receipt": ["event_id", "outcome_id"],
    "event_bad_behaviour": ["event_id", "card_type_id"],
    "event_substitution": ["event_id", "replacement_id", "outcome_id"],
    "event_50_50": ["event_id", "outcome_id"],
    "event_half_start": ["event_id", "late_video_start"],
}

# ---------------------------------------------------------------------------
# Resolución de catálogos
# ---------------------------------------------------------------------------


def _resolve_catalog_id(
    cache_dict: dict[str, int],
    name: str | None,
) -> int | None:
    if name is None:
        return None
    return cache_dict.get(name)


def _resolve_ref_tag(cache_dict: dict[str, int], ref: Any) -> int | None:
    """Resuelve un RefTag {id, name} a su id."""
    if ref is None:
        return None
    if hasattr(ref, "id"):
        return ref.id
    if isinstance(ref, dict):
        return ref.get("id")
    return None


# ---------------------------------------------------------------------------
# Event base flattening
# ---------------------------------------------------------------------------


def _flatten_event_base(match_id: int, raw: dict[str, Any], cache: Any) -> dict[str, Any]:
    """Extrae las columnas base de un evento."""
    e = Event.model_validate(raw)

    location = e.location
    loc_x = float(location[0]) if location else None
    loc_y = float(location[1]) if location else None

    return {
        "event_id": e.id,
        "match_id": match_id,
        "index": e.index,
        "period": e.period,
        "timestamp": e.timestamp,
        "minute": e.minute,
        "second": float(e.second),
        "type_id": e.type_id,
        "possession": e.possession,
        "possession_team_id": _resolve_ref_tag(cache._team, e.possession_team),
        "play_pattern_id": _resolve_ref_tag(cache._play_pattern, e.play_pattern),
        "team_id": _resolve_ref_tag(cache._team, e.team),
        "player_id": _resolve_ref_tag(cache._player, e.player),
        "position_id": _resolve_ref_tag(cache._position, e.position),
        "location_x": loc_x,
        "location_y": loc_y,
        "duration": e.duration,
        "under_pressure": e.under_pressure,
        "off_camera": e.off_camera,
        "out": e.out,
        "_raw": raw,  # Para subtipos
        "_subtype": None,
    }


# ---------------------------------------------------------------------------
# Subtype extraction
# ---------------------------------------------------------------------------


def _extract_subtype_fields(e: Event, raw: dict[str, Any], cache: Any) -> dict[str, Any]:
    """Extrae campos del subtipo correspondiente al type_id."""
    subtype_name = SUBTYPE_BY_TYPE.get(e.type_id)
    if subtype_name is None and e.type_id not in TACTICS_TYPES:
        return {}

    result: dict[str, Any] = {"_subtype": subtype_name}

    if subtype_name == "pass" and e.pass_:
        p = e.pass_
        result.update(
            {
                "_sub_pass_length": p.length,
                "_sub_pass_angle": p.angle,
                "_sub_pass_height_id": _resolve_ref_tag(cache._pass_height, p.height),
                "_sub_pass_type_id": _resolve_ref_tag(cache._pass_type, p.type),
                "_sub_technique_id": _resolve_ref_tag(cache._technique, p.technique),
                "_sub_body_part_id": _resolve_ref_tag(cache._body_part, p.body_part),
                "_sub_outcome_id": _resolve_ref_tag(cache._outcome, p.outcome),
                "_sub_recipient_id": _resolve_ref_tag(cache._player, p.recipient),
                "_sub_is_assist": p.goal_assist,
                "_sub_is_shot_assist": p.shot_assist,
                "_sub_is_goal_assist": p.goal_assist,
            }
        )
    elif subtype_name == "shot" and e.shot:
        s = e.shot
        result.update(
            {
                "_sub_xg": s.statsbomb_xg,
                "_sub_is_goal": s.outcome.name == "Goal" if s.outcome else None,
                "_sub_shot_type_id": _resolve_ref_tag(cache._shot_type, s.type),
                "_sub_body_part_id": _resolve_ref_tag(cache._body_part, s.body_part),
                "_sub_technique_id": _resolve_ref_tag(cache._technique, s.technique),
                "_sub_outcome_id": _resolve_ref_tag(cache._outcome, s.outcome),
                "_sub_first_time": s.first_time,
                "_sub_open_goal": s.open_goal,
                "_sub_deflected": s.deflected,
            }
        )
    elif subtype_name == "carry" and e.carry:
        end = e.carry.end_location
        result.update(
            {
                "_sub_end_location_x": float(end[0]) if end else None,
                "_sub_end_location_y": float(end[1]) if end else None,
            }
        )
    elif subtype_name == "duel" and e.duel:
        d = e.duel
        result.update(
            {
                "_sub_duel_type_id": _resolve_ref_tag(cache._duel_type, d.type),
                "_sub_outcome_id": _resolve_ref_tag(cache._outcome, d.outcome),
            }
        )
    elif subtype_name == "dribble" and e.dribble:
        dr = e.dribble
        result.update(
            {
                "_sub_outcome_id": _resolve_ref_tag(cache._outcome, dr.outcome),
                "_sub_overrun": dr.overrun,
                "_sub_nutmeg": dr.nutmeg,
                "_sub_no_touch": dr.no_touch,
            }
        )
    elif subtype_name == "clearance" and e.clearance:
        c = e.clearance
        result.update(
            {
                "_sub_body_part_id": _resolve_ref_tag(cache._body_part, c.body_part),
                "_sub_outcome_id": None,
                "_sub_under_pressure": None,
            }
        )
    elif subtype_name == "interception" and e.interception:
        result.update(
            {
                "_sub_outcome_id": _resolve_ref_tag(cache._outcome, e.interception.outcome),
            }
        )
    elif subtype_name == "goalkeeper" and e.goalkeeper:
        g = e.goalkeeper
        result.update(
            {
                "_sub_goalkeeper_type_id": _resolve_ref_tag(cache._goalkeeper_type, g.type),
                "_sub_outcome_id": _resolve_ref_tag(cache._outcome, g.outcome),
                "_sub_technique_id": _resolve_ref_tag(cache._technique, g.technique),
                "_sub_body_part_id": _resolve_ref_tag(cache._body_part, g.body_part),
            }
        )
    elif subtype_name == "foul_committed" and e.foul_committed:
        fc = e.foul_committed
        result.update(
            {
                "_sub_card_type_id": _resolve_ref_tag(cache._card_type, fc.card),
                "_sub_foul_type": fc.type.name if fc.type else None,
                "_sub_advantage": fc.advantage,
                "_sub_penalty": fc.penalty,
            }
        )
    elif subtype_name == "foul_won" and e.foul_won:
        fw = e.foul_won
        result.update(
            {
                "_sub_defensive": fw.defensive,
                "_sub_advantage": fw.advantage,
                "_sub_penalty": fw.penalty,
            }
        )
    elif subtype_name == "block" and e.block:
        b = e.block
        result.update(
            {
                "_sub_body_part_id": None,
                "_sub_deflection": b.deflection,
                "_sub_offensive": b.offensive,
                "_sub_saved_shot": None,
            }
        )
    elif subtype_name == "miscontrol" and e.miscontrol:
        result.update(
            {
                "_sub_outcome_id": None,
            }
        )
    elif subtype_name == "ball_receipt" and e.ball_receipt:
        result.update(
            {
                "_sub_outcome_id": _resolve_ref_tag(cache._outcome, e.ball_receipt.outcome),
            }
        )
    elif subtype_name == "bad_behaviour" and e.bad_behaviour:
        result.update(
            {
                "_sub_card_type_id": _resolve_ref_tag(cache._card_type, e.bad_behaviour.card),
            }
        )
    elif subtype_name == "substitution" and e.substitution:
        s = e.substitution
        result.update(
            {
                "_sub_replacement_id": _resolve_ref_tag(cache._player, s.replacement),
                "_sub_outcome_id": _resolve_ref_tag(cache._outcome, s.outcome),
            }
        )
    elif subtype_name == "50_50" and e.fifty_fifty:
        result.update(
            {
                "_sub_outcome_id": _resolve_ref_tag(cache._outcome, e.fifty_fifty.outcome),
            }
        )

    return result


# ---------------------------------------------------------------------------
# Related events + tactics + freeze_frame
# ---------------------------------------------------------------------------


def _extract_related_events(raw: dict[str, Any]) -> list[tuple[str, str]]:
    """Extrae pares (event_id, related_event_id) del campo related_events."""
    related = raw.get("related_events", [])
    event_id = raw.get("id", "")
    pairs = []
    for rel_id in related:
        pairs.append((event_id, rel_id))
    return pairs


def _extract_tactics(raw: dict[str, Any], event_id: str, cache: Any) -> dict[str, Any] | None:
    """Extrae datos de tactics para eventos tipo 35/36."""
    tactics = raw.get("tactics")
    if not tactics:
        return None
    formation = tactics.get("formation")
    return {
        "event_id": event_id,
        "_formation_id": formation,
        "_lineup": tactics.get("lineup", []),
    }


def _extract_freeze_frame(raw: dict[str, Any], event_id: str) -> list[dict[str, Any]]:
    """Extrae freeze_frame de un evento shot."""
    shot = raw.get("shot", {})
    ff = shot.get("freeze_frame", [])
    rows = []
    for i, frame in enumerate(ff):
        loc = frame.get("location", [None, None])
        rows.append(
            {
                "event_id": event_id,
                "frame_idx": i,
                "player_id": frame.get("player", {}).get("id")
                if isinstance(frame.get("player"), dict)
                else None,
                "is_teammate": frame.get("teammate"),
                "is_actor": frame.get("actor"),
                "is_keeper": frame.get("keeper"),
                "x": float(loc[0]) if loc[0] is not None else None,
                "y": float(loc[1]) if loc[1] is not None else None,
            }
        )
    return rows


def extract_event_extras(
    raw_events: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Extrae event_relation, shot_freeze_frame y tactics_* de los eventos crudos.

    Devuelve dict con claves "relations", "freeze_frames" y "tactics" (listas de filas).
    """
    relations: list[dict[str, Any]] = []
    freeze_frames: list[dict[str, Any]] = []
    tactics: list[dict[str, Any]] = []
    for raw in raw_events:
        event_id = raw.get("id", "")
        if not event_id:
            continue
        for src, rel_id in _extract_related_events(raw):
            relations.append({"event_id": src, "related_event_id": rel_id})
        freeze_frames.extend(_extract_freeze_frame(raw, event_id))
        t = raw.get("tactics")
        if isinstance(t, dict):
            tactics.append(
                {
                    "event_id": event_id,
                    "formation_id": t.get("formation"),
                    "lineup": t.get("lineup", []),
                }
            )
    return {"relations": relations, "freeze_frames": freeze_frames, "tactics": tactics}


# ---------------------------------------------------------------------------
# Main flatten function
# ---------------------------------------------------------------------------


def flatten_events(
    match_id: int,
    raw_events: list[dict[str, Any]],
    cache: Any,
) -> list[dict[str, Any]]:
    """Aplana una lista de eventos crudos a filas OLTP.

    Devuelve lista de dicts con columnas base + _subtype + _sub_* fields.
    """
    flattened = []
    for raw in raw_events:
        try:
            flat = _flatten_event_base(match_id, raw, cache)
            subtype_fields = _extract_subtype_fields(Event.model_validate(raw), raw, cache)
            flat.update(subtype_fields)
            flattened.append(flat)
        except (KeyError, ValueError, TypeError) as exc:
            # Log y skip evento malformado (no aborta el lote)
            import logging

            logging.getLogger(__name__).warning(
                "skip malformed event in match %d: %s (%s)", match_id, raw.get("id", "?"), exc
            )
    return flattened
