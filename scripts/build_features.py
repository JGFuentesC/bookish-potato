"""Construye feat_diaria en finanzas_olap leyendo el OLTP (features + mercado)."""

import argparse
import time

import pymysql
import polars as pl

from _config import cfg_db
from features import TO_COLUMNAS, agregar_mercado, cargar_precios, enginyerear_features

OLTP = "finanzas"
OLAP = "finanzas_olap"
LOTE = 10_000


def t0(msg: str) -> float:
    print(f"[FEATURES] {msg} ...", flush=True)
    return time.perf_counter()


def cronometra(inicio: float, msg: str) -> None:
    print(f"[FEATURES] {msg}: {time.perf_counter() - inicio:.1f}s", flush=True)


def leer_simbolos(limite: int | None = None) -> list[str] | None:
    """Símbolos con precios (primeros `limite` si --solo, todos si None)."""
    sql = (
        "SELECT t.simbolo FROM ticker t "
        "WHERE EXISTS (SELECT 1 FROM precio p WHERE p.ticker_id = t.id) "
        "ORDER BY t.id"
    )
    if limite:
        sql += f" LIMIT {int(limite)}"
    conn = pymysql.connect(**cfg_db(OLTP))
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            simbolos = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()
    return simbolos if limite else None


def insertar(conn, df: pl.DataFrame) -> int:
    columnas = ", ".join(TO_COLUMNAS)
    marcadores = ", ".join(["%s"] * len(TO_COLUMNAS))
    actualizar = ", ".join(f"{c}=VALUES({c})" for c in TO_COLUMNAS if c not in ("simbolo", "fecha"))
    sql = (
        f"INSERT INTO feat_diaria ({columnas}) VALUES ({marcadores}) "
        f"ON DUPLICATE KEY UPDATE {actualizar}"
    )
    n = 0
    with conn.cursor() as cur:
        lote = []
        for fila in df.iter_rows():
            lote.append(fila)
            if len(lote) == LOTE:
                cur.executemany(sql, lote)
                n += len(lote)
                lote = []
        if lote:
            cur.executemany(sql, lote)
            n += len(lote)
    return n


def verificar(conn, n_enviadas: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*), COUNT(DISTINCT simbolo), MIN(fecha), MAX(fecha) FROM feat_diaria"
        )
        total, tickers, fmin, fmax = cur.fetchone()
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = 'feat_diaria' "
            "ORDER BY ordinal_position"
        )
        ddl = [r[0] for r in cur.fetchall()]
    print(f"[FEATURES] filas enviadas: {n_enviadas:,}", flush=True)
    print(f"[FEATURES] filas en tabla: {total:,} · tickers: {tickers:,} · rango: {fmin} → {fmax}", flush=True)
    print(f"[FEATURES] columnas DDL == script: {ddl == TO_COLUMNAS}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Construye feat_diaria (features + mercado)")
    ap.add_argument("--solo", type=int, default=None, metavar="N",
                    help="procesar solo N tickers (pruebas)")
    ap.add_argument("--fuerza", action="store_true",
                    help="TRUNCATE antes de insertar (por defecto upsert por PK)")
    args = ap.parse_args()

    simbolos = leer_simbolos(args.solo)
    if args.solo:
        print(f"[FEATURES] limitado a {len(simbolos)} tickers", flush=True)

    ini = t0("leyendo precios OLTP")
    df = cargar_precios(cfg_db(OLTP), simbolos=simbolos)
    cronometra(ini, f"precios ({df.height:,} filas)")

    ini = t0("computando features")
    df = enginyerear_features(df)
    df = agregar_mercado(df)
    cronometra(ini, f"features ({df.height:,} filas)")

    if df.is_empty():
        print("[FEATURES] sin filas para insertar", flush=True)
        return

    conn = pymysql.connect(**cfg_db(OLAP))
    try:
        if args.fuerza:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE feat_diaria")
            print("[FEATURES] tabla truncada (fuerza)", flush=True)
        ini = t0("insertando en feat_diaria")
        n = insertar(conn, df)
        cronometra(ini, f"insert ({n:,} filas)")
        verificar(conn, n)
    finally:
        conn.close()


if __name__ == "__main__":
    main()