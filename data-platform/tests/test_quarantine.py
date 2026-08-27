"""Pruebas de cuarentena (PRD E1-H2 T3.1)."""

from __future__ import annotations

import json
from pathlib import Path

from genbi_data.ingest.quarantine import ENTITY_MODEL, issue_for, scan_entity, scan_file

VALID_EVENT = {
    "id": "00000000-0000-0000-0000-000000000001",
    "index": 0,
    "period": 1,
    "timestamp": "00:00:00.000",
    "minute": 0,
    "second": 0,
    "type": {"id": 30, "name": "Pass"},
}


def _write(data_root: Path, records: list[dict[str, object]]) -> Path:
    src = data_root / "events" / "1.json"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(json.dumps(records))
    return src


def test_scan_file_cuarentena_registro_invalido(tmp_path: Path) -> None:
    corrupted = dict(VALID_EVENT)
    corrupted["brand_new_field"] = True  # extra='forbid' -> fallo
    src = _write(tmp_path, [VALID_EVENT, corrupted])

    ok, quarantined = scan_file(
        ENTITY_MODEL["events"], src, tmp_path, "events", [VALID_EVENT, corrupted]
    )

    assert (ok, quarantined) == (1, 1)
    dest = tmp_path / "events" / "1.jsonl"
    assert dest.is_file()
    entry = json.loads(dest.read_text())
    assert entry["error_type"] == "extra_forbidden"
    assert entry["error_path"] == "brand_new_field"
    assert entry["raw_record"] == corrupted


def test_issue_for_tipo_incorrecto() -> None:
    bad = dict(VALID_EVENT)
    bad["index"] = "no-un-entero"
    issue = issue_for(ENTITY_MODEL["events"], bad, 3)
    assert issue is not None
    assert issue.error_path == "index"
    assert issue.index == 3
    assert "int" in issue.error_type  # int_parsing


def test_issue_for_registro_valido_es_none() -> None:
    assert issue_for(ENTITY_MODEL["events"], VALID_EVENT, 0) is None


def test_scan_entity_limpio_sin_cuarentena(tmp_path: Path) -> None:
    src = _write(tmp_path, [dict(VALID_EVENT), dict(VALID_EVENT)])
    ok, quarantined = scan_entity("events", [src], tmp_path)
    assert (ok, quarantined) == (2, 0)
    assert not (tmp_path / "events" / "1.jsonl").exists()
