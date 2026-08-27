"""Descarga del dataset StatsBomb (Open Data / Hudl) a ``data/raw/`` (PRD E1-H2, RF-01/RF-08).

Modos (``--scope``):
- ``subset``: baja únicamente las competición-temporada declaradas en
  ``config/subset.yaml`` (ruta crítica). Reutiliza archivos ya presentes cuyo
  SHA-256 coincide con el ``manifest.json`` (no vuelve a descargar).
- ``full``: clona/sincroniza el repositorio completo con ``git``.

Cada archivo descargado queda registrado con su SHA-256 en ``data/raw/manifest.json``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, BinaryIO

import yaml

RAW_BASE = "https://raw.githubusercontent.com/hudl/open-data/master/data/"
REPO_URL = "https://github.com/hudl/open-data.git"

# entidades por match_id: (relpath bajo data/, subdirectorio)
_ENTITIES: tuple[str, ...] = ("events", "lineups", "three-sixty")


@dataclass(frozen=True)
class SubsetSeason:
    """Competición-temporada de la ruta crítica (config/subset.yaml)."""

    competition_id: int
    season_ids: tuple[int, ...]


def load_subset(config_path: Path) -> list[SubsetSeason]:
    """Lee ``config/subset.yaml`` y devuelve sus competición-temporada."""
    data = yaml.safe_load(config_path.read_text())
    comps = data["competitions"]
    if not isinstance(comps, list) or not comps:
        raise ValueError(f"{config_path}: 'competitions' debe ser una lista no vacía")
    seasons: list[SubsetSeason] = []
    for item in comps:
        competition_id = int(item["competition_id"])
        season_ids = tuple(int(s) for s in item["season_ids"])
        if not season_ids:
            raise ValueError(f"{config_path}: competition {competition_id} sin season_ids")
        seasons.append(SubsetSeason(competition_id, season_ids))
    return seasons


def sha256_of(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


class HttpError(Exception):
    """Error de red al recuperar una URL."""


class NotModified(Exception):
    """El archivo ya está en disco con el SHA-256 esperado (no se vuelve a bajar)."""


def _open_url(url: str) -> BinaryIO:
    try:
        return urllib.request.urlopen(url, timeout=60)  # type: ignore[no-any-return]
    except Exception as exc:  # pragma: no cover - red no determinista
        raise HttpError(f"no se pudo abrir {url}: {exc}") from exc


class _ResponseContext:
    """Cierre determinista del cuerpo descargado."""

    def __init__(self, handle: Any) -> None:
        self._handle = handle

    def __enter__(self) -> Any:
        return self._handle

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        close = getattr(self._handle, "close", None)
        if close is not None:
            close()


def _download(url: str, dest: Path, expected_sha: str | None) -> str:
    """Descarga ``url`` a ``dest`` (atómicamente, vía `.part`) y devuelve su SHA-256.

    Si ``dest`` ya existe con el hash ``expected_sha``, no descarga (idempotencia, T2.3).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and expected_sha is not None and sha256_of(dest) == expected_sha:
        raise NotModified
    handle = _open_url(url)
    with _ResponseContext(handle):
        tmp = dest.with_suffix(dest.suffix + ".part")
        digest = hashlib.sha256()
        with tmp.open("wb") as out:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
                out.write(chunk)
        actual = digest.hexdigest()
        tmp.replace(dest)
    return actual


def build_payload(
    raw_base: str, seasons: list[SubsetSeason], match_cache: dict[str, list[int]]
) -> list[tuple[str, str]]:
    """Devuelve ``(relpath, url)`` de todos los ficheros del subset.

    Requiere los ids de partido ya resueltos en ``match_cache`` (clave ``cid/season``).
    """
    payload: list[tuple[str, str]] = [("data/competitions.json", raw_base + "competitions.json")]
    for season_item in seasons:
        for season in season_item.season_ids:
            key = f"{season_item.competition_id}/{season}"
            for mid in match_cache[key]:
                for entity in _ENTITIES:
                    rel = f"data/{entity}/{mid}.json"
                    payload.append((rel, raw_base + f"{entity}/{mid}.json"))
    return payload


def _read_match_ids(match_file: Path) -> list[int]:
    records = json.loads(match_file.read_text())
    return [int(record["match_id"]) for record in records]


def _load_manifest(raw_root: Path) -> dict[str, str]:
    manifest_path = raw_root / "manifest.json"
    if not manifest_path.is_file():
        return {}
    data = json.loads(manifest_path.read_text())
    return dict(data.get("files", {}))


def _write_manifest(
    raw_root: Path, entries: dict[str, str], scope: str, subset: dict[str, Any]
) -> None:
    (raw_root / "manifest.json").write_text(
        json.dumps(
            {"scope": scope, "subset": subset, "files": entries}, ensure_ascii=False, indent=2
        )
    )


def run(
    raw_root: Path,
    scope: str,
    config_path: Path | None = None,
    raw_base: str = RAW_BASE,
    workers: int = 8,
) -> dict[str, int]:
    """Ejecuta la descarga. Devuelve ``{descargado, cacheado, omitido}``."""
    counts = {"descargado": 0, "cacheado": 0, "omitido": 0}
    manifest = _load_manifest(raw_root)

    if scope == "full":
        _git_sync(raw_root)
        payload = _full_payload(raw_root)
    elif scope == "subset":
        if config_path is None or not config_path.is_file():
            raise FileNotFoundError(f"config/subset.yaml no encontrado: {config_path}")
        seasons = load_subset(config_path)
        payload = _resolve_subset_payload(raw_root, raw_base, seasons, manifest, counts)
    else:
        raise ValueError(f"SCOPE inválido: {scope!r} (use subset|full)")

    def _fetch(item: tuple[str, str]) -> None:
        rel, url = item
        expected = manifest.get(rel)
        try:
            sha = _download(url, raw_root / rel, expected)
            if sha != expected:
                manifest[rel] = sha
                counts["descargado"] += 1
            else:
                counts["cacheado"] += 1
        except NotModified:
            counts["cacheado"] += 1
        except HttpError:
            # p. ej. three-sixty que aún no existe para ese partido -> 404
            counts["omitido"] += 1

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in pool.map(_fetch, payload):
            pass

    subset_dict: dict[str, Any] = {}
    if scope == "subset" and config_path is not None and config_path.is_file():
        subset_dict = yaml.safe_load(config_path.read_text())
    _write_manifest(raw_root, dict(manifest), scope, subset_dict)
    return counts


def _resolve_subset_payload(
    raw_root: Path,
    raw_base: str,
    seasons: list[SubsetSeason],
    manifest: dict[str, str],
    counts: dict[str, int],
) -> list[tuple[str, str]]:
    """Descarga competicions + matches del subset y devuelve el payload de eventos etc."""
    # competitions.json
    try:
        sha = _download(raw_base + "competitions.json", raw_root / "data/competitions.json", None)
        if sha != manifest.get("data/competitions.json"):
            manifest["data/competitions.json"] = sha
            counts["descargado"] += 1
        else:
            counts["cacheado"] += 1
    except NotModified:
        counts["cacheado"] += 1

    match_cache: dict[str, list[int]] = {}
    for season_item in seasons:
        for season in season_item.season_ids:
            rel = f"data/matches/{season_item.competition_id}/{season}.json"
            url = raw_base + f"matches/{season_item.competition_id}/{season}.json"
            expected = manifest.get(rel)
            try:
                sha = _download(url, raw_root / rel, expected)
                if sha != expected:
                    manifest[rel] = sha
                    counts["descargado"] += 1
                else:
                    counts["cacheado"] += 1
            except NotModified:
                counts["cacheado"] += 1
            match_cache[f"{season_item.competition_id}/{season}"] = _read_match_ids(raw_root / rel)
    return build_payload(raw_base, seasons, match_cache)


def _git_sync(raw_root: Path) -> None:
    if (raw_root / ".git").exists():
        subprocess.run(["git", "-C", str(raw_root), "pull", "--rebase"], check=True)
    else:
        raw_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", REPO_URL, str(raw_root)], check=True)


def _full_payload(raw_root: Path) -> list[tuple[str, str]]:
    """Tras clonar, 'descarga' = indexar los JSON ya presentes bajo ``raw_root/data/``."""
    payload: list[tuple[str, str]] = []
    data_dir = raw_root / "data"
    if not data_dir.is_dir():
        raise FileNotFoundError(f"{data_dir}: repositorio no clonado (scope=full)")
    for path in data_dir.rglob("*.json"):
        payload.append((str(path.relative_to(raw_root)), str(path)))
    return payload


def _project_root() -> Path:
    """Raíz del monorepo (donde vive el Makefile), subiendo desde este módulo."""
    current = Path(__file__).resolve().parent
    for _ in range(6):
        if (current / "Makefile").is_file():
            return current
        current = current.parent
    return Path.cwd()


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    scope, workers = "subset", 8
    config_path = _project_root() / "config" / "subset.yaml"
    raw_root = _project_root() / "data" / "raw"
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--scope" and i + 1 < len(args):
            scope = args[i + 1]
            i += 2
        elif arg == "--config" and i + 1 < len(args):
            config_path = Path(args[i + 1])
            i += 2
        elif arg == "--data-raw" and i + 1 < len(args):
            raw_root = Path(args[i + 1])
            i += 2
        elif arg == "--workers" and i + 1 < len(args):
            workers = int(args[i + 1])
            i += 2
        elif arg in ("-h", "--help"):
            print("uso: fetch --scope subset|full [--config subset.yaml] [--data-raw data/raw]")
            return 0
        else:
            raise ValueError(f"argumento desconocido: {arg!r}")
    counts = run(raw_root, scope, config_path, workers=workers)
    print(
        f"data-pull {scope}: descargado={counts['descargado']} "
        f"cacheado={counts['cacheado']} omitido={counts['omitido']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
