"""Motor de ejecución de modelos a Parquet (PRD E2-H1-T2.2).

Lee los contratos YAML de ``models/{layer}/``, ordena por dependencias,
ejecuta el SQL en DuckDB (conectado a Postgres OLTP), corre las pruebas
de calidad y materializa a ``lakehouse/{layer}/{model}/`` en Parquet.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import psycopg
import yaml

from genbi_data.quality.tests import QualityReport, run_model_tests
from genbi_data.runner.contracts import DataContract
from genbi_data.runner.dag import topological_order

logger = logging.getLogger(__name__)


@dataclass
class ModelResult:
    name: str
    rows: int
    duration_seconds: float
    quality: QualityReport


@dataclass
class LayerResult:
    layer: str
    models: list[ModelResult] = field(default_factory=list)

    @property
    def failed(self) -> list[str]:
        return [m.name for m in self.models if m.quality.errors]

    @property
    def warnings(self) -> int:
        return sum(len(m.quality.warnings) for m in self.models)


def load_contracts(models_dir: Path, layer: str) -> dict[str, DataContract]:
    """Carga y valida todos los contratos de una capa. Acumula errores."""
    dir_path = models_dir / layer
    contracts: dict[str, DataContract] = {}
    errors: list[str] = []
    for yaml_file in sorted(dir_path.glob("*.yaml")):
        try:
            raw = yaml.safe_load(yaml_file.read_text())
            contract = DataContract.model_validate(raw)
        except Exception as exc:  # noqa: BLE001 — reporte agregado
            errors.append(f"{yaml_file.name}: {exc}")
            continue
        if contract.name in contracts:
            errors.append(f"{yaml_file.name}: nombre duplicado '{contract.name}'")
        else:
            contracts[contract.name] = contract
    if errors:
        raise ValueError("contratos inválidos:\n  " + "\n  ".join(errors))
    return contracts


def _postgres_dsn() -> str:
    import os

    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5433")
    user = os.getenv("POSTGRES_USER", os.getenv("PGUSER", "postgres"))
    dbname = os.getenv("POSTGRES_DB", os.getenv("PGDATABASE", "genbi"))
    password = os.getenv("POSTGRES_PASSWORD", os.getenv("PGPASSWORD", ""))
    return f"host={host} port={port} user={user} dbname={dbname} password={password}"


def build_layer(
    models_dir: Path,
    lakehouse_dir: Path,
    layer: str = "gold",
    select: str | None = None,
    postgres_dsn: str | None = None,
) -> LayerResult:
    """Construye una capa del lakehouse desde Postgres OLTP."""
    start = time.time()
    contracts = load_contracts(models_dir, layer)
    names = list(contracts)
    depends_on = {n: c.depends_on for n, c in contracts.items()}

    if select is not None and select != layer:
        if select not in contracts:
            raise ValueError(f"modelo desconocido: {select}")
        names = topological_order([select], {select: contracts[select].depends_on})
    else:
        names = topological_order(names, depends_on)

    dsn = postgres_dsn or _postgres_dsn()
    # Verifica que Postgres responda antes de tocar DuckDB
    with psycopg.connect(dsn) as conn:
        conn.execute("SELECT 1")

    con = duckdb.connect()
    con.execute("INSTALL postgres; LOAD postgres;")
    con.execute(f"ATTACH '{_escape_dsn(dsn)}' AS pg (TYPE postgres)")

    result = LayerResult(layer=layer)
    out_root = lakehouse_dir / layer
    for name in names:
        model_start = time.time()
        sql = (models_dir / layer / f"{name}.sql").read_text()
        logger.info("[gold] %s materializando...", name)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS {sql}")
        rows = con.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
        quality = run_model_tests(con, name, contracts[name])
        _export_parquet(con, name, out_root / name)
        result.models.append(
            ModelResult(name=name, rows=rows, duration_seconds=time.time() - model_start, quality=quality)
        )
        logger.info("[gold] %s listo: %d filas en %.1fs", name, rows, time.time() - model_start)

    if result.failed:
        raise ValueError(
            "calidad: errores en " + ", ".join(f"{m} ({len(_e(m, result))})" for m in result.failed)
        )

    _write_report(result, lakehouse_dir, time.time() - start)
    return result


def _e(name: str, result: LayerResult) -> list[Any]:
    for m in result.models:
        if m.name == name:
            return m.quality.errors
    return []


def _escape_dsn(dsn: str) -> str:
    # DuckDB requiere que el password con caracteres especiales vaya escapado.
    return dsn.replace("\\", "\\\\").replace("'", "''")


def _export_parquet(con: duckdb.DuckDBPyConnection, name: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"COPY (SELECT * FROM {name}) TO '{out_dir / 'data.parquet'}' (FORMAT PARQUET)"
    )


def _write_report(result: LayerResult, lakehouse_dir: Path, duration: float) -> None:
    reports_dir = lakehouse_dir / "_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:12]
    payload = {
        "run_id": run_id,
        "layer": result.layer,
        "duration_seconds": round(duration, 1),
        "models": [
            {
                "name": m.name,
                "rows": m.rows,
                "duration_seconds": round(m.duration_seconds, 1),
                "tests": [
                    {
                        "type": r.test_type,
                        "column": r.column,
                        "severity": r.severity,
                        "passed": r.passed,
                        "message": r.message,
                    }
                    for r in m.quality.results
                ],
            }
            for m in result.models
        ],
    }
    (reports_dir / f"quality-{run_id}.json").write_text(json.dumps(payload, indent=2))
    logger.info("reporte de calidad: %s", reports_dir / f"quality-{run_id}.json")