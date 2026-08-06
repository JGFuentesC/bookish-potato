import datetime as dt
import time
from pathlib import Path

import pymysql

from _config import cfg_db

RAIZ = Path(__file__).resolve().parent.parent
SCHEMA = RAIZ / "docker" / "mysql" / "olap" / "01_schema_olap.sql"
OLTP = "finanzas"

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def t0(msg: str) -> float:
    print(f"[OLAP] {msg} ...", flush=True)
    return time.perf_counter()


def cronometra(inicio: float, msg: str) -> None:
    print(f"[OLAP] {msg}: {time.perf_counter() - inicio:.1f}s", flush=True)


def conectar(database: str | None = "finanzas_olap"):
    cfg = cfg_db(database)
    return pymysql.connect(**cfg)


def ejecutar_schema() -> None:
    conn0 = conectar(database=None)
    with conn0.cursor() as cur:
        cur.execute(
            "CREATE DATABASE IF NOT EXISTS finanzas_olap "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
        )
    conn0.close()

    conn = conectar()
    with conn.cursor() as cur:
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        for tabla in (
            "hecho_membresia", "fact_precio_mensual", "fact_precio_diario",
            "dim_lista", "dim_empresa", "dim_subsector", "dim_sector",
            "dim_fecha", "dim_mes", "dim_anio",
        ):
            cur.execute(f"DROP TABLE IF EXISTS {tabla}")
        for stmt in SCHEMA.read_text().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
    conn.close()


def cargar_calendario() -> None:
    conn = conectar()
    with conn.cursor() as cur:
        cur.execute(f"SELECT MIN(fecha), MAX(fecha) FROM {OLTP}.precio")
        fmin, fmax = cur.fetchone()

    def ultimo_dia_mes(d: dt.date) -> dt.date:
        if d.month == 12:
            return dt.date(d.year, 12, 31)
        return dt.date(d.year, d.month + 1, 1) - dt.timedelta(days=1)

    anios, meses, fechas = {}, {}, []
    dia = dt.date(fmin.year, fmin.month, 1)
    limite = ultimo_dia_mes(fmax)
    while dia <= limite:
        anios[dia.year] = None
        meses[(dia.year, dia.month)] = None
        dia += dt.timedelta(days=1)
    dia = dt.date(fmin.year, fmin.month, 1)
    while dia <= limite:
        fin_mes = ultimo_dia_mes(dia)
        iso = dia.isocalendar()
        fechas.append(
            (
                dia.year * 10000 + dia.month * 100 + dia.day,
                dia,
                dia.day,
                iso.weekday,                       # 1=Lun..7=Dom
                DIAS[iso.weekday - 1],
                f"{iso.year}-{iso.week:02d}",
                1 if iso.weekday >= 6 else 0,
                1 if dia.day == fin_mes.day else 0,
                dia.year * 100 + dia.month,
            )
        )
        dia += dt.timedelta(days=1)

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO dim_anio (anio_id, anio, decada) VALUES (%s,%s,%s)",
            [(a, a, (a // 10) * 10) for a in sorted(anios)],
        )
        cur.executemany(
            "INSERT INTO dim_mes (mes_id, mes_num, mes_nombre, anio_id) VALUES (%s,%s,%s,%s)",
            [
                (a * 100 + m, m, MESES[m - 1], a)
                for a, m in sorted(meses)
            ],
        )
        cur.executemany(
            """INSERT INTO dim_fecha
                (fecha_id, fecha, dia_num, dia_semana, dia_semana_nombre,
                 semana_iso, es_fin_semana, es_ultimo_dia_mes, mes_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            fechas,
        )
    conn.close()


def cargar_sectores() -> None:
    conn = conectar()
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT DISTINCT sector, subsector FROM {OLTP}.ticker
                WHERE sector <> '' AND subsector <> '' ORDER BY sector, subsector"""
        )
        pares = cur.fetchall()

    cur = conn.cursor()
    cur.execute("INSERT INTO dim_sector (sector_nombre) VALUES ('Sin clasificar')")
    sectores = {"Sin clasificar": cur.lastrowid}
    subs = [("Sin clasificar", "Sin clasificar")]
    for sector, subsector in pares:
        if sector not in sectores:
            cur.execute("INSERT INTO dim_sector (sector_nombre) VALUES (%s)", (sector,))
            sectores[sector] = cur.lastrowid
        subs.append((subsector, sector))
    cur.executemany(
        "INSERT INTO dim_subsector (subsector_nombre, sector_id) VALUES (%s,%s)",
        [(s, sectores[sec]) for s, sec in subs],
    )
    cur.execute("SELECT subsector_nombre, subsector_id FROM dim_subsector")
    subsector_id = dict(cur.fetchall())
    conn.close()
    return subsector_id


def cargar_empresas(subsector_id: dict[str, int]) -> None:
    conn = conectar()
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT simbolo, nombre, sector, subsector FROM {OLTP}.ticker ORDER BY id"""
        )
        filas = cur.fetchall()
    cur = conn.cursor()
    datos = [
        (
            s,
            n if n else None,
            subsector_id[sub if sub else "Sin clasificar"],
        )
        for s, n, sec, sub in filas
        if s != ""
    ]
    cur.executemany(
        "INSERT INTO dim_empresa (simbolo, nombre, subsector_id) VALUES (%s,%s,%s)",
        datos,
    )
    conn.close()


def cargar_listas() -> None:
    conn = conectar()
    with conn.cursor() as cur:
        cur.execute(f"SELECT id, codigo, nombre FROM {OLTP}.lista")
        cur.executemany(
            "INSERT INTO dim_lista (lista_id, codigo, nombre) VALUES (%s,%s,%s)",
            cur.fetchall(),
        )
    conn.close()


def cargar_fact_diario() -> int:
    conn = conectar()
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE fact_precio_diario DROP FOREIGN KEY fk_fd_fecha")
        cur.execute("ALTER TABLE fact_precio_diario DROP INDEX idx_fd_fecha")
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        cur.execute(
            f"""INSERT INTO fact_precio_diario
                    (empresa_id, fecha_id, open, high, low, close, adj_close, volumen,
                     retorno_diario, retorno_log, retorno_ajustado, rango, volumen_dolares)
                WITH base AS (
                    SELECT p.ticker_id, t.simbolo, p.fecha, p.open, p.high, p.low,
                           p.close, p.adj_close, p.volumen,
                           LAG(p.close)     OVER (PARTITION BY p.ticker_id ORDER BY p.fecha) AS prev_close,
                           LAG(p.adj_close) OVER (PARTITION BY p.ticker_id ORDER BY p.fecha) AS prev_adj
                    FROM {OLTP}.precio p
                    JOIN {OLTP}.ticker t ON t.id = p.ticker_id
                )
                SELECT
                    e.empresa_id,
                    f.fecha_id,
                    b.open, b.high, b.low, b.close, b.adj_close, b.volumen,
                    CASE WHEN b.prev_close IS NOT NULL AND b.prev_close <> 0
                         THEN (b.close - b.prev_close) / b.prev_close END,
                    CASE WHEN b.prev_close IS NOT NULL AND b.prev_close > 0 AND b.close > 0
                         THEN LN(b.close / b.prev_close) END,
                    CASE WHEN b.prev_adj IS NOT NULL AND b.prev_adj <> 0
                         THEN (b.adj_close - b.prev_adj) / b.prev_adj END,
                    CASE WHEN b.high IS NOT NULL AND b.low IS NOT NULL
                         THEN b.high - b.low END,
                    CASE WHEN b.close IS NOT NULL AND b.volumen IS NOT NULL
                         THEN b.close * b.volumen END
                FROM base b
                JOIN dim_empresa e ON e.simbolo = b.simbolo
                JOIN dim_fecha  f ON f.fecha = b.fecha"""
        )
        n = cur.rowcount
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
        cur.execute("ALTER TABLE fact_precio_diario ADD INDEX idx_fd_fecha (fecha_id)")
        cur.execute(
            "ALTER TABLE fact_precio_diario ADD CONSTRAINT fk_fd_fecha "
            "FOREIGN KEY (fecha_id) REFERENCES dim_fecha (fecha_id)"
        )
        cur.execute("ANALYZE TABLE fact_precio_diario")
    conn.close()
    return n


def cargar_fact_mensual() -> int:
    conn = conectar()
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE fact_precio_mensual DROP FOREIGN KEY fk_fm_mes")
        cur.execute("ALTER TABLE fact_precio_mensual DROP INDEX idx_fm_mes")
        cur.execute("SET FOREIGN_KEY_CHECKS=0")
        cur.execute(
            """INSERT INTO fact_precio_mensual
                    (empresa_id, mes_id, open_primero, close_ultimo, high_max, low_min,
                     volumen_total, retorno_mensual, volatilidad_mensual, n_dias)
                WITH diario AS (
                    SELECT d.empresa_id, df.mes_id, d.open, d.high, d.low, d.close,
                           d.volumen, d.retorno_diario,
                           ROW_NUMBER() OVER (PARTITION BY d.empresa_id, df.mes_id ORDER BY d.fecha_id) AS rn_asc,
                           ROW_NUMBER() OVER (PARTITION BY d.empresa_id, df.mes_id ORDER BY d.fecha_id DESC) AS rn_desc
                    FROM fact_precio_diario d
                    JOIN dim_fecha df ON df.fecha_id = d.fecha_id
                )
                SELECT
                    empresa_id,
                    mes_id,
                    MAX(CASE WHEN rn_asc = 1 THEN open END),
                    MAX(CASE WHEN rn_desc = 1 THEN close END),
                    MAX(high),
                    MIN(low),
                    SUM(volumen),
                    CASE WHEN MAX(CASE WHEN rn_asc = 1 THEN open END) <> 0
                         THEN MAX(CASE WHEN rn_desc = 1 THEN close END)
                              / MAX(CASE WHEN rn_asc = 1 THEN open END) - 1 END,
                    STDDEV_SAMP(retorno_diario),
                    COUNT(*)
                FROM diario
                GROUP BY empresa_id, mes_id"""
        )
        n = cur.rowcount
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
        cur.execute("ALTER TABLE fact_precio_mensual ADD INDEX idx_fm_mes (mes_id)")
        cur.execute(
            "ALTER TABLE fact_precio_mensual ADD CONSTRAINT fk_fm_mes "
            "FOREIGN KEY (mes_id) REFERENCES dim_mes (mes_id)"
        )
        cur.execute("ANALYZE TABLE fact_precio_mensual")
    conn.close()
    return n


def cargar_membresia() -> int:
    conn = conectar()
    with conn.cursor() as cur:
        cur.execute(
            f"""INSERT INTO hecho_membresia (empresa_id, lista_id)
                SELECT e.empresa_id, tl.lista_id
                FROM {OLTP}.ticker_lista tl
                JOIN {OLTP}.ticker t ON t.id = tl.ticker_id
                JOIN dim_empresa e ON e.simbolo = t.simbolo"""
        )
        n = cur.rowcount
        cur.execute("ANALYZE TABLE hecho_membresia")
    conn.close()
    return n


def verificar() -> None:
    conn = conectar()
    with conn.cursor() as cur:
        for tabla in (
            "dim_anio", "dim_mes", "dim_fecha", "dim_sector", "dim_subsector",
            "dim_empresa", "dim_lista", "fact_precio_diario",
            "fact_precio_mensual", "hecho_membresia",
        ):
            cur.execute(f"SELECT COUNT(*) FROM {tabla}")
            print(f"[OLAP] {tabla}: {cur.fetchone()[0]:,} filas", flush=True)
        cur.execute(
            """SELECT COUNT(*) FROM fact_precio_diario f
               LEFT JOIN dim_empresa e ON e.empresa_id = f.empresa_id
               LEFT JOIN dim_fecha df ON df.fecha_id = f.fecha_id
               WHERE e.empresa_id IS NULL OR df.fecha_id IS NULL"""
        )
        print(f"[OLAP] fact diario huérfanos: {cur.fetchone()[0]}", flush=True)
        cur.execute(
            """SELECT t.simbolo, df.fecha, p.close, f.close, f.retorno_diario
                FROM fact_precio_diario f
                JOIN dim_empresa e ON e.empresa_id = f.empresa_id
                JOIN dim_fecha df ON df.fecha_id = f.fecha_id
                JOIN finanzas.ticker t ON t.simbolo = e.simbolo
                JOIN finanzas.precio p ON p.ticker_id = t.id AND p.fecha = df.fecha
                WHERE t.simbolo = 'AAPL'
                ORDER BY df.fecha_id DESC LIMIT 3"""
        )
        print("[OLAP] muestra AAPL (close OLTP vs OLAP, retorno):")
        for fila in cur.fetchall():
            print(f"[OLAP]   {fila}", flush=True)
    conn.close()


def main() -> None:
    ini = t0("esquema")
    ejecutar_schema()
    cronometra(ini, "esquema")

    ini = t0("calendario")
    cargar_calendario()
    cronometra(ini, "calendario")

    ini = t0("sector/subsector")
    subsector_id = cargar_sectores()
    cronometra(ini, "sector/subsector")

    ini = t0("empresas")
    cargar_empresas(subsector_id)
    cronometra(ini, "empresas")

    ini = t0("listas")
    cargar_listas()
    cronometra(ini, "listas")

    ini = t0("fact_precio_diario (bulk + retornos con LAG)")
    n_diario = cargar_fact_diario()
    cronometra(ini, f"fact diario ({n_diario:,} filas)")

    ini = t0("fact_precio_mensual (agregado)")
    n_mensual = cargar_fact_mensual()
    cronometra(ini, f"fact mensual ({n_mensual:,} filas)")

    ini = t0("hecho_membresia")
    n_mem = cargar_membresia()
    cronometra(ini, f"membresía ({n_mem:,} filas)")

    verificar()


if __name__ == "__main__":
    main()
