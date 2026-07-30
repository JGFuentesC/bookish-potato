"""
Analizar periodos de actividad/inactividad de estaciones RAMA.

Lee data/curated/rama_historica.parquet y, para cada estación,
detecta periodos de actividad basándose en presencia/ausencia de datos.
Un "gap" (hueco) de >30 días sin datos marca cambio de estado activo/inactivo.

Salida: tabla con periodos (estacion, fecha_inicio, fecha_fin, dias_con_datos, activo).
"""

import polars as pl
from datetime import datetime, timedelta
from pathlib import Path


def analizar_estacion(df_est: pl.DataFrame, codigo_est: str) -> list[dict]:
    """
    Analiza una estación individual. Retorna lista de periodos (dicts).
    """
    periodos = []

    if df_est.height == 0:
        return periodos

    df_est = df_est.sort("FECHA")
    fechas_unicas = sorted(df_est["FECHA"].unique().to_list())

    if not fechas_unicas:
        return periodos

    # Detectar gaps: diferencias entre fechas consecutivas
    gap_threshold = timedelta(days=30)
    grupos_activos = []  # Lista de (fecha_inicio, fecha_fin) para periodos activos

    grupo_inicio = fechas_unicas[0]
    grupo_fin = fechas_unicas[0]

    for i in range(1, len(fechas_unicas)):
        fecha_actual = fechas_unicas[i]
        fecha_anterior = fechas_unicas[i - 1]
        gap = fecha_actual - fecha_anterior

        if gap <= gap_threshold:
            # Continúa el grupo
            grupo_fin = fecha_actual
        else:
            # Gap detectado: cierra grupo anterior, inicia nuevo
            grupos_activos.append((grupo_inicio, grupo_fin))
            grupo_inicio = fecha_actual
            grupo_fin = fecha_actual

    # Cierra último grupo
    grupos_activos.append((grupo_inicio, grupo_fin))

    # Convertir grupos a periodos con metadata
    for idx, (fecha_inicio, fecha_fin) in enumerate(grupos_activos):
        # Datos en el periodo
        df_periodo = df_est.filter(
            (pl.col("FECHA") >= fecha_inicio) & (pl.col("FECHA") <= fecha_fin)
        )
        dias_con_datos = df_periodo["FECHA"].n_unique()

        periodos.append({
            "estacion": codigo_est,
            "periodo_num": idx + 1,
            "fecha_inicio": fecha_inicio,
            "fecha_fin": fecha_fin,
            "dias_con_datos": dias_con_datos,
            "activo": True,  # Por definición, un grupo detectado = activo
        })

    return periodos


def main():
    """Ejecuta análisis completo."""
    parquet_path = Path("data/curated/rama_historica.parquet")
    if not parquet_path.exists():
        print(f"ERROR: {parquet_path} no existe")
        return

    print(f"Leyendo {parquet_path}...")
    df = pl.read_parquet(parquet_path)

    total_filas = df.height
    estaciones = sorted(df["estacion"].unique().to_list())

    print(f"Total filas: {total_filas:,}")
    print(f"Estaciones: {len(estaciones)}")
    print(f"Rango de fechas: {df['FECHA'].min()} → {df['FECHA'].max()}")
    print()

    # Análisis por estación
    todos_periodos = []
    for codigo_est in estaciones:
        df_est = df.filter(pl.col("estacion") == codigo_est)
        periodos_est = analizar_estacion(df_est, codigo_est)
        todos_periodos.extend(periodos_est)

    # Convertir a DataFrame
    df_periodos = pl.DataFrame(todos_periodos)

    # Resumen por estación
    print("=" * 90)
    print("PERIODOS DETECTADOS POR ESTACIÓN")
    print("=" * 90)
    print()

    for codigo_est in estaciones:
        df_est_periodos = df_periodos.filter(pl.col("estacion") == codigo_est)
        n_periodos = df_est_periodos.height

        print(f"{codigo_est}: {n_periodos} periodo(s)")
        for row in df_est_periodos.iter_rows(named=True):
            print(
                f"  [{row['periodo_num']}] "
                f"{row['fecha_inicio']} → {row['fecha_fin']} "
                f"({row['dias_con_datos']} días con datos)"
            )
        print()

    # Estadísticas generales
    print("=" * 90)
    print("ESTADÍSTICAS GENERALES")
    print("=" * 90)
    total_periodos = df_periodos.height
    estaciones_con_multiplos_periodos = (
        df_periodos.group_by("estacion")
        .agg(pl.count().alias("num_periodos"))
        .filter(pl.col("num_periodos") > 1)
        .height
    )

    print(f"Total periodos detectados: {total_periodos}")
    print(f"Estaciones con 1 periodo: {len(estaciones) - estaciones_con_multiplos_periodos}")
    print(f"Estaciones con múltiples periodos: {estaciones_con_multiplos_periodos}")
    print()

    # Guardar resumen
    output_path = Path("data/exposure/periodos_estaciones.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_periodos.write_csv(output_path)
    print(f"Resumen guardado en: {output_path}")
    print()

    # Tabla de carga (SCD Type 2): fecha_inicio, fecha_fin, activo
    # Agregar también estaciones que NO aparecen en ningún periodo (inactivas siempre)
    # Por ahora, solo mostramos las detectadas
    print("=" * 90)
    print("TABLA PARA CARGA (SCD Type 2 — rama.estacion_periodo)")
    print("=" * 90)
    print()
    print("Campos requeridos (antes de agregar metadata de estaciones):")
    print("  estacion_codigo, nombre_estacion, alcaldia, latitud, longitud,")
    print("  fecha_inicio, fecha_fin, activo")
    print()

    # Preview
    preview = df_periodos.select(
        pl.col("estacion"),
        pl.col("fecha_inicio"),
        pl.col("fecha_fin"),
        pl.col("dias_con_datos"),
    ).head(10)
    print(preview)


if __name__ == "__main__":
    main()
