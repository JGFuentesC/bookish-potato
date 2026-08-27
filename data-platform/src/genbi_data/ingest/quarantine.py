"""Cuarentena de datos malformados (PRD E1-H2 T3).

Valida cada archivo del subset contra su contrato Pydantic y, cuando un registro
no valida, lo escribe en ``data/quarantine/{entity}/{file}.jsonl`` con:
- ``error_path``: ruta del campo que falla (loc de la ValidationError),
- ``error_type``: tipo de error Pydantic (p. ej. ``extra_forbidden``,
  ``int_parsing``, ``value_error``),
- ``raw_record``: el registro tal cual llegó (para auditoría).

El resto del archivo continúa procesándose (el error no aborta el lote).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from genbi_data.contracts.statsbomb import (
    CompetitionSeason,
    Event,
    Match,
    TeamLineup,
    ThreeSixty,
)


@dataclass(frozen=True)
class Issue:
    """Un registro inválido y por qué no validó."""

    index: int
    error_path: str
    error_type: str
    message: str
    raw_record: dict[str, Any]


def issue_for(model: type[BaseModel], record: dict[str, Any], index: int) -> Issue | None:
    """Valida ``record`` contra ``model``; devuelve un Issue o None si es válido."""
    try:
        model.model_validate(record)
    except ValidationError as exc:
        error = exc.errors()[0]
        loc = error.get("loc", ())
        return Issue(
            index=index,
            error_path=".".join(str(part) for part in loc) or "<root>",
            error_type=str(error.get("type", "validation_error")),
            message=error.get("msg", str(exc)),
            raw_record=dict(record),
        )
    return None


def default_loader(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())  # type: ignore[no-any-return]


def scan_file(
    model: type[BaseModel],
    file_path: Path,
    qroot: Path,
    entity: str,
    records: list[dict[str, Any]],
) -> tuple[int, int]:
    """Valida los registros de un archivo y escribe los inválidos a cuarentena.

    Devuelve ``(registros_ok, registros_cuarentena)``; los inválidos no abortan
    el resto del lote.
    """
    dest = qroot / entity / f"{file_path.stem}.jsonl"
    ok = 0
    quarantined = 0
    for index, record in enumerate(records):
        issue = issue_for(model, record, index)
        if issue is None:
            ok += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "error_path": issue.error_path,
                        "error_type": issue.error_type,
                        "message": issue.message,
                        "index": issue.index,
                        "raw_record": issue.raw_record,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        quarantined += 1
    return ok, quarantined


ENTITY_MODEL: dict[str, type[BaseModel]] = {
    "competitions": CompetitionSeason,
    "matches": Match,
    "lineups": TeamLineup,
    "three-sixty": ThreeSixty,
    "events": Event,
}


def scan_entity(
    entity: str,
    files: Iterable[Path],
    qroot: Path,
    loader: Callable[[Path], list[dict[str, Any]]] = default_loader,
) -> tuple[int, int]:
    """Valida una entidad entera. Devuelve ``(registros_ok, registros_cuarentena)``."""
    model = ENTITY_MODEL[entity]
    total_ok = 0
    total_q = 0
    for path in files:
        ok, q = scan_file(model, path, qroot, entity, loader(path))
        total_ok += ok
        total_q += q
    return total_ok, total_q


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    entity = args[0] if args else "events"
    if entity not in ENTITY_MODEL:
        raise ValueError(f"entidad desconocida: {entity!r} (use {sorted(ENTITY_MODEL)})")
    from genbi_data.ingest.fetch import _project_root

    root = _project_root()
    data_dir = root / "data" / "raw" / "data"
    qroot = root / "data" / "quarantine"
    files = sorted((data_dir / entity).rglob("*.json"))
    ok, quarantined = scan_entity(entity, files, qroot)
    print(f"quarantine {entity}: ok={ok} cuarentena={quarantined}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
