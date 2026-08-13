"""Entrenamiento del forecast global (XGBoost) con VALIDACIÓN TEMPORAL OOT.

Corre en una máquina con acceso a MySQL (máquina de entrenamiento). Entrena:
  - Regresores cuantílicos Q10/Q50/Q90 (multi-horizon directo con FEATURE ``h``).
  - Clasificador de VOLATILIDAD: P(|retorno 21d| > 15%) = "movimiento fuerte",
    + calibración isotónica. (La dirección sube/baja es impredecible; la
    magnitud del movimiento sí lo es por clustering de volatilidad.)
Escribe en ./models/: forecast_q*.joblib, updown_clf.joblib, updown_iso.joblib,
forecast_meta.json y current.json.

Metodología de validación (lo que faltaba en la versión anterior):
  - Split TEMPORAL con purga/embargo: el test es el último ``--oot-dias`` días
    hábiles (NUNCA se muestrea); train = todo lo anterior menos 22 días de
    embargo (para que los labels no solapen con el test).
  - Unidad muestral ticker × mes con muestreo estratificado: cada ticker aporta
    observaciones de TODOS los meses de su historia (ventana deslizante), no
    solo del último tramo. Esto multiplica las observaciones y da robustez.
  - El muestreo de regresión/clasificador se aplica SOLO al train.
  - Métricas OOT de los REGRESORES: pinball Q10/Q50/Q90, MAE(q50), sesgo,
    cobertura empírica de la banda y comparación vs random walk (pred = 0).
  - Métricas OOT del CLASIFICADOR: acc, AUC, Brier y calibración por deciles.
  - Importancia de variables (gain) para q50 y clasificador.

Uso:
    python train_forecast.py --user train --password <pw> [--host 127.0.0.1]
        [--dias 0] [--max-tickers 0] [--meses 0] [--oot-dias 120]
        [--salida ./models] [--version vYYYYMMDDHHMM] [--cpu]
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, date
from pathlib import Path

import joblib
import numpy as np
import polars as pl
import pymysql
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.metrics import brier_score_loss

from features import TO_COLUMNAS

FEATURE_COLS = [
    "ret_1d", "ret_5d", "ret_21d", "ret_63d",
    "ma_5", "ma_20", "ma_50", "ma_ratio_20_50",
    "vol_20", "rng_mean_20", "volumen_log", "volume_ratio_20",
    "mes_num", "dia_semana", "mkt_ret_1d", "mkt_vol_20",
]
HORIZONTES = list(range(1, 11))
H_CLASIF = 21
EMBARGO_DIAS = 22  # días hábiles de purga (>= max horizonte 21)
TOPE_REGRESION = 6_000_000
TOPE_CLASIF = 4_000_000
UMBRAL_MOV = 0.15  # |retorno 21d| > 15% => "movimiento fuerte" (volatilidad, predecible)
VENTANA_DIAS = 63  # ancho de la ventana deslizante (en días naturales) por ticker×mes

NUMERICAS = {c for c in FEATURE_COLS} | {"close", "es_sp500", "es_nasdaq", "es_amex"}


def argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=3306)
    p.add_argument("--user", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--dias", type=int, default=0, help="últimos N días por ticker (0 = historia completa)")
    p.add_argument("--max-tickers", type=int, default=0, help="tickers muestreados (0 = todos)")
    p.add_argument("--meses", type=int, default=0, help="últimos N meses por ticker (0 = todos)")
    p.add_argument("--oot-dias", type=int, default=120, help="últimos N días hábiles como test OOT")
    p.add_argument("--salida", default="./models")
    p.add_argument("--version", default=None)
    p.add_argument("--cpu", action="store_true", help="fuerza CPU (sin device=cuda)")
    return p


def _conv(valor: object, numerica: bool):
    if valor is None:
        return None
    if numerica:
        return float(valor)
    if isinstance(valor, (datetime, date)):
        return valor
    return str(valor)


def cargar_feat(conn: pymysql.connections.Connection, dias: int | None, max_tickers: int | None, meses: int | None) -> pl.DataFrame:
    """Trae feat_diaria con push-down: `dias`/`meses` por ticker y hasta `max_tickers`.

    - ``dias=0`` → historia completa.
    - ``meses=0`` → todos los meses.
    - ``max_tickers=0`` → todos los tickers.
    """
    conds: list[str] = []
    if max_tickers:
        conds.append(
            "simbolo IN ("
            "SELECT simbolo FROM ("
            "SELECT simbolo, ROW_NUMBER() OVER (ORDER BY RAND(42)) AS rn "
            "FROM finanzas_olap.feat_diaria GROUP BY simbolo"
            f") s WHERE rn <= {int(max_tickers)})"
        )
    if dias:
        conds.append(
            "fecha >= DATE_SUB((SELECT MAX(fecha) FROM finanzas_olap.feat_diaria), "
            f"INTERVAL {int(dias)} DAY)"
        )
    if meses:
        conds.append(
            "fecha >= DATE_SUB((SELECT MAX(fecha) FROM finanzas_olap.feat_diaria), "
            f"INTERVAL {int(meses)} MONTH)"
        )
    where = f"WHERE {' AND '.join(conds)}" if conds else ""
    sql = f"""
        SELECT {", ".join(c for c in TO_COLUMNAS)}
        FROM finanzas_olap.feat_diaria
        {where}
        ORDER BY simbolo, fecha
    """
    cur = conn.cursor()
    cur.execute(sql)
    cols = [d[0] for d in cur.description]
    filas = cur.fetchall()
    cur.close()
    filas = [tuple(_conv(v, c in NUMERICAS) for c, v in zip(cols, f)) for f in filas]
    schema = {c: (pl.Float64 if c in NUMERICAS else pl.String) for c in cols}
    schema["fecha"] = pl.Date
    return pl.DataFrame(filas, schema=schema, orient="row")


def muestrear_mes(df: pl.DataFrame, tope: int) -> pl.DataFrame:
    """Muestreo estratificado por (ticker, mes): cada unidad muestral aporta igual.

    Mantiene la proporción de clases y el orden temporal dentro de cada grupo.
    """
    if df.height <= tope:
        return df
    df = df.with_columns(pl.col("fecha").dt.strftime("%Y-%m").alias("_mes"))
    n_grupos = df.select(pl.struct(["simbolo", "_mes"])).n_unique()
    k = max(1, tope // n_grupos)
    df = df.with_columns(
        pl.Series("_r", np.random.default_rng(42).permutation(np.arange(df.height)))
    )
    df = df.with_columns(pl.col("_r").rank("ordinal").over(["simbolo", "_mes"]).alias("_rank"))
    df = df.filter(pl.col("_rank") <= k)
    # si aún sobra (k=1 con muchos grupos), recorta al tope de forma aleatoria
    if df.height > tope:
        df = df.sample(n=tope, seed=42, shuffle=True)
    return df.drop(["_mes", "_r", "_rank"])


def construir_dataset(orig: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Devuelve (reg, clf) conservando simbolo/fecha para el split temporal.

    - reg: una fila por (simbolo, fecha, h) con target retorno acumulado a h días.
    - clf: una fila por (simbolo, fecha) con target bool "sube a 21 días".
    """
    df = orig.sort(["simbolo", "fecha"])

    shift = {"fecha": pl.col("fecha"), "simbolo": pl.col("simbolo")}
    for h in HORIZONTES:
        shift[f"fut_{h}"] = pl.col("close").shift(-h).over("simbolo") / pl.col("close") - 1
    shift["fut_21"] = pl.col("close").shift(-H_CLASIF).over("simbolo") / pl.col("close") - 1

    bloques = []
    for h in HORIZONTES:
        bloques.append(
            df.select(["simbolo", "fecha"] + FEATURE_COLS + [shift[f"fut_{h}"].alias("y"), pl.lit(h).alias("h")])
            .drop_nulls()
        )
    reg_df = pl.concat(bloques)

    clf_df = (
        df.select(["simbolo", "fecha"] + FEATURE_COLS + [shift["fut_21"].alias("y")])
        .with_columns((pl.col("y").abs() > UMBRAL_MOV).cast(pl.Int8).alias("y"))
        .drop_nulls()
    )
    return reg_df, clf_df


def split_temporal(df: pl.DataFrame, fechas_test: list[date], fechas_embargo: list[date]) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Divide por fecha: test = solo fechas_test; train = todo lo anterior, sin la ventana de embargo."""
    test_filtro = pl.col("fecha").is_in(fechas_test)
    train = df.filter((~test_filtro) & (~pl.col("fecha").is_in(fechas_embargo)))
    test = df.filter(test_filtro)
    return train, test


def pinball(y: pl.Series, q: pl.Series, alpha: float) -> float:
    """Pinball loss medio."""
    d = (y.to_numpy() - q.to_numpy())
    return float((d * alpha * (d >= 0) + d * (alpha - 1) * (d < 0)).mean())


def main() -> None:
    t_inicio = time.time()
    args = argparser().parse_args()
    version = args.version or time.strftime("v%Y%m%d%H%M")
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)

    device = {} if args.cpu else {"device": "cuda"}

    print("conectando a MySQL...", flush=True)
    conn = pymysql.connect(
        host=args.host, port=args.port, user=args.user, password=args.password,
        charset="utf8mb4",
    )
    feats = cargar_feat(conn, args.dias, args.max_tickers, args.meses)
    conn.close()
    print(f"feat_diaria: {feats.shape[0]} filas x {feats.shape[1]} cols", flush=True)

    simbolos = feats["simbolo"].unique().sort().to_list()
    n_meses = feats.select(pl.col("fecha").dt.strftime("%Y-%m")).n_unique()
    print(f"tickers: {len(simbolos)} | meses: {n_meses}", flush=True)

    reg_df, clf_df = construir_dataset(feats)
    print(f"dataset regresión: {reg_df.shape[0]} filas | clasificador: {clf_df.shape[0]} filas", flush=True)

    # Fechas del test OOT: últimos `oot_dias` hábiles globales, con embargo previo
    # para que los labels (hasta h=21) del train no solapen con el test.
    fechas_globales = sorted(feats["fecha"].unique().to_list())
    fechas_test = fechas_globales[-args.oot_dias:]
    fechas_embargo = fechas_globales[-args.oot_dias - EMBARGO_DIAS: -args.oot_dias]

    reg_train, reg_test = split_temporal(reg_df, fechas_test, fechas_embargo)
    clf_train, clf_test = split_temporal(clf_df, fechas_test, fechas_embargo)
    print(
        f"split temporal: train {reg_train.shape[0]}/{clf_train.shape[0]} | "
        f"OOT {reg_test.shape[0]}/{clf_test.shape[0]} filas "
        f"({fechas_test[0]} → {fechas_test[-1]}, embargo {EMBARGO_DIAS}d)",
        flush=True,
    )

    # Muestreo estratificado SOLO en train, por unidad muestral (ticker × mes)
    if reg_train.height > TOPE_REGRESION:
        reg_train = muestrear_mes(reg_train, TOPE_REGRESION)
        print(f"muestreo regresión a {reg_train.height} (estratificado ticker×mes)", flush=True)
    if clf_train.height > TOPE_CLASIF:
        clf_train = muestrear_mes(clf_train, TOPE_CLASIF)
        print(f"muestreo clasificador a {clf_train.height} (estratificado ticker×mes)", flush=True)

    # ---- Regresores cuantílicos (16 features + h) ----
    X_cols = FEATURE_COLS + ["h"]
    X_reg_train = reg_train.select(X_cols).to_numpy()
    y_reg_train = reg_train["y"].to_numpy()
    X_reg_test = reg_test.select(X_cols).to_numpy()
    y_reg_test = reg_test["y"].to_numpy()

    params_base = dict(
        max_depth=8, learning_rate=0.08, n_estimators=150,
        subsample=0.9, colsample_bytree=0.8, tree_method="hist", n_jobs=-1,
        random_state=42, **device,
    )

    modelos: dict[str, xgb.XGBRegressor] = {}
    tiempos: dict[str, float] = {}
    for nombre, alpha in (("q10", 0.10), ("q50", 0.50), ("q90", 0.90)):
        t0 = time.time()
        m = xgb.XGBRegressor(**params_base, objective="reg:quantileerror", quantile_alpha=alpha)
        try:
            m.fit(X_reg_train, y_reg_train, verbose=False)
        except Exception:  # noqa: BLE001 - fallback a CPU si CUDA falla
            print(f"{nombre}: CUDA falló, reintento en CPU", flush=True)
            m = xgb.XGBRegressor(
                **{k: v for k, v in params_base.items() if k != "device"},
                objective="reg:quantileerror", quantile_alpha=alpha,
            )
            m.fit(X_reg_train, y_reg_train, verbose=False)
        modelos[nombre] = m
        tiempos[nombre] = time.time() - t0
        print(f"{nombre}: {tiempos[nombre]:.0f}s", flush=True)

    # ---- Clasificador sube/baja (16 features) ----
    Xc_cols = FEATURE_COLS
    Xc_train = clf_train.select(Xc_cols).to_numpy()
    yc_train = clf_train["y"].to_numpy()
    Xc_test = clf_test.select(Xc_cols).to_numpy()
    yc_test = clf_test["y"].to_numpy()

    t0 = time.time()
    clf = xgb.XGBClassifier(
        max_depth=6, learning_rate=0.08, n_estimators=120, subsample=0.9,
        colsample_bytree=0.8, tree_method="hist", n_jobs=-1, random_state=42,
        eval_metric="logloss", **device,
    )
    try:
        clf.fit(Xc_train, yc_train, verbose=False)
    except Exception:  # noqa: BLE001 - fallback CPU
        print("clf: CUDA falló, reintento en CPU", flush=True)
        clf = xgb.XGBClassifier(
            max_depth=6, learning_rate=0.08, n_estimators=120, subsample=0.9,
            colsample_bytree=0.8, tree_method="hist", n_jobs=-1, random_state=42,
            eval_metric="logloss",
        )
        clf.fit(Xc_train, yc_train, verbose=False)
    t_clf = time.time() - t0
    print(f"clasificador: {t_clf:.0f}s", flush=True)

    t0 = time.time()
    calibrado = CalibratedClassifierCV(clf, method="isotonic", cv=3)
    calibrado.fit(Xc_train, yc_train)
    t_cal = time.time() - t0
    print(f"calibración isotónica: {t_cal:.0f}s", flush=True)

    # ---- Métricas OOT: regresores ----
    # Basura vs random walk: predecir retorno 0 (precio constante).
    metricas_reg: dict = {}
    for nombre, alpha in (("q10", 0.10), ("q50", 0.50), ("q90", 0.90)):
        pred = modelos[nombre].predict(X_reg_test)
        ps = pl.Series(pred)
        ys = y_reg_test
        pin = pinball(pl.Series(ys), ps, alpha)
        metricas_reg[nombre] = {
            "pinball": round(pin, 6),
            "pinball_rw": round(pinball(pl.Series(ys), pl.Series([0.0] * len(ys)), alpha), 6),
            "ratio_vs_rw": round(pin / max(pinball(pl.Series(ys), pl.Series([0.0] * len(ys)), alpha), 1e-12), 4),
        }

    p50 = modelos["q50"].predict(X_reg_test)
    p10 = modelos["q10"].predict(X_reg_test)
    p90 = modelos["q90"].predict(X_reg_test)
    maes = float((pl.Series(y_reg_test) - pl.Series(p50)).abs().mean())
    sesgo = float((pl.Series(p50) - pl.Series(y_reg_test)).mean())
    cobertura = float(((pl.Series(p10) <= pl.Series(y_reg_test)) & (pl.Series(y_reg_test) <= pl.Series(p90))).mean())
    mae_rw = float(pl.Series(y_reg_test).abs().mean())
    metricas_reg["mae_q50"] = round(maes, 6)
    metricas_reg["mae_rw"] = round(mae_rw, 6)
    metricas_reg["ratio_mae_vs_rw"] = round(maes / max(mae_rw, 1e-12), 4)
    metricas_reg["sesgo_q50"] = round(sesgo, 6)
    metricas_reg["cobertura_q10_q90"] = round(cobertura, 4)

    # Por horizonte (para detectar si h=1..10 se degradan)
    por_h: dict[str, float] = {}
    for h in HORIZONTES:
        mask = (reg_test["h"] == h).to_numpy()
        if mask.sum() == 0:
            continue
        eh = float((pl.Series(p50[mask]) - pl.Series(y_reg_test[mask])).abs().mean())
        por_h[f"mae_q50_h{h}"] = round(eh, 6)
    metricas_reg["mae_por_horizonte"] = por_h

    # ---- Métricas OOT: clasificador (modelo SERVIDO: el calibrado) ----
    proba_test = calibrado.predict_proba(Xc_test)[:, 1]
    pred_bin = (proba_test >= 0.5).astype(int)
    acc = accuracy_score(yc_test, pred_bin)
    auc = roc_auc_score(yc_test, proba_test)
    brier = brier_score_loss(yc_test, proba_test)
    tasa_mov = float(yc_test.mean())

    # Calibración por deciles
    orden = proba_test.argsort()
    deciles: list[dict] = []
    n_dec = 10
    for i in range(n_dec):
        idx = orden[int(i * len(proba_test) / n_dec):int((i + 1) * len(proba_test) / n_dec)]
        if len(idx) == 0:
            continue
        deciles.append({
            "bins": round(i / n_dec + 1 / (2 * n_dec), 2),
            "prob_media": round(float(proba_test[idx].mean()), 3),
            "frec_obs": round(float(yc_test[idx].mean()), 3),
        })
    metricas_clf = {
        "acc_oot": round(acc, 4),
        "auc_oot": round(auc, 4),
        "brier_oot": round(brier, 4),
        "tasa_mov_oot": round(tasa_mov, 4),
        "umbral_movimiento": UMBRAL_MOV,
        "n_oot": int(len(yc_test)),
        "calibracion_deciles": deciles,
    }
    print(
        f"OOT clf (movimiento fuerte >{UMBRAL_MOV:.0%}): acc={acc:.4f} auc={auc:.4f} "
        f"brier={brier:.4f} (n={len(yc_test)}, tasa={tasa_mov:.3f})",
        flush=True,
    )

    # ---- Importancia de variables (gain) ----
    def importancias(m, cols: list[str]) -> list[dict]:
        imp = m.feature_importances_
        pares = sorted(zip(cols, imp), key=lambda t: -t[1])
        return [{"feature": c, "gain": round(float(v), 6)} for c, v in pares]

    meta_importancias = {
        "q50": importancias(modelos["q50"], X_cols),
        "clasificador": importancias(clf, Xc_cols),
    }

    # ---- Persistencia ----
    for nombre, m in modelos.items():
        joblib.dump(m, out / f"forecast_{nombre}.joblib")
    joblib.dump(clf, out / "updown_clf.joblib")
    joblib.dump(calibrado, out / "updown_iso.joblib")

    t_total = time.time() - t_inicio
    meta = {
        "version": version,
        "entrenado_el": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duracion_s": round(t_total, 1),
        "dataset": {
            "filas_feat": int(feats.shape[0]),
            "filas_reg_entren": int(reg_train.height),
            "filas_reg_oot": int(reg_test.height),
            "filas_clf_entren": int(clf_train.height),
            "filas_clf_oot": int(clf_test.height),
            "tickers": len(simbolos),
            "oot_inicio": fechas_test[0].isoformat(),
            "oot_fin": fechas_test[-1].isoformat(),
        },
        "tiempos_fit_s": {
            **{k: round(v, 1) for k, v in tiempos.items()},
            "clasificador": round(t_clf, 1),
            "calibracion_isotonica": round(t_cal, 1),
        },
        "metricas": {
            "regresores": metricas_reg,
            "clasificador": metricas_clf,
        },
        "importancias": meta_importancias,
    }
    (out / "forecast_meta.json").write_text(json.dumps(meta, indent=2))

    rutas = {
        "forecast_q10": "forecast_q10.joblib", "forecast_q50": "forecast_q50.joblib",
        "forecast_q90": "forecast_q90.joblib", "updown_clf": "updown_clf.joblib",
        "updown_iso": "updown_iso.joblib",
    }
    (out / "current.json").write_text(json.dumps(
        {"modelo": version, "entrenado_el": meta["entrenado_el"], "rutas": rutas,
         "umbral_movimiento": UMBRAL_MOV}, indent=2,
    ))

    print(
        f"\nOK. artefactos en {out} | versión {version} | duración total {t_total:.0f}s",
        flush=True,
    )
    print("REGRESORES OOT:", json.dumps({k: v for k, v in metricas_reg.items() if k != "mae_por_horizonte"}, indent=2), flush=True)
    print("CLF OOT:", json.dumps(metricas_clf, indent=2), flush=True)


if __name__ == "__main__":
    main()
