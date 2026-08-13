"""Features por ticker para entrenamiento (población de feat_diaria)."""

import pymysql
import polars as pl

TO_COLUMNAS = [
    "simbolo", "fecha", "sector", "es_sp500", "es_nasdaq", "es_amex", "close",
    "ret_1d", "ret_5d", "ret_21d", "ret_63d",
    "ma_5", "ma_20", "ma_50", "ma_ratio_20_50",
    "vol_20", "rng_mean_20", "volumen_log", "volume_ratio_20",
    "mes_num", "dia_semana", "mkt_ret_1d", "mkt_vol_20",
]

COLUMNAS_FEATURES = [
    "ret_1d", "ret_5d", "ret_21d", "ret_63d",
    "ma_5", "ma_20", "ma_50", "ma_ratio_20_50",
    "vol_20", "rng_mean_20", "volumen_log", "volume_ratio_20",
    "mes_num", "dia_semana", "mkt_ret_1d", "mkt_vol_20",
]

_COLUMNAS_BASE = [c for c in TO_COLUMNAS if c not in ("mkt_ret_1d", "mkt_vol_20")]
_LISTA_A_BANDERA = {"SP500": 0, "NASDAQ": 1, "AMEX": 2}


def cargar_precios(conn_info: dict, simbolos: list[str] | None = None) -> pl.DataFrame:
    """Une ticker + ticker_lista + lista + precio del OLTP y devuelve serie diaria."""
    db = pymysql.connect(**conn_info)
    try:
        with db.cursor() as cur:
            cur.execute(
                "SELECT t.simbolo, l.codigo FROM ticker_lista tl "
                "JOIN ticker t ON t.id = tl.ticker_id "
                "JOIN lista l ON l.id = tl.lista_id"
            )
            membresias = cur.fetchall()
            cur.execute("SELECT simbolo, sector FROM ticker")
            metadatos = dict(cur.fetchall())

            sql = (
                "SELECT t.simbolo, p.fecha, p.close, p.volumen, p.high, p.low "
                "FROM precio p JOIN ticker t ON t.id = p.ticker_id"
            )
            params = ()
            if simbolos is not None:
                marcadores = ", ".join(["%s"] * len(simbolos))
                sql += f" WHERE t.simbolo IN ({marcadores})"
                params = tuple(simbolos)
            cur.execute(sql, params)
            filas = cur.fetchall()
    finally:
        db.close()

    precios = pl.DataFrame(
        filas,
        schema={
            "simbolo": pl.String,
            "fecha": pl.Date,
            "close": pl.Float64,
            "volumen": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
        },
        orient="row",
    )

    banderas: dict[str, list[int]] = {}
    for simbolo, codigo in membresias:
        b = banderas.setdefault(simbolo, [0, 0, 0])
        b[_LISTA_A_BANDERA[codigo]] = 1
    tickers = pl.DataFrame(
        {
            "simbolo": list(metadatos),
            "sector": list(metadatos.values()),
            "es_sp500": [banderas.get(s, [0, 0, 0])[0] for s in metadatos],
            "es_nasdaq": [banderas.get(s, [0, 0, 0])[1] for s in metadatos],
            "es_amex": [banderas.get(s, [0, 0, 0])[2] for s in metadatos],
        }
    )
    return (
        precios.join(tickers, on="simbolo", how="left")
        .select(["simbolo", "fecha", "close", "volumen", "high", "low", "sector",
                 "es_sp500", "es_nasdaq", "es_amex"])
        .sort(["simbolo", "fecha"])
    )


def enginyerear_features(df: pl.DataFrame) -> pl.DataFrame:
    """Retornos pasados, medias móviles, volatilidad y calendario por simbolo."""
    d = df.sort(["simbolo", "fecha"]).with_columns(
        (pl.col("close") / pl.col("close").shift(1) - 1).over("simbolo").alias("ret_1d"),
        (pl.col("close") / pl.col("close").shift(5) - 1).over("simbolo").alias("ret_5d"),
        (pl.col("close") / pl.col("close").shift(21) - 1).over("simbolo").alias("ret_21d"),
        (pl.col("close") / pl.col("close").shift(63) - 1).over("simbolo").alias("ret_63d"),
        pl.col("close").rolling_mean(min_samples=5, window_size=5).over("simbolo").alias("ma_5"),
        pl.col("close").rolling_mean(min_samples=5, window_size=20).over("simbolo").alias("ma_20"),
        pl.col("close").rolling_mean(min_samples=5, window_size=50).over("simbolo").alias("ma_50"),
    )
    d = d.with_columns(
        pl.col("ret_1d").rolling_std(min_samples=5, window_size=20).over("simbolo").alias("vol_20"),
        ((pl.col("high") - pl.col("low")) / pl.col("close"))
        .rolling_mean(min_samples=5, window_size=20)
        .over("simbolo")
        .alias("rng_mean_20"),
        pl.when(pl.col("volumen") > 0)
        .then(pl.col("volumen").log())
        .otherwise(None)
        .alias("volumen_log"),
        (pl.col("ma_20") / pl.col("ma_50") - 1).alias("ma_ratio_20_50"),
        (pl.col("volumen") / pl.col("volumen").rolling_mean(min_samples=5, window_size=20).over("simbolo") - 1)
        .alias("volume_ratio_20"),
        pl.col("fecha").dt.month().alias("mes_num"),
        pl.col("fecha").dt.weekday().alias("dia_semana"),
    )
    return d.select(_COLUMNAS_BASE)


def agregar_mercado(df: pl.DataFrame) -> pl.DataFrame:
    """Contexto cross-tickers por fecha (medias de ret_1d y vol_20) y descarta incompletas."""
    mercado = (
        df.group_by("fecha")
        .agg(mkt_ret_1d=pl.col("ret_1d").mean(), mkt_vol_20=pl.col("vol_20").mean())
    )
    flotantes = [c for c in TO_COLUMNAS
                 if c not in ("simbolo", "fecha", "sector", "es_sp500", "es_nasdaq",
                              "es_amex", "mes_num", "dia_semana")]
    return (
        df.join(mercado, on="fecha", how="left")
        .with_columns(pl.col(flotantes).replace([float("inf"), float("-inf")], None))
        .fill_nan(None)
        .select(TO_COLUMNAS)
        .drop_nulls()
    )