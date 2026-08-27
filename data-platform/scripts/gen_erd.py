"""Genera docs/erd-oltp.md (Mermaid erDiagram) desde el esquema OLTP real en Postgres.

Uso (desde la raíz del repo, con direnv activo):
    uv run --project data-platform python -m scripts.gen_erd
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "erd-oltp.md"

SCHEMA = "oltp"

ATTR_TYPE = {
    "smallint": "int",
    "integer": "int",
    "bigint": "int",
    "numeric": "num",
    "uuid": "uuid",
    "text": "text",
    "boolean": "bool",
    "date": "date",
    "timestamp with time zone": "timestamptz",
    "jsonb": "jsonb",
}


def load(conn: psycopg.Connection) -> dict[str, dict]:
    columns = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s
            ORDER BY table_name, ordinal_position
            """,
            (SCHEMA,),
        )
        for table, column, dtype in cur.fetchall():
            columns.setdefault(table, []).append((column, dtype))

        cur.execute(
            """
            SELECT tc.table_name, kcu.column_name, ccu.table_name AS ref_table
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = %s
            """,
            (SCHEMA,),
        )
        refs = cur.fetchall()

        cur.execute(
            """
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = %s
            """,
            (SCHEMA,),
        )
        pks = set(cur.fetchall())
    return {"columns": columns, "refs": refs, "pks": pks}


def build(schema: dict[str, dict]) -> str:
    entities = schema["columns"]
    refs = schema["refs"]
    pks = schema["pks"]
    by_table: dict[str, list[tuple[str, str]]] = {t: [] for t in entities}
    for table, column, ref_table in refs:
        by_table[table].append((column, ref_table))

    lines: list[str] = ["# ERD OLTP — GenBI Fútbol", ""]
    lines.append("```mermaid")
    lines.append("erDiagram")
    for table in sorted(entities):
        label = table.upper()
        fk_cols = {col for col, _ in by_table[table]}
        lines.append(f'    {label} {{')
        for col, dtype in entities[table]:
            attrs = []
            if (table, col) in pks:
                attrs.append("PK")
            if col in fk_cols:
                attrs.append("FK")
            kind = ATTR_TYPE.get(dtype, dtype)
            lines.append(f'        {kind} {col} {" ".join(attrs)}')
        lines.append(f'    }}')
        for col, ref_table in by_table[table]:
            lines.append(f'    {label} ||--o{{ {ref_table.upper()} : "{col}"')
    lines.append("```")
    lines.append("")
    lines.append(f"**{len(entities)} tablas** en esquema `oltp` · generado por `scripts/gen_erd.py` desde el esquema real.")
    return "\n".join(lines) + "\n"


def main() -> None:
    dsn = (
        f"postgresql://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}"
        f"@localhost:5433/{os.environ['POSTGRES_DB']}"
    )
    with psycopg.connect(dsn) as conn:
        schema = load(conn)
    OUT.write_text(build(schema))
    print(f"ERD escrito en {OUT.relative_to(ROOT)} con {len(schema['columns'])} tablas y {len(schema['refs'])} FKs")


if __name__ == "__main__":
    main()