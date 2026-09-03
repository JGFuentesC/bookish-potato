"""Genera el catálogo semántico del sidecar desde los contratos gold.

Fuente única: los contratos de data-platform/models/gold/*.yaml.
Salida: ai-sidecar/semantic/catalog.yaml (permite el allow-list del endpoint).
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from genbi_data.runner.execute import load_contracts


def main() -> int:
    root = Path(__file__).resolve().parent
    for _ in range(6):
        if (root / "Makefile").is_file():
            break
        root = root.parent
    contracts = load_contracts(root / "data-platform" / "models", "gold")

    tables = []
    for name in sorted(contracts):
        c = contracts[name]
        tables.append(
            {
                "name": c.name,
                "description": c.description or "",
                "grain": c.grain or "",
                "columns": [
                    {"name": col.name, "type": col.type, "description": col.description or ""}
                    for col in c.columns
                ],
            }
        )

    payload = {"version": 1, "tables": tables}
    out = root / "ai-sidecar" / "semantic" / "catalog.yaml"
    out.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True))
    print(f"catálogo escrito en {out} ({len(tables)} tablas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())