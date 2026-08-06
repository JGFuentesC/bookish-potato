import glob
import multiprocessing
import time
from pathlib import Path

import pandas as pd
import pymysql

from _config import cfg_db

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
SCHEMA = RAIZ / "docker" / "mysql" / "init" / "01_schema.sql"

DB = cfg_db("finanzas")

LISTAS = {
    "SP500": ("Índice S&P 500", "sp500.csv"),
    "NASDAQ": ("Bolsa NASDAQ", "nasdaq.csv"),
    "AMEX": ("NYSE American (AMEX)", "amex.csv"),
}

TRABAJADORES = min(8, multiprocessing.cpu_count())


def t0(msg: str) -> float:
    print(f"[ETL] {msg} ...", flush=True)
    return time.perf_counter()


def cronometra(inicio: float, msg: str) -> None:
    print(f"[ETL] {msg}: {time.perf_counter() - inicio:.1f}s", flush=True)


def conectar() -> pymysql.connections.Connection:
    return pymysql.connect(**DB)


def ejecutar_schema() -> None:
    conn = conectar()
    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for tabla in ("precio", "ticker_lista", "ticker", "lista", "precio_stage"):
            cur.execute(f"DROP TABLE IF EXISTS {tabla}")
        for stmt in SCHEMA.read_text().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
    conn.close()


def cargar_listas() -> None:
    conn = conectar()
    with conn.cursor() as cur:
        for codigo, (nombre, _) in LISTAS.items():
            cur.execute(
                "INSERT INTO lista (codigo, nombre) VALUES (%s, %s)", (codigo, nombre)
            )
    conn.close()


def cargar_tickers() -> dict[str, int]:
    sp = pd.read_csv(DATA / "sp500.csv", dtype=str, keep_default_na=False).fillna("")
    na = pd.read_csv(DATA / "nasdaq.csv", dtype=str, keep_default_na=False).fillna("")
    am = pd.read_csv(DATA / "amex.csv", dtype=str, keep_default_na=False).fillna("")

    base = pd.concat([sp[["symbol", "name"]], na[["symbol", "name"]], am[["symbol", "name"]]])
    base = base[base["name"].str.strip() != ""]
    base = base.drop_duplicates("symbol").set_index("symbol")
    base["sector"] = sp.set_index("symbol")["sector"].reindex(base.index).fillna("")
    base["subsector"] = sp.set_index("symbol")["subsector"].reindex(base.index).fillna("")

    filas = [
        (s, r["name"], r["sector"], r["subsector"]) for s, r in base.iterrows()
    ]
    conn = conectar()
    with conn.cursor() as cur:
        for i in range(0, len(filas), 2000):
            cur.executemany(
                "INSERT INTO ticker (simbolo, nombre, sector, subsector) VALUES (%s,%s,%s,%s)",
                filas[i : i + 2000],
            )
    conn.close()
    return {s: i for i, s in enumerate(base.index)}


def cargar_membresias() -> None:
    conn = conectar()
    with conn.cursor() as cur:
        cur.execute("SELECT codigo, id FROM lista")
        lista_id = dict(cur.fetchall())
        filas = []
        for codigo, (_, archivo) in LISTAS.items():
            df = pd.read_csv(DATA / archivo, usecols=["symbol"], dtype=str, keep_default_na=False)
            for s in df["symbol"]:
                filas.append((s, lista_id[codigo]))
        cur.executemany(
            "INSERT INTO ticker_lista (ticker_id, lista_id) "
            "SELECT id, %s FROM ticker WHERE simbolo = %s",
            [(lid, s) for s, lid in filas],
        )
    conn.close()


def preparar_stage() -> None:
    conn = conectar()
    with conn.cursor() as cur:
        cur.execute(
            """CREATE TABLE precio_stage (
                simbolo   VARCHAR(20) NOT NULL,
                fecha     DATE        NOT NULL,
                open      DECIMAL(18,6) NULL,
                high      DECIMAL(18,6) NULL,
                low       DECIMAL(18,6) NULL,
                close     DECIMAL(18,6) NULL,
                adj_close DECIMAL(18,6) NULL,
                volumen   BIGINT UNSIGNED NULL
            ) ENGINE=InnoDB"""
        )
    conn.close()


def cargar_stage_lote(archivos: list[str]) -> int:
    conn = pymysql.connect(**DB)
    n = 0
    try:
        with conn.cursor() as cur:
            for ruta in archivos:
                simbolo = Path(ruta).stem
                cur.execute("SET @s = %s", (simbolo,))
                cur.execute(
                    """LOAD DATA LOCAL INFILE %s INTO TABLE precio_stage
                        FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '\"'
                        LINES TERMINATED BY '\\n' IGNORE 1 LINES
                        (fecha, open, high, low, close, adj_close, volumen)
                        SET simbolo = @s""",
                    (ruta,),
                )
                n += cur.rowcount
    finally:
        conn.close()
    return n


def cargar_stage_paralelo() -> int:
    archivos = sorted(glob.glob(str(DATA / "prices" / "*.csv")))
    print(f"[ETL] archivos de precios: {len(archivos)}", flush=True)
    lotes = [[] for _ in range(TRABAJADORES)]
    for i, ruta in enumerate(archivos):
        lotes[i % TRABAJADORES].append(ruta)
    with multiprocessing.Pool(TRABAJADORES) as pool:
        totales = pool.map(cargar_stage_lote, lotes)
    return sum(totales)


def volcar_stage_a_precio() -> int:
    conn = conectar()
    try:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE precio DROP INDEX idx_precio_fecha")
            cur.execute("SET FOREIGN_KEY_CHECKS=0")
            cur.execute(
                """INSERT INTO precio (ticker_id, fecha, open, high, low, close, adj_close, volumen)
                    SELECT t.id, s.fecha, s.open, s.high, s.low, s.close, s.adj_close, s.volumen
                    FROM precio_stage s JOIN ticker t ON t.simbolo = s.simbolo"""
            )
            insertadas = cur.rowcount
            cur.execute("SET FOREIGN_KEY_CHECKS=1")
            cur.execute("ALTER TABLE precio ADD INDEX idx_precio_fecha (fecha)")
            cur.execute("DROP TABLE precio_stage")
            cur.execute("ANALYZE TABLE precio")
            return insertadas
    finally:
        conn.close()


def verificar(esperadas: dict[str, int]) -> None:
    conn = conectar()
    with conn.cursor() as cur:
        for tabla, esperado in esperadas.items():
            cur.execute(f"SELECT COUNT(*) FROM {tabla}")
            real = cur.fetchone()[0]
            estado = "OK" if real == esperado else f"DIFERENCIA (esperado {esperado})"
            print(f"[ETL] {tabla}: {real} filas  {estado}", flush=True)
        cur.execute(
            """SELECT COUNT(*) FROM precio p LEFT JOIN ticker t ON p.ticker_id = t.id
                WHERE t.id IS NULL"""
        )
        print(f"[ETL] precios huérfanos (sin ticker): {cur.fetchone()[0]}", flush=True)
    conn.close()


def main() -> None:
    ini = t0("verificando esquema")
    ejecutar_schema()
    cronometra(ini, "esquema")

    ini = t0("cargando listas")
    cargar_listas()
    cronometra(ini, "listas")

    ini = t0("cargando tickers")
    cargar_tickers()
    cronometra(ini, "tickers")

    ini = t0("cargando membresías")
    cargar_membresias()
    cronometra(ini, "membresías")

    ini = t0("preparando stage")
    preparar_stage()
    cronometra(ini, "stage")

    ini = t0(f"cargando precios en paralelo ({TRABAJADORES} workers)")
    filas_stage = cargar_stage_paralelo()
    cronometra(ini, f"stage cargado ({filas_stage} filas)")

    ini = t0("volcando stage -> precio (bulk INSERT)")
    insertadas = volcar_stage_a_precio()
    cronometra(ini, f"bulk insert ({insertadas} filas)")

    verificar(
        {
            "lista": len(LISTAS),
            "ticker": len(pd.read_csv(DATA / "tickers_all.csv", keep_default_na=False)),
            "precio": insertadas,
        }
    )
    print(f"[ETL] fin ({time.perf_counter() - ini:.1f}s total etapa final)", flush=True)


if __name__ == "__main__":
    main()
