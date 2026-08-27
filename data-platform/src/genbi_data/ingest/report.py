"""Reporte de ingesta OLTP (PRD E1-H3 T4.2, ``make ingest-report``)."""

from __future__ import annotations

import os
import sys

import psycopg


def _connect() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("PGHOST", "localhost"),
        port=os.getenv("PGPORT", "5433"),
        user=os.getenv("PGUSER", "postgres"),
        dbname=os.getenv("PGDATABASE", "genbi"),
        password=os.getenv("PGPASSWORD", ""),
    )


def main() -> int:
    with _connect() as conn:
        print("=== Últimas corridas de ingesta ===")
        rows = conn.execute(
            "SELECT run_id::text, started_at, finished_at, status, scope, "
            "files_processed, rows_written, error_summary "
            "FROM oltp.ingestion_run ORDER BY started_at DESC LIMIT 5"
        ).fetchall()
        for r in rows:
            errs = f" | {r[7]}" if r[7] else ""
            print(
                f"  {r[0][:8]}… {r[1]} → {r[2]} | {r[3]} | {r[4]} | files={r[5]} rows={r[6]}{errs}"
            )
        print()

        print("=== Archivos procesados (última corrida) ===")
        last = conn.execute(
            "SELECT run_id FROM oltp.ingestion_run ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        if last:
            files = conn.execute(
                "SELECT source_path, entity, rows, status FROM oltp.ingestion_file "
                "WHERE run_id = %s ORDER BY source_path",
                (last[0],),
            ).fetchall()
            for f in files:
                print(f"  {f[0].split('/')[-1]:30s} {f[1]:12s} rows={f[2]:6d} {f[3]}")
        print()

        total = conn.execute("SELECT count(*) FROM oltp.event").fetchone()[0]
        matches = conn.execute("SELECT count(*) FROM oltp.match").fetchone()[0]
        print(f"Total eventos en oltp.event: {total:,}")
        print(f"Total partidos en oltp.match: {matches:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
