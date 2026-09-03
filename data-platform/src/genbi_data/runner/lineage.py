"""Linaje del lakehouse: diagrama Mermaid (PRD E2-H1-T4, ``make lineage``)."""

from __future__ import annotations

from pathlib import Path

from genbi_data.runner.execute import load_contracts


def build_lineage(models_dir: Path, layers: list[str]) -> str:
    """Genera un diagrama Mermaid del DAG entre modelos de las capas dadas."""
    contracts: dict[str, object] = {}
    for layer in layers:
        contracts.update(load_contracts(models_dir, layer))

    lines = ["```mermaid", "flowchart LR"]
    for name in contracts:
        lines.append(f"    {name}[{name}]")
    for name, contract in contracts.items():
        for dep in contract.depends_on:
            lines.append(f"    {dep} --> {name}")
    lines.append("```")
    return "\n".join(lines)


def main(models_dir: Path, out_file: Path) -> int:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(build_lineage(models_dir, ["bronze", "silver", "gold"]) + "\n")
    print(f"lineage escrito en {out_file}")
    return 0