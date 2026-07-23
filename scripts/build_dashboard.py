"""Build rama_dashboard.html — injects compact JSON into the HTML template.

Reads data/exposure/rama_mensual.parquet, drops zero-data rows, rounds values,
and writes a self-contained dashboard to data/exposure/rama_dashboard.html.
"""
import html
import json
from pathlib import Path

import polars as pl

PARQUET = "data/exposure/rama_mensual.parquet"
TEMPLATE = "scripts/dashboard_template.html"
OUTPUT = "data/exposure/rama_dashboard.html"

CONT_INFO = {
    "CO":   {"n": "Monóxido de carbono",   "u": "ppm"},
    "NO":   {"n": "Óxido nítrico",         "u": "ppb"},
    "NO2":  {"n": "Dióxido de nitrógeno",  "u": "ppb"},
    "NOX":  {"n": "Óxidos de nitrógeno",   "u": "ppb"},
    "O3":   {"n": "Ozono",                 "u": "ppb"},
    "PM10": {"n": "Partículas < 10 µm",    "u": "µg/m³"},
    "PM25": {"n": "Partículas < 2.5 µm",   "u": "µg/m³"},
    "PMCO": {"n": "Partículas gruesas",    "u": "µg/m³"},
    "SO2":  {"n": "Dióxido de azufre",     "u": "ppb"},
}


def main():
    df = pl.read_parquet(PARQUET)

    # Stations in stable order (sorted by code)
    stations_df = (
        df.select(["estacion", "nombre_estacion", "alcaldia", "lat_lon"])
        .unique()
        .sort("estacion")
    )
    stations = []
    for row in stations_df.iter_rows(named=True):
        lat, lon = row["lat_lon"].split(",")
        stations.append({
            "c": row["estacion"],
            "n": html.unescape(row["nombre_estacion"]),
            "a": html.unescape(row["alcaldia"]),
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
        })
    st_idx = {s["c"]: i for i, s in enumerate(stations)}

    conts_present = sorted(df["contaminante"].unique().to_list())
    conts = [{"c": c, "n": CONT_INFO[c]["n"], "u": CONT_INFO[c]["u"]} for c in conts_present]
    ct_idx = {c: i for i, c in enumerate(conts_present)}

    # Keep only rows with actual data
    df = df.filter(pl.col("horas_validas") > 0)

    rows = []
    for r in df.select([
        "anio", "mes", "estacion", "contaminante",
        "valor_mean", "valor_max", "valor_p95", "pct_datos",
    ]).iter_rows():
        anio, mes, est, cont, mean, vmax, p95, pct = r
        rows.append([
            anio, mes, st_idx[est], ct_idx[cont],
            round(mean, 1) if mean is not None else None,
            round(vmax, 1) if vmax is not None else None,
            round(p95, 1) if p95 is not None else None,
            round(pct),
        ])

    payload = {
        "stations": stations,
        "conts": conts,
        "rows": rows,
        "yearMin": int(df["anio"].min()),
        "yearMax": int(df["anio"].max()),
    }

    js = "window.RAMA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";"
    print(f"Payload: {len(js) / 1024 / 1024:.1f} MB, {len(rows):,} rows")

    tpl = Path(TEMPLATE).read_text(encoding="utf-8")
    marker = "/*__RAMA_DATA__*/"
    if marker not in tpl:
        raise SystemExit(f"Marker {marker} not found in {TEMPLATE}")
    out = tpl.replace(marker, js)
    Path(OUTPUT).write_text(out, encoding="utf-8")
    size_mb = Path(OUTPUT).stat().st_size / 1024 / 1024
    print(f"Wrote {OUTPUT} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
