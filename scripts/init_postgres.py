"""Bootstrap: exporta datos horarios del Parquet a PostgreSQL y ejecuta las
transformaciones SQL bronze → silver → gold.

Uso:  uv run python scripts/init_postgres.py
"""
import subprocess
import sys
import time
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
PARQUET = ROOT / "data" / "curated" / "rama_historica.parquet"
BRONZE_CSV = ROOT / "data" / "bronze_rama.csv"
COMPOSE_FILE = ROOT / "compose.yml"
TRANSFORM_SILVER = ROOT / "scripts" / "transform_silver.sql"
TRANSFORM_GOLD = ROOT / "scripts" / "transform_gold.sql"
INDEXES = ROOT / "docker" / "postgres" / "init" / "06_indexes.sql"


def run(cmd, **kwargs):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT, check=True, **kwargs)
    return result


def wait_pg_ready():
    print("Waiting for PostgreSQL...")
    for _ in range(30):
        r = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "-T", "postgres",
             "pg_isready", "-U", "rama", "-d", "rama"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if r.returncode == 0:
            print("  PostgreSQL ready")
            return
        time.sleep(1.5)
    raise RuntimeError("PostgreSQL did not become ready")


def export_bronze_csv():
    print(f"Exporting {PARQUET} → {BRONZE_CSV} ...")
    df = pl.read_parquet(PARQUET)
    # polars write_csv no acepta None como null por defecto? revisamos
    df = df.select(["FECHA", "HORA", "estacion", "contaminante", "valor"])
    df.write_csv(BRONZE_CSV, include_header=False, null_value="")
    size_mb = BRONZE_CSV.stat().st_size / 1024 / 1024
    print(f"  Done ({size_mb:.0f} MB)")


def psql_copy(sql: str):
    """Ejecuta SQL via psql en el contenedor."""
    p = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "-T", "postgres",
         "psql", "-U", "rama", "-d", "rama"],
        cwd=ROOT, input=sql, capture_output=True, text=True,
    )
    if p.returncode != 0:
        print(p.stderr[-600:] if len(p.stderr) > 600 else p.stderr, file=sys.stderr)
        raise subprocess.CalledProcessError(p.returncode, "psql")
    # mostrar ultimas lineas de output (resumen de INSERT/COPY)
    out = p.stdout.strip()
    if out:
        for line in out.splitlines()[-5:]:
            print(f"    {line}")


def psql_file(path: Path):
    """Ejecuta un archivo SQL via psql."""
    sql = path.read_text(encoding="utf-8")
    print(f"  Running {path.name} ...")
    psql_copy(sql)


def load_bronze():
    print("Loading Bronze data via COPY ...")
    # COPY desde el host: montar un volumen o usar stdin via docker cp + psql
    # Lo mas simple: docker cp el CSV al contenedor, luego COPY, luego borrar
    csv_name = "bronze_rama.csv"
    run(["docker", "compose", "-f", str(COMPOSE_FILE), "cp",
         str(BRONZE_CSV), f"postgres:/tmp/{csv_name}"])
    psql_copy(f"""
        COPY bronze.rama_horaria (fecha, hora, estacion, contaminante, valor)
        FROM '/tmp/{csv_name}'
        WITH (FORMAT CSV, NULL '');
    """)
    # verificar conteo
    psql_copy("SELECT COUNT(*) AS bronze_rows FROM bronze.rama_horaria;")


def main():
    # 1. Exportar
    export_bronze_csv()

    # 2. Arrancar compose (si no esta corriendo)
    print("\nStarting Docker services...")
    run(["docker", "compose", "-f", str(COMPOSE_FILE), "up", "-d"])

    # 3. Esperar a que PG este listo
    wait_pg_ready()

    # 4. Cargar Bronze
    load_bronze()

    # 5. Ejecutar transformaciones
    print("\nRunning Silver transform...")
    psql_file(TRANSFORM_SILVER)
    psql_copy("SELECT COUNT(*) AS silver_rows FROM silver.rama_horaria_validada;")

    print("\nRunning Gold transform...")
    psql_file(TRANSFORM_GOLD)
    psql_copy("SELECT COUNT(*) AS gold_rows FROM gold.rama_mensual_bi;")

    # 6. Crear indices
    print("\nCreating indexes...")
    psql_file(INDEXES)

    # 7. Limpiar CSV temporal
    print(f"\nCleaning up {BRONZE_CSV} ...")
    BRONZE_CSV.unlink(missing_ok=True)

    print("\nDone. PostgreSQL medallon ready.")
    print(f"  Postgres: localhost:5433  (db: rama)")
    print(f"  API:      http://localhost:8080/api/data?cont=NOX&from=2015&to=2025")
    print("  Dashboard: abre data/exposure/rama_dashboard.html (modo Servidor)")


if __name__ == "__main__":
    main()
