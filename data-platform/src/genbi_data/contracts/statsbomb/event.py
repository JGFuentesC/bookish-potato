"""Contrato de ``events/{match_id}.json`` (StatsBomb Open Data).

El evento es una unión discriminada por ``type.id``: según el id de tipo, el
evento DEBE llevar su objeto de subtipo correspondiente (p. ej. ``pass``,
``shot``, ``carry``) y NO puede llevar otros. Todo campo no declarado en el
esquema cae en cuarentena (``extra="forbid"``, T1.4).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from genbi_data.contracts.statsbomb._common import STRICT, Point, RefTag

# Field de alias: 'pass' y '50_50' son inválidos como identificador Python.

Player = RefTag  # en un evento, ``player`` es ``{id, name}``
EventTypeTag = RefTag


# ---------------------------------------------------------------------------
# Objetos anidados de subtipo (18 = los "18 subtipos" del PRD E1-H2)
# ---------------------------------------------------------------------------


class Pass(BaseModel):
    model_config = STRICT

    end_location: Point | None = None
    recipient: RefTag | None = None
    length: float | None = None
    angle: float | None = None
    height: RefTag | None = None
    body_part: RefTag | None = None
    type: RefTag | None = None
    outcome: RefTag | None = None
    technique: RefTag | None = None
    assisted_shot_id: str | None = None
    aerial_won: bool | None = None
    shot_assist: bool | None = None
    switch: bool | None = None
    cross: bool | None = None
    deflected: bool | None = None
    inswinging: bool | None = None
    through_ball: bool | None = None
    no_touch: bool | None = None
    outswinging: bool | None = None
    miscommunication: bool | None = None
    cut_back: bool | None = None
    goal_assist: bool | None = None
    straight: bool | None = None


class BallReceipt(BaseModel):
    model_config = STRICT

    outcome: RefTag | None = None


class Carry(BaseModel):
    model_config = STRICT

    end_location: Point | None = None


class Duel(BaseModel):
    model_config = STRICT

    type: RefTag | None = None
    outcome: RefTag | None = None


class BallRecovery(BaseModel):
    model_config = STRICT

    recovery_failure: bool | None = None
    offensive: bool | None = None


class Clearance(BaseModel):
    model_config = STRICT

    body_part: RefTag | None = None
    right_foot: bool | None = None
    left_foot: bool | None = None
    aerial_won: bool | None = None
    head: bool | None = None
    other: bool | None = None


class ShotFrame(BaseModel):
    model_config = STRICT

    location: Point
    player: Player
    position: RefTag
    teammate: bool


class Shot(BaseModel):
    model_config = STRICT

    end_location: Point | None = None
    statsbomb_xg: float | None = None
    key_pass_id: str | None = None
    body_part: RefTag | None = None
    type: RefTag | None = None
    outcome: RefTag | None = None
    technique: RefTag | None = None
    freeze_frame: list[ShotFrame] | None = None
    first_time: bool | None = None
    deflected: bool | None = None
    one_on_one: bool | None = None
    aerial_won: bool | None = None
    saved_to_post: bool | None = None
    redirect: bool | None = None
    open_goal: bool | None = None
    follows_dribble: bool | None = None
    saved_off_target: bool | None = None


class Goalkeeper(BaseModel):
    model_config = STRICT

    end_location: Point | None = None
    outcome: RefTag | None = None
    technique: RefTag | None = None
    position: RefTag | None = None
    body_part: RefTag | None = None
    type: RefTag | None = None
    shot_saved_to_post: bool | None = None
    shot_saved_off_target: bool | None = None
    punched_out: bool | None = None
    lost_in_play: bool | None = None
    success_in_play: bool | None = None


class FoulCommitted(BaseModel):
    model_config = STRICT

    type: RefTag | None = None
    card: RefTag | None = None
    penalty: bool | None = None
    advantage: bool | None = None
    offensive: bool | None = None


class FoulWon(BaseModel):
    model_config = STRICT

    penalty: bool | None = None
    defensive: bool | None = None
    advantage: bool | None = None


class Miscontrol(BaseModel):
    model_config = STRICT

    aerial_won: bool | None = None


class Block(BaseModel):
    model_config = STRICT

    deflection: bool | None = None
    offensive: bool | None = None
    save_block: bool | None = None


class Dribble(BaseModel):
    model_config = STRICT

    outcome: RefTag | None = None
    overrun: bool | None = None
    nutmeg: bool | None = None
    no_touch: bool | None = None


class BadBehaviour(BaseModel):
    model_config = STRICT

    card: RefTag | None = None


class Interception(BaseModel):
    model_config = STRICT

    outcome: RefTag | None = None


class Substitution(BaseModel):
    model_config = STRICT

    outcome: RefTag | None = None
    replacement: RefTag | None = None


class InjuryStoppage(BaseModel):
    model_config = STRICT

    in_chain: bool | None = None


class FiftyFifty(BaseModel):
    model_config = STRICT

    outcome: RefTag | None = None


class TacticsLineupEntry(BaseModel):
    model_config = STRICT

    player: Player
    position: RefTag
    jersey_number: int


class Tactics(BaseModel):
    model_config = STRICT

    formation: int
    lineup: list[TacticsLineupEntry]


# ---------------------------------------------------------------------------
# Unión discriminada
# ---------------------------------------------------------------------------

# statsbomb key -> atributo del modelo (alias para nombres inválidos en Python)
_PY_KEY: dict[str, str] = {
    "pass": "pass_",
    "ball_receipt": "ball_receipt",
    "carry": "carry",
    "duel": "duel",
    "ball_recovery": "ball_recovery",
    "clearance": "clearance",
    "shot": "shot",
    "goalkeeper": "goalkeeper",
    "foul_committed": "foul_committed",
    "foul_won": "foul_won",
    "miscontrol": "miscontrol",
    "block": "block",
    "dribble": "dribble",
    "bad_behaviour": "bad_behaviour",
    "interception": "interception",
    "substitution": "substitution",
    "injury_stoppage": "injury_stoppage",
    "50_50": "fifty_fifty",
}

# type.id -> único objeto de subtipo esperado (los 18 subtipos del PRD)
SUBTYPE_BY_TYPE: dict[int, str] = {
    30: "pass",
    42: "ball_receipt",
    43: "carry",
    4: "duel",
    2: "ball_recovery",
    9: "clearance",
    16: "shot",
    23: "goalkeeper",
    22: "foul_committed",
    21: "foul_won",
    38: "miscontrol",
    6: "block",
    14: "dribble",
    24: "bad_behaviour",
    10: "interception",
    19: "substitution",
    40: "injury_stoppage",
    33: "50_50",
}

# type.id -> atributo del modelo con el subtipo permitido
_SUBTYPE_BY_PY: dict[int, str] = {tid: _PY_KEY[key] for tid, key in SUBTYPE_BY_TYPE.items()}

# tipos que llevan ``tactics`` (Starting XI, Tactical Shift) en vez de subtipo
TACTICS_TYPES: frozenset[int] = frozenset({35, 36})

_SUBTYPE_FIELDS = frozenset(_PY_KEY.values())


class Event(BaseModel):
    """Evento StatsBomb. Discriminado por ``type.id`` (model_validator)."""

    model_config = STRICT

    id: str
    index: int
    period: int
    timestamp: str
    minute: int
    second: int
    type: EventTypeTag
    possession: int | None = None
    possession_team: RefTag | None = None
    play_pattern: RefTag | None = None
    team: RefTag | None = None
    player: Player | None = None
    position: RefTag | None = None
    location: Point | None = None
    duration: float | None = None
    under_pressure: bool | None = None
    related_events: list[str] | None = None
    off_camera: bool | None = None
    counterpress: bool | None = None
    out: bool | None = None
    tactics: Tactics | None = None

    # 18 subtipos (alias para 'pass' y '50_50')
    pass_: Annotated[Pass | None, Field(alias="pass")] = None
    ball_receipt: BallReceipt | None = None
    carry: Carry | None = None
    duel: Duel | None = None
    ball_recovery: BallRecovery | None = None
    clearance: Clearance | None = None
    shot: Shot | None = None
    goalkeeper: Goalkeeper | None = None
    foul_committed: FoulCommitted | None = None
    foul_won: FoulWon | None = None
    miscontrol: Miscontrol | None = None
    block: Block | None = None
    dribble: Dribble | None = None
    bad_behaviour: BadBehaviour | None = None
    interception: Interception | None = None
    substitution: Substitution | None = None
    injury_stoppage: InjuryStoppage | None = None
    fifty_fifty: Annotated[FiftyFifty | None, Field(alias="50_50")] = None

    @model_validator(mode="after")
    def _enforce_discriminant(self) -> Event:
        type_id = self.type.id

        if self.tactics is not None and type_id not in TACTICS_TYPES:
            raise ValueError(f"evento tipo {type_id} no puede llevar 'tactics'")
        # un evento solo puede portar el objeto de subtipo que le corresponde a su type.id
        allowed = _SUBTYPE_BY_PY.get(type_id)
        for field in _SUBTYPE_FIELDS:
            if getattr(self, field, None) is not None and field != allowed:
                raise ValueError(f"evento tipo {type_id} lleva objeto '{field}' no permitido")
        return self

    @property
    def type_id(self) -> int:
        return self.type.id
