"""Fixtures compartidos: acceso a los datos reales del subset (data/raw)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA = REPO_ROOT / "data" / "raw" / "data"


@pytest.fixture(scope="session")
def subset_root() -> Path | None:
    """Raíz de los datos StatsBomb del subset, o None si aún no se corrió data-pull."""
    return DATA if (DATA / "events").is_dir() else None
