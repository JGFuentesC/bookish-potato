"""CLI del runner: ``python -m genbi_data.runner [--layer gold] [--select MODEL]``."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]

    layer = "gold"
    select: str | None = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--layer" and i + 1 < len(args):
            layer = args[i + 1]
            i += 2
        elif arg == "--select" and i + 1 < len(args):
            select = args[i + 1]
            i += 2
        elif arg in ("-h", "--help"):
            print("uso: runner --layer bronze|silver|gold [--select MODEL]")
            return 0
        else:
            raise ValueError(f"argumento desconocido: {arg!r}")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    current = Path(__file__).resolve().parent
    for _ in range(6):
        if (current / "Makefile").is_file():
            break
        current = current.parent
    root = current

    models_dir = root / "data-platform" / "models"
    lakehouse_dir = root / "lakehouse"

    from genbi_data.runner.execute import build_layer

    result = build_layer(models_dir, lakehouse_dir, layer=layer, select=select)

    print(f"\nlayer {layer}: {len(result.models)} modelos construidos")
    for m in result.models:
        print(f"  {m.name:24s} filas={m.rows:>12,}  {m.duration_seconds:5.1f}s  tests={len(m.quality.results)}")
    if result.warnings:
        print(f"warnings de calidad: {result.warnings}")
    if result.failed:
        print(f"errores de calidad: {', '.join(result.failed)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())