"""Pruebas de descarga (PRD E1-H2 T2): payload del subset e idempotencia por hash."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from genbi_data.ingest.fetch import (
    NotModified,
    SubsetSeason,
    _download,
    build_payload,
    load_subset,
    sha256_of,
)

MOCK_CONFIG = """\
scope: subset
competitions:
  - competition_id: 11
    season_ids: [90, 42]
"""


def test_load_subset_lee_config(tmp_path: Path) -> None:
    cfg = tmp_path / "subset.yaml"
    cfg.write_text(MOCK_CONFIG)
    seasons = load_subset(cfg)
    assert seasons == [SubsetSeason(competition_id=11, season_ids=(90, 42))]


def test_build_payload_por_partido() -> None:
    cache = {"11/90": [1, 2, 3]}
    payload = build_payload("https://x/", [SubsetSeason(11, (90,))], cache)
    relpaths = [rel for rel, _url in payload]
    # competiciones + 3 partidos x 3 entidades (events, lineups, three-sixty)
    assert "data/competitions.json" in relpaths
    assert len(relpaths) == 1 + 3 * 3
    assert "data/events/2.json" in relpaths
    assert "data/three-sixty/3.json" in relpaths


def test_download_omite_si_hash_coincide(tmp_path: Path) -> None:
    """T2.3: si el archivo ya está con el mismo SHA-256, no vuelve a descargar."""
    dest = tmp_path / "data.bin"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(b"contenido estable")
    with pytest.raises(NotModified):
        _download("http://no-se-consulta/", dest, sha256_of(dest))


def test_download_descarga_y_hash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    body = b"hola-statsbomb"
    monkeypatch.setattr("genbi_data.ingest.fetch._open_url", lambda _url: io.BytesIO(body))
    dest = tmp_path / "nested" / "f.json"
    sha = _download("http://x/f.json", dest, None)
    assert dest.read_bytes() == body
    assert sha == sha256_of(dest)
