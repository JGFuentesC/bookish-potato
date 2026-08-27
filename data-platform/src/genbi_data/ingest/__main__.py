"""Entry point: ``python -m genbi_data.ingest``."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]

    scope = "subset"
    workers = 1
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--scope" and i + 1 < len(args):
            scope = args[i + 1]
            i += 2
        elif arg == "--workers" and i + 1 < len(args):
            workers = int(args[i + 1])
            i += 2
        elif arg in ("-h", "--help"):
            print("uso: ingest --scope subset|full [--workers N]")
            return 0
        else:
            raise ValueError(f"argumento desconocido: {arg!r}")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Resolver paths
    current = Path(__file__).resolve().parent
    for _ in range(6):
        if (current / "Makefile").is_file():
            break
        current = current.parent
    root = current

    # DSN desde entorno
    import os

    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5433")
    user = os.getenv("PGUSER", "postgres")
    dbname = os.getenv("PGDATABASE", "genbi")
    password = os.getenv("PGPASSWORD", "")
    dsn = f"host={host} port={port} user={user} dbname={dbname} password={password}"

    raw_root = root / "data" / "raw"
    if not raw_root.is_dir():
        print(f"error: {raw_root} no existe — ejecuta 'make data-pull' primero")
        return 1

    from genbi_data.ingest.orchestrate import ingest_data

    result = ingest_data(dsn, raw_root, scope=scope, workers=workers)

    print(
        f"\ningest {result.scope}: "
        f"archivos={result.files_processed} "
        f"partidos={result.matches_loaded} "
        f"eventos={result.events_loaded} "
        f"alineaciones={result.lineups_loaded} "
        f"omitidos={result.skipped} "
        f"duración={result.duration_seconds:.1f}s"
    )
    if result.errors:
        print(f"errores ({len(result.errors)}):")
        for e in result.errors:
            print(f"  - {e}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
