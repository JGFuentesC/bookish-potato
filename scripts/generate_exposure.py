"""Generate rama_mensual.parquet — BI-ready monthly exposure table for Looker Studio.

Reads curated data, enriches with station coordinates, aggregates to monthly grain.
"""
import json
import sys
from pathlib import Path

import polars as pl

CATALOG_PATH = "data/exposure/stations_catalog.json"
INPUT_PATH = "data/curated/rama_historica.parquet"
OUTPUT_PATH = "data/exposure/rama_mensual.parquet"

CONTAMINANT_NAMES = {
    "CO": "Monoxido de carbono",
    "NO": "Oxido nitrico",
    "NO2": "Dioxido de nitrogeno",
    "NOX": "Oxidos de nitrogeno",
    "O3": "Ozono",
    "PM10": "Particulas < 10 µm",
    "PM25": "Particulas < 2.5 µm",
    "PMCO": "Particulas gruesas",
    "SO2": "Dioxido de azufre",
}

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def estacion_del_anio(mes: int) -> str:
    if mes in (3, 4, 5):
        return "Primavera"
    elif mes in (6, 7, 8):
        return "Verano"
    elif mes in (9, 10, 11):
        return "Otonio"
    else:
        return "Invierno"


def trimestre(mes: int) -> int:
    return (mes - 1) // 3 + 1


def build_station_frame(catalog_path: str) -> pl.DataFrame:
    cat = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    rows = []
    for code, info in cat.items():
        rows.append({
            "estacion": code,
            "nombre_estacion": info.get("nombre", code),
            "alcaldia": info.get("alcaldia", ""),
            "lat_lon": f"{info['lat']:.6f},{info['lon']:.6f}",
            "lat": info["lat"],
            "lon": info["lon"],
        })
    return pl.DataFrame(rows, schema={
        "estacion": pl.Utf8,
        "nombre_estacion": pl.Utf8,
        "alcaldia": pl.Utf8,
        "lat_lon": pl.Utf8,
        "lat": pl.Float64,
        "lon": pl.Float64,
    })


def main():
    print("Loading catalog...")
    stations = build_station_frame(CATALOG_PATH)
    print(f"  {len(stations)} stations loaded")

    print("Loading curated data...")
    df = pl.read_parquet(INPUT_PATH)
    print(f"  {df.height:,} rows, {df.width} columns")

    print("Building time dimensions...")
    df = df.with_columns(
        pl.col("FECHA").dt.year().cast(pl.Int16).alias("anio"),
        pl.col("FECHA").dt.month().cast(pl.Int8).alias("mes"),
    )

    print("Joining station metadata...")
    df = df.join(stations, on="estacion", how="left")

    # Report unmatched
    missing = df.filter(pl.col("lat_lon").is_null()).select("estacion").unique()
    if missing.height > 0:
        print(f"  WARNING: {missing.height} stations without coordinates: {missing['estacion'].to_list()}")

    print("Aggregating to monthly grain...")
    aggs = [
        pl.col("valor").mean().alias("valor_mean"),
        pl.col("valor").max().alias("valor_max"),
        pl.col("valor").min().alias("valor_min"),
        pl.col("valor").std().alias("valor_std"),
        pl.col("valor").median().alias("valor_p50"),
        pl.col("valor").quantile(0.95).alias("valor_p95"),
        pl.col("valor").quantile(0.98).alias("valor_p98"),
        pl.col("valor").count().alias("horas_validas"),
    ]

    monthly = df.group_by(
        "estacion", "contaminante", "anio", "mes",
        "nombre_estacion", "alcaldia", "lat_lon",
        maintain_order=False,
    ).agg(aggs)

    print("Computing derived columns...")
    monthly = monthly.with_columns(
        pl.date(pl.col("anio"), pl.col("mes"), 1).alias("fecha"),
        pl.date(pl.col("anio"), pl.col("mes"), 1).dt.days_in_month().alias("dias_en_mes"),
    )
    monthly = monthly.with_columns(
        (pl.col("dias_en_mes").cast(pl.Int32) * 24).alias("horas_esperadas"),
        pl.col("dias_en_mes").alias("dias_esperados"),
    ).drop("dias_en_mes")

    # % completeness: (valid hours / expected hours) * 100
    monthly = monthly.with_columns(
        (
            (pl.col("horas_validas").cast(pl.Float32) /
             pl.col("horas_esperadas").cast(pl.Float32)) * 100
        ).alias("pct_datos"),
    )

    # Estimate days with data: count distinct days from hourly data
    # We compute this separately then join
    print("Computing days_with_data...")
    daily_presence = (
        df.group_by("estacion", "contaminante", "anio", "mes", "FECHA")
        .agg(pl.len())
        .group_by("estacion", "contaminante", "anio", "mes")
        .agg(pl.col("FECHA").n_unique().cast(pl.Int16).alias("dias_con_dato"))
    )

    monthly = monthly.join(
        daily_presence,
        on=["estacion", "contaminante", "anio", "mes"],
        how="left",
    )

    print("Adding text dimensions...")
    monthly = monthly.with_columns(
        pl.col("mes").replace_strict(MESES, return_dtype=pl.Utf8).alias("nombre_mes"),
        ((pl.col("mes") - 1) // 3 + 1).cast(pl.Int8).alias("trimestre"),
        pl.when(pl.col("mes").is_in([3, 4, 5])).then(pl.lit("Primavera"))
        .when(pl.col("mes").is_in([6, 7, 8])).then(pl.lit("Verano"))
        .when(pl.col("mes").is_in([9, 10, 11])).then(pl.lit("Otonio"))
        .otherwise(pl.lit("Invierno")).alias("estacion_del_anio"),
        pl.col("contaminante").replace_strict(CONTAMINANT_NAMES, return_dtype=pl.Utf8).alias("nombre_contaminante"),
    )

    # Final column selection and type enforcement for Looker Studio compatibility
    output_cols = [
        pl.col("fecha"),
        pl.col("anio").cast(pl.Int16),
        pl.col("mes").cast(pl.Int8),
        pl.col("nombre_mes"),
        pl.col("trimestre").cast(pl.Int8),
        pl.col("estacion_del_anio"),
        pl.col("estacion"),
        pl.col("nombre_estacion"),
        pl.col("alcaldia"),
        pl.col("lat_lon"),
        pl.col("contaminante"),
        pl.col("nombre_contaminante"),
        pl.col("valor_mean").cast(pl.Float32),
        pl.col("valor_max").cast(pl.Float32),
        pl.col("valor_min").cast(pl.Float32),
        pl.col("valor_std").cast(pl.Float32),
        pl.col("valor_p50").cast(pl.Float32),
        pl.col("valor_p95").cast(pl.Float32),
        pl.col("valor_p98").cast(pl.Float32),
        pl.col("horas_validas").cast(pl.Int32),
        pl.col("horas_esperadas").cast(pl.Int32),
        pl.col("dias_con_dato").cast(pl.Int16),
        pl.col("dias_esperados").cast(pl.Int8),
        pl.col("pct_datos").cast(pl.Float32),
    ]

    final = monthly.select(output_cols).sort(["fecha", "estacion", "contaminante"])

    print(f"Writing {OUTPUT_PATH}...")
    final.write_parquet(OUTPUT_PATH, compression="zstd", statistics=True)

    print(f"\nDone! {OUTPUT_PATH}")
    print(f"  Shape: {final.height:,} rows x {final.width} columns")
    print(f"  Schema:")
    for col, dtype in zip(final.columns, final.dtypes):
        print(f"    {col}: {dtype}")
    print(f"  Size: {Path(OUTPUT_PATH).stat().st_size / 1024 / 1024:.1f} MB")
    print(f"  Date range: {final['fecha'].min()} to {final['fecha'].max()}")
    print(f"  Contaminants: {final['contaminante'].unique().sort().to_list()}")
    print(f"  Stations: {final['estacion'].n_unique()}")

    # Sample rows
    print(f"\n  Sample (first 3 rows):")
    print(final.head(3))


if __name__ == "__main__":
    main()
