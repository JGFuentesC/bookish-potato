#!/usr/bin/env python3
"""Exporta un snapshot SQLite estático (lean) desde MySQL — SOLO lectura.

Conecta con el usuario ``dashboards`` (grants SELECT en ``finanzas_olap``) y
vuelca a un archivo ``.db`` lo que la forecast-api sirve en modo ``sqlite``:

  - Catálogo OLAP: dim_sector / dim_subsector / dim_empresa / dim_lista /
    hecho_membresia.
  - Historia OHLCV completa (5 años): ``fact_precio_diario`` → (empresa_id,
    fecha, open, high, low, close, volumen).
  - Forecast: última fila de ``feat_diaria`` por símbolo (features + close).

Uso:
    uv run python deploy/scripts/export_snapshot.py [--salida deploy/data/static.db]

Idempotente: recrea el archivo en cada ejecución.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

DDL = [
    """CREATE TABLE dim_sector (
        sector_id INTEGER PRIMARY KEY, sector_nombre TEXT NOT NULL)""",
    """CREATE TABLE dim_subsector (
        subsector_id INTEGER PRIMARY KEY,
        sector_id INTEGER NOT NULL, subsector_nombre TEXT NOT NULL)""",
    """CREATE TABLE dim_empresa (
        empresa_id INTEGER PRIMARY KEY, simbolo TEXT NOT NULL UNIQUE,
        nombre TEXT, subsector_id INTEGER NOT NULL)""",
    """CREATE TABLE dim_lista (
        lista_id INTEGER PRIMARY KEY, codigo TEXT NOT NULL UNIQUE)""",
    """CREATE TABLE hecho_membresia (
        empresa_id INTEGER NOT NULL, lista_id INTEGER NOT NULL,
        PRIMARY KEY (empresa_id, lista_id))""",
    """CREATE TABLE fact_precio_diario (
        empresa_id INTEGER NOT NULL, fecha TEXT NOT NULL,
        open REAL, high REAL, low REAL, close REAL, volumen INTEGER,
        PRIMARY KEY (empresa_id, fecha))""",
    """CREATE TABLE feat_diaria (
        simbolo TEXT PRIMARY KEY, fecha TEXT, close REAL,
        ret_1d REAL, ret_5d REAL, ret_21d REAL, ret_63d REAL,
        ma_5 REAL, ma_20 REAL, ma_50 REAL, ma_ratio_20_50 REAL,
        vol_20 REAL, rng_mean_20 REAL, volumen_log REAL, volume_ratio_20 REAL,
        mes_num INTEGER, dia_semana INTEGER, mkt_ret_1d REAL, mkt_vol_20 REAL)""",
    "CREATE INDEX idx_fact_fecha ON fact_precio_diario (fecha)",
    "CREATE INDEX idx_hm_lista ON hecho_membresia (lista_id)",
]

LOTE = 100_000


def cargar_env() -> None:
    ruta = ROOT / ".env"
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, _, v = linea.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def sqlite_conexion(ruta: Path) -> sqlite3.Connection:
    if ruta.exists():
        ruta.unlink()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(ruta))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.isolation_level = None  # autocommit; transacciones manuales por lote
    for ddl in DDL:
        conn.execute(ddl)
    return conn


def fila_plana(fila: tuple) -> tuple:
    return tuple(float(v) if isinstance(v, Decimal) else v for v in fila)


def copiar(titulo: str, mysql_cur, sqlite_conn, insert_sql: str, where: str | None = None) -> int:
    inicio = time.time()
    total = 0
    sqlite_conn.execute("BEGIN")
    lote: list[tuple] = []
    for fila in mysql_cur:
        lote.append(fila_plana(fila))
        if len(lote) >= LOTE:
            sqlite_conn.executemany(insert_sql, lote)
            total += len(lote)
            lote.clear()
            sqlite_conn.execute("COMMIT")
            sqlite_conn.execute("BEGIN")
    if lote:
        sqlite_conn.executemany(insert_sql, lote)
        total += len(lote)
    sqlite_conn.execute("COMMIT")
    seg = time.time() - inicio
    print(f"  {titulo:<28} {total:>10,} filas   ({seg:6.1f}s)")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", default=str(ROOT / "deploy" / "data" / "static.db"))
    args = parser.parse_args()

    cargar_env()
    try:
        import pymysql
    except ImportError:
        sys.exit("pip install pymysql (uv run) antes de exportar el snapshot")

    salida = Path(args.salida)
    print(f"Snapshot → {salida}")
    conn_mysql = pymysql.connect(
        host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_DASHBOARDS_USER"),
        password=os.getenv("MYSQL_DASHBOARDS_PASSWORD"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.SSCursor,
    )
    sqlite_conn = sqlite_conexion(salida)
    try:
        with conn_mysql, sqlite_conn, conn_mysql.cursor() as cur:
            cur.execute(
                "SELECT sector_id, sector_nombre FROM finanzas_olap.dim_sector ORDER BY sector_id"
            )
            copiar("dim_sector", cur, sqlite_conn, "INSERT INTO dim_sector VALUES (?, ?)")

            cur.execute(
                "SELECT subsector_id, sector_id, subsector_nombre FROM finanzas_olap.dim_subsector ORDER BY subsector_id"
            )
            copiar("dim_subsector", cur, sqlite_conn, "INSERT INTO dim_subsector VALUES (?, ?, ?)")

            cur.execute(
                "SELECT empresa_id, simbolo, nombre, subsector_id FROM finanzas_olap.dim_empresa ORDER BY empresa_id"
            )
            copiar("dim_empresa", cur, sqlite_conn, "INSERT INTO dim_empresa VALUES (?, ?, ?, ?)")

            cur.execute(
                "SELECT lista_id, codigo FROM finanzas_olap.dim_lista ORDER BY lista_id"
            )
            copiar("dim_lista", cur, sqlite_conn, "INSERT INTO dim_lista VALUES (?, ?)")

            cur.execute(
                "SELECT empresa_id, lista_id FROM finanzas_olap.hecho_membresia ORDER BY empresa_id"
            )
            copiar("hecho_membresia", cur, sqlite_conn, "INSERT INTO hecho_membresia VALUES (?, ?)")

            cur.execute(
                """SELECT f.empresa_id, CAST(DATE_FORMAT(df.fecha, '%Y-%m-%d') AS CHAR),
                          f.open, f.high, f.low, f.close, f.volumen
                   FROM finanzas_olap.fact_precio_diario f
                   JOIN finanzas_olap.dim_fecha df ON df.fecha_id = f.fecha_id
                   ORDER BY f.empresa_id, df.fecha"""
            )
            copiar(
                "fact_precio_diario",
                cur,
                sqlite_conn,
                "INSERT INTO fact_precio_diario VALUES (?, ?, ?, ?, ?, ?, ?)",
            )

            cols = (
                "ret_1d, ret_5d, ret_21d, ret_63d, ma_5, ma_20, ma_50, ma_ratio_20_50,"
                " vol_20, rng_mean_20, volumen_log, volume_ratio_20,"
                " mes_num, dia_semana, mkt_ret_1d, mkt_vol_20"
            )
            cur.execute(
                f"""SELECT t.simbolo, CAST(DATE_FORMAT(t.fecha, '%Y-%m-%d') AS CHAR),
                           t.close, {cols}
                    FROM (
                      SELECT *, ROW_NUMBER() OVER (PARTITION BY simbolo ORDER BY fecha DESC) rn
                      FROM finanzas_olap.feat_diaria
                    ) t WHERE t.rn = 1"""
            )
            copiar(
                "feat_diaria (última/símbolo)",
                cur,
                sqlite_conn,
                "INSERT INTO feat_diaria VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            )
    finally:
        try:
            sqlite_conn.execute("ANALYZE")
            sqlite_conn.execute("VACUUM")
        except sqlite3.Error:
            pass

    tam = salida.stat().st_size / (1024 * 1024)
    print(f"\nOK → {salida} ({tam:.1f} MB)")


if __name__ == "__main__":
    main()