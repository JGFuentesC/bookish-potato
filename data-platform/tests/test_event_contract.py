"""Contrato del evento: unión discriminada por ``type.id`` (T1.2) y rigor extra='forbid' (T1.4).

Frente a muestras reales del subset:
- Cada uno de los 18 subtipos se cubre con una muestra real y valida sin error.
- Un campo desconocido produce un error de validación tipado (no silencio).
- Un tipo incorrecto en un campo conocido produce error.
- Un evento no puede portar el objeto de subtipo de otro tipo (discriminación).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from genbi_data.contracts.statsbomb import SUBTYPE_BY_TYPE, TACTICS_TYPES, Event
from genbi_data.contracts.statsbomb.event import _PY_KEY

_SUBTYPE_ROWS = sorted(SUBTYPE_BY_TYPE.items())


@pytest.fixture(scope="module")
def samples_by_type(subset_root: Path | None) -> dict[int, dict[str, object]] | None:
    """Una muestra real por type.id (barriendo unos pocos ficheros de eventos)."""
    if subset_root is None:
        return None
    sample: dict[int, dict[str, object]] = {}
    for path in sorted(subset_root.glob("events/*.json"))[:60]:
        for record in json.loads(path.read_text()):
            tid = record["type"]["id"]
            if tid in sample:
                continue
            subkey = SUBTYPE_BY_TYPE.get(tid)
            if subkey is not None and subkey not in record:
                continue  # queremos una muestra que SÍ porta su objeto de subtipo
            sample[tid] = record
    return sample


@pytest.mark.parametrize("type_id,subkey", _SUBTYPE_ROWS)
def test_subtype_muestra_real(
    samples_by_type: dict[int, dict[str, object]] | None, type_id: int, subkey: str
) -> None:
    """T1.2: cada uno de los 18 subtipos valida una muestra real y porta su subtipo."""
    if samples_by_type is None:
        pytest.skip("sin data/raw")
    sample = samples_by_type.get(type_id)
    if sample is None:
        pytest.skip(f"sin muestra real de tipo {type_id}")
    event = Event.model_validate(sample)
    assert event.type_id == type_id
    assert getattr(event, _PY_KEY[subkey]) is not None


def test_event_extra_forbid_campo_desconocido(
    samples_by_type: dict[int, dict[str, object]] | None,
) -> None:
    """T1.4: un campo nuevo (desconocido) es fallo explícito y tipado."""
    if samples_by_type is None:
        pytest.skip("sin data/raw")
    sample = dict(samples_by_type[30])
    sample["brand_new_field"] = True
    with pytest.raises(ValidationError) as info:
        Event.model_validate(sample)
    assert "Extra inputs are not permitted" in str(info.value)


def test_event_tipo_incorrecto(samples_by_type: dict[int, dict[str, object]] | None) -> None:
    """Escenario 'un campo de tipo incorrecto': el registro es rechazado."""
    if samples_by_type is None:
        pytest.skip("sin data/raw")
    sample = dict(samples_by_type[30])
    sample["index"] = "no-soy-un-entero"
    with pytest.raises(ValidationError):
        Event.model_validate(sample)


def test_event_subtipo_de_otro_tipo_rechazado(
    samples_by_type: dict[int, dict[str, object]] | None,
) -> None:
    """Discriminación: un Pass no puede llevar 'shot'."""
    if samples_by_type is None:
        pytest.skip("sin data/raw")
    sample = dict(samples_by_type[30])
    sample["shot"] = {"end_location": [10, 20], "outcome": {"id": 1, "name": "Wayward"}}
    with pytest.raises(ValidationError) as info:
        Event.model_validate(sample)
    assert "no permitido" in str(info.value)


def test_event_tactics_solo_starting_xi(
    samples_by_type: dict[int, dict[str, object]] | None,
) -> None:
    """'tactics' solo está permitido en los tipos 35/36."""
    if samples_by_type is None:
        pytest.skip("sin data/raw")
    for tid, sample in samples_by_type.items():
        if tid in TACTICS_TYPES or "tactics" not in sample:
            continue
        with pytest.raises(ValidationError):
            Event.model_validate(dict(sample))
