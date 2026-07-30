"""
Ingesta batch de datos RAMA en PostgreSQL OLTP.

Lee:
  - data/curated/rama_historica.parquet (mediciones horarias)
  - data/exposure/stations_catalog.json (metadatos de estaciones)
  - data/exposure/periodos_estaciones.csv (periodos de actividad SCD Type 2)

Carga en:
  - rama.estacion (códigos)
  - rama.estacion_periodo (dimensión lenta SCD Type 2)
  - rama.medicion (hechos, por año)
  - rama.lote_carga (auditoría)

Uso:
  uv run python scripts/ingesta_batch.py [--anio YYYY]

Si --anio se especifica, carga solo ese año. Si no, carga todos.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import polars as pl
import psycopg
from psycopg import sql


DATABASE_URL = "postgresql://rama:rama@localhost:5433/rama"
PARQUET_PATH = Path("data/curated/rama_historica.parquet")
STATIONS_PATH = Path("data/exposure/stations_catalog.json")
PERIODOS_PATH = Path("data/exposure/periodos_estaciones.csv")


def load_estaciones(conn, stations_data: dict) -> dict[str, int]:
    """Cargar estaciones base y retornar mapeo codigo -> estacion_id."""
    cursor = conn.cursor()

    codigos = sorted(stations_data.keys())
    resultado = {}

    for codigo in codigos:
        cursor.execute(
            "INSERT INTO rama.estacion (codigo) VALUES (%s) "
            "ON CONFLICT (codigo) DO UPDATE SET codigo = EXCLUDED.codigo "
            "RETURNING estacion_id",
            (codigo,),
        )
        estacion_id = cursor.fetchone()[0]
        resultado[codigo] = estacion_id

    conn.commit()
    print(f"✓ Cargadas {len(resultado)} estaciones")
    return resultado


def load_estacion_periodos(conn, periodos_df: pl.DataFrame, stations_data: dict) -> None:
    """Cargar tabla estacion_periodo (SCD Type 2) desde CSV de análisis."""
    cursor = conn.cursor()

    count = 0
    for row in periodos_df.iter_rows(named=True):
        codigo = row["estacion"]
        if codigo not in stations_data:
            print(f"  WARN: estacion {codigo} no en catálogo, skip")
            continue

        # Obtener estacion_id
        cursor.execute(
            "SELECT estacion_id FROM rama.estacion WHERE codigo = %s",
            (codigo,),
        )
        result = cursor.fetchone()
        if not result:
            print(f"  WARN: estacion {codigo} no encontrada en BD, skip")
            continue
        estacion_id = result[0]

        estacion_info = stations_data[codigo]
        fecha_inicio = row["fecha_inicio"]
        fecha_fin = row["fecha_fin"]

        # Verificar que no existe ya este período
        cursor.execute(
            """
            SELECT 1 FROM rama.estacion_periodo
            WHERE estacion_id = %s AND fecha_inicio = %s AND fecha_fin = %s
            """,
            (estacion_id, fecha_inicio, fecha_fin),
        )
        if cursor.fetchone():
            continue  # Ya existe, skip

        cursor.execute(
            """
            INSERT INTO rama.estacion_periodo
            (estacion_id, nombre_estacion, alcaldia, latitud, longitud,
             fecha_inicio, fecha_fin, activo)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                estacion_id,
                estacion_info.get("nombre"),
                estacion_info.get("alcaldia"),
                estacion_info.get("lat"),
                estacion_info.get("lon"),
                fecha_inicio,
                fecha_fin,
                True,
            ),
        )

        count += cursor.rowcount

    conn.commit()
    print(f"✓ Cargados {count} periodos de estación")


def load_mediciones_anio(
    conn,
    df_parquet: pl.DataFrame,
    estacion_id_map: dict[str, int],
    anio: int,
) -> tuple[int, int]:
    """
    Cargar mediciones de un año específico usando COPY (bulk insert).
    Retorna (filas_insertadas, filas_rechazadas).
    """
    # Filtrar por año
    df_anio = df_parquet.filter(
        pl.col("FECHA").dt.year() == anio
    )

    if df_anio.height == 0:
        return 0, 0

    # Transformar a formato compatible con medicion tabla
    import io
    from datetime import timedelta

    filas_para_copiar = []
    filas_rechazadas = 0

    for row in df_anio.iter_rows(named=True):
        estacion_codigo = row["estacion"]
        if estacion_codigo not in estacion_id_map:
            filas_rechazadas += 1
            continue

        estacion_id = estacion_id_map[estacion_codigo]
        contaminante = row["contaminante"]
        valor = row["valor"]

        # Combinar FECHA + HORA en TIMESTAMP
        fecha = row["FECHA"]
        hora = row["HORA"]
        medido_en = datetime.combine(
            fecha,
            (datetime.min + timedelta(hours=hora)).time()
        )

        # Formato: tab-separated, compatible con COPY
        valor_str = str(valor) if valor is not None else "\\N"
        filas_para_copiar.append(
            f"{medido_en}\t{estacion_id}\t{contaminante}\t{valor_str}\n"
        )

    if not filas_para_copiar:
        return 0, filas_rechazadas

    # Usar COPY para bulk insert (mucho más rápido que INSERT uno a uno)
    cursor = conn.cursor()
    csv_buffer = io.StringIO("".join(filas_para_copiar))

    try:
        with cursor.copy(
            "COPY rama.medicion (medido_en, estacion_id, contaminante_codigo, valor) "
            "FROM STDIN"
        ) as copy:
            copy.write("".join(filas_para_copiar))
        filas_insertadas = len(filas_para_copiar)
    except Exception as e:
        print(f"  ERROR en COPY: {e}")
        filas_insertadas = 0

    conn.commit()
    return filas_insertadas, filas_rechazadas


def registrar_lote(
    conn,
    anio: int,
    filas_insertadas: int,
    filas_rechazadas: int,
) -> None:
    """Registrar carga en tabla lote_carga."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO rama.lote_carga
        (anio, archivo_origen, filas_insertadas, filas_rechazadas)
        VALUES (%s, %s, %s, %s)
        """,
        (anio, "rama_historica.parquet", filas_insertadas, filas_rechazadas),
    )
    conn.commit()


def main():
    """Ejecuta ingesta completa o parcial."""
    anio_especifico = None
    if len(sys.argv) > 1 and sys.argv[1] == "--anio":
        if len(sys.argv) > 2:
            try:
                anio_especifico = int(sys.argv[2])
            except ValueError:
                print(f"ERROR: año inválido: {sys.argv[2]}")
                return

    # Validar archivos
    if not PARQUET_PATH.exists():
        print(f"ERROR: {PARQUET_PATH} no existe")
        return
    if not STATIONS_PATH.exists():
        print(f"ERROR: {STATIONS_PATH} no existe")
        return
    if not PERIODOS_PATH.exists():
        print(f"ERROR: {PERIODOS_PATH} no existe")
        return

    print("=" * 80)
    print("INGESTA BATCH — RAMA OLTP")
    print("=" * 80)
    print()

    # Conectar a BD
    try:
        conn = psycopg.connect(DATABASE_URL)
        print("✓ Conectado a PostgreSQL")
    except Exception as e:
        print(f"ERROR conectando a BD: {e}")
        return

    try:
        # 1. Cargar catálogo de estaciones
        print("\n[1/4] Cargando catálogo de estaciones...")
        with open(STATIONS_PATH) as f:
            stations_data = json.load(f)
        estacion_id_map = load_estaciones(conn, stations_data)

        # 2. Cargar períodos de estaciones
        print("\n[2/4] Cargando períodos de estaciones (SCD Type 2)...")
        periodos_df = pl.read_csv(PERIODOS_PATH)
        load_estacion_periodos(conn, periodos_df, stations_data)

        # 3. Cargar mediciones
        print("\n[3/4] Cargando mediciones horarias...")
        df = pl.read_parquet(PARQUET_PATH)
        anios = sorted(df["FECHA"].dt.year().unique().to_list())

        if anio_especifico:
            anios = [y for y in anios if y == anio_especifico]
            if not anios:
                print(f"  No hay datos para año {anio_especifico}")
        total_insertadas = 0
        total_rechazadas = 0

        for i, anio in enumerate(anios, 1):
            insertadas, rechazadas = load_mediciones_anio(
                conn, df, estacion_id_map, anio
            )
            registrar_lote(conn, anio, insertadas, rechazadas)
            total_insertadas += insertadas
            total_rechazadas += rechazadas
            pct_validas = (
                100 * insertadas / (insertadas + rechazadas)
                if (insertadas + rechazadas) > 0
                else 0
            )
            print(
                f"  {anio}: {insertadas:,} OK, {rechazadas:,} REJECT "
                f"({pct_validas:.1f}% válidas)"
            )

        print(f"\n  Total: {total_insertadas:,} insertadas, {total_rechazadas:,} rechazadas")

        # 4. Validación
        print("\n[4/4] Validación...")
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM rama.estacion")
        n_estaciones = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM rama.estacion_periodo")
        n_periodos = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM rama.contaminante")
        n_contaminantes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM rama.medicion")
        n_mediciones = cursor.fetchone()[0]

        print(f"  Estaciones: {n_estaciones}")
        print(f"  Periodos: {n_periodos}")
        print(f"  Contaminantes: {n_contaminantes}")
        print(f"  Mediciones: {n_mediciones:,}")

        print()
        print("=" * 80)
        print("✓ INGESTA COMPLETADA")
        print("=" * 80)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
