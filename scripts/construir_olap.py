"""
Construir cubo OLAP (snowflake) sobre datos OLTP de RAMA.

Lee schema rama.* (OLTP cargado) y puebla rama_olap.* (dimensiones + fact + agregados).
Limpia datos sucios (alcaldías con HTML entities), deduplica, calcula índices normalizados,
y genera vistas materializadas de agregación para performance del dashboard.

Uso:
  uv run python scripts/construir_olap.py
  uv run python scripts/construir_olap.py --anio 2020   (reconstruir solo un año)

DDL se ejecuta desde docker/postgres/olap/*.sql en orden.
"""

import html
import os
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from psycopg import sql


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rama:rama@localhost:5433/rama",  # sólo default de desarrollo
)
OLAP_SQL_DIR = Path("docker/postgres/olap")


# Mapeo fijo: variantes sucias (HTML entities + typos) → nombre canónico
MAPEO_ALCALDIAS_LIMPIAS = {
    # CDMX (16 alcaldías oficiales)
    "Álvaro Obregón": "Álvaro Obregón",
    "Alvaro Obregon": "Álvaro Obregón",  # typo + sin tilde
    "&Aacute;lvaro Obreg&oacute;n": "Álvaro Obregón",
    "Azcapotzalco": "Azcapotzalco",
    "Benito Juárez": "Benito Juárez",
    "Benito Juarez": "Benito Juárez",
    "Coyoacán": "Coyoacán",
    "Coyoacan": "Coyoacán",
    "Coyoac&aacute;n": "Coyoacán",
    "Cuajimalpa de Morelos": "Cuajimalpa de Morelos",
    "Cuauhtémoc": "Cuauhtémoc",
    "Cuauhtemoc": "Cuauhtémoc",
    "Cuauht&eacute;moc": "Cuauhtémoc",
    "Gustavo A. Madero": "Gustavo A. Madero",
    "Iztacalco": "Iztacalco",
    "Iztapalapa": "Iztapalapa",
    "Magdalena Contreras": "Magdalena Contreras",
    "Miguel Hidalgo": "Miguel Hidalgo",
    "Milpa Alta": "Milpa Alta",
    "Tláhuac": "Tláhuac",
    "Tlalpan": "Tlalpan",
    "Venustiano Carranza": "Venustiano Carranza",
    "Xochimilco": "Xochimilco",
    # Estado de México (12 municipios)
    "Acolman": "Acolman",
    "Atizapán de Zaragoza": "Atizapán de Zaragoza",
    "Atizap&aacute;n de Zaragoza": "Atizapán de Zaragoza",
    "Chalco": "Chalco",
    "Coacalco de Berriozábal": "Coacalco de Berriozábal",
    "Coacalco de Berrioz&aacute;bal": "Coacalco de Berriozábal",
    "Cuautitlán Izcalli": "Cuautitlán Izcalli",
    "Cuautitl&aacute;n Izcalli": "Cuautitlán Izcalli",
    "Ecatepec de Morelos": "Ecatepec de Morelos",
    "Naucalpan de Juárez": "Naucalpan de Juárez",
    "Naucalpan de Ju&aacute;rez": "Naucalpan de Juárez",
    "Nezahualcóyotl": "Nezahualcóyotl",
    "Nezahualcoyotl": "Nezahualcóyotl",
    "Ocoyoacac": "Ocoyoacac",
    "Texcoco": "Texcoco",
    "Tlalnepantla de Baz": "Tlalnepantla de Baz",
    "Tultitlán": "Tultitlán",
}

# Mapeo: alcaldía canónica → entidad (CDMX o Estado de México)
MAPEO_ENTIDAD = {
    "Álvaro Obregón": "CDMX",
    "Azcapotzalco": "CDMX",
    "Benito Juárez": "CDMX",
    "Coyoacán": "CDMX",
    "Cuajimalpa de Morelos": "CDMX",
    "Cuauhtémoc": "CDMX",
    "Gustavo A. Madero": "CDMX",
    "Iztacalco": "CDMX",
    "Iztapalapa": "CDMX",
    "Magdalena Contreras": "CDMX",
    "Miguel Hidalgo": "CDMX",
    "Milpa Alta": "CDMX",
    "Tláhuac": "CDMX",
    "Tlalpan": "CDMX",
    "Venustiano Carranza": "CDMX",
    "Xochimilco": "CDMX",
    "Acolman": "Estado de México",
    "Atizapán de Zaragoza": "Estado de México",
    "Chalco": "Estado de México",
    "Coacalco de Berriozábal": "Estado de México",
    "Cuautitlán Izcalli": "Estado de México",
    "Ecatepec de Morelos": "Estado de México",
    "Naucalpan de Juárez": "Estado de México",
    "Nezahualcóyotl": "Estado de México",
    "Ocoyoacac": "Estado de México",
    "Texcoco": "Estado de México",
    "Tlalnepantla de Baz": "Estado de México",
    "Tultitlán": "Estado de México",
}


def limpiar_alcaldia(nombre_sucio: str) -> str:
    """Decodificar HTML entities y normalizar nombre de alcaldía."""
    # Primero intentar mapeo directo (más rápido)
    if nombre_sucio in MAPEO_ALCALDIAS_LIMPIAS:
        return MAPEO_ALCALDIAS_LIMPIAS[nombre_sucio]
    # Si no está, decodificar HTML entities y reintentar
    decodificado = html.unescape(nombre_sucio).strip()
    if decodificado in MAPEO_ALCALDIAS_LIMPIAS:
        return MAPEO_ALCALDIAS_LIMPIAS[decodificado]
    # Última opción: buscar en valores (case-insensitive)
    for variante, canonica in MAPEO_ALCALDIAS_LIMPIAS.items():
        if variante.lower() == decodificado.lower():
            return canonica
    # Si no encontró, retornar decodificado + warning
    print(f"  WARN: alcaldía no reconocida: '{nombre_sucio}' → '{decodificado}'")
    return decodificado


def ejecutar_sql_archivo(conn, ruta_sql: Path) -> None:
    """Ejecutar archivo SQL."""
    with open(ruta_sql) as f:
        sql_text = f.read()
    cursor = conn.cursor()
    cursor.execute(sql_text)
    conn.commit()
    print(f"  ✓ {ruta_sql.name}")


def crear_schema_y_dimensiones(conn) -> None:
    """Ejecutar DDL: schema, dimensiones, fact, agregados."""
    print("\n[1/6] Creando schema y dimensiones...")
    archivos = sorted(OLAP_SQL_DIR.glob("*.sql"))
    for archivo in archivos:
        ejecutar_sql_archivo(conn, archivo)


def pueblar_alcaldias(conn) -> None:
    """Pueblar dim_alcaldia: limpiar alcaldías de rama.estacion_periodo."""
    print("\n[2/6] Limpiando y poblando dim_alcaldia...")
    cursor = conn.cursor()

    # Obtener alcaldías únicas del OLTP
    cursor.execute(
        "SELECT DISTINCT alcaldia FROM rama.estacion_periodo ORDER BY alcaldia"
    )
    alcaldias_sucias = [row[0] for row in cursor.fetchall()]

    # Limpiar y deduplicar
    alcaldias_limpias = {}
    for sucia in alcaldias_sucias:
        canonica = limpiar_alcaldia(sucia)
        if canonica not in alcaldias_limpias:
            alcaldias_limpias[canonica] = MAPEO_ENTIDAD.get(canonica, "Desconocido")

    # Insertar
    for nombre, entidad in sorted(alcaldias_limpias.items()):
        cursor.execute(
            """
            INSERT INTO rama_olap.dim_alcaldia (nombre_alcaldia, entidad)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
            """,
            (nombre, entidad),
        )

    conn.commit()
    print(f"  ✓ Pobladas {len(alcaldias_limpias)} alcaldías limpias (deduplicadas de {len(alcaldias_sucias)})")


def pueblar_contaminantes_y_categorias(conn) -> None:
    """Pueblar dim_categoria_contaminante y dim_contaminante desde rama."""
    print("\n[3/6] Poblando contaminantes y categorías...")

    # Mapeo contaminante → categoría
    mapeo_cat = {
        "CO": "Gases",
        "NO": "Gases",
        "NO2": "Gases",
        "NOX": "Gases",
        "O3": "Gases",
        "SO2": "Gases",
        "PM10": "Partículas",
        "PM25": "Partículas",
        "PMCO": "Partículas",
    }

    # Leer primero todas las categorías
    cursor = conn.cursor()
    cursor.execute(
        "SELECT nombre_categoria, categoria_id FROM rama_olap.dim_categoria_contaminante"
    )
    mapeo_categoria_id = {nombre: cid for nombre, cid in cursor.fetchall()}

    # Leer contaminantes de OLTP
    cursor.execute("SELECT codigo, nombre, unidad, valor_min, valor_max FROM rama.contaminante")
    contaminantes = cursor.fetchall()

    # Ahora insertar (cursor nuevo para no interferir)
    cursor = conn.cursor()
    for codigo, nombre, unidad, valor_min, valor_max in contaminantes:
        categoria = mapeo_cat.get(codigo.strip(), "Desconocido")
        categoria_id = mapeo_categoria_id.get(categoria)

        cursor.execute(
            """
            INSERT INTO rama_olap.dim_contaminante
            (codigo, nombre, unidad, categoria_id, valor_min, valor_max)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (codigo) DO NOTHING
            """,
            (codigo, nombre, unidad, categoria_id, valor_min, valor_max),
        )

    conn.commit()
    print(f"  ✓ Pobladas dim_contaminante (9 contaminantes)")


def pueblar_estaciones(conn) -> None:
    """Pueblar dim_estacion desde rama.estacion_periodo (período más reciente por estación)."""
    print("\n[4/6] Poblando dim_estacion...")
    cursor = conn.cursor()

    # Obtener período más reciente de cada estación (por fecha_fin DESC NULL FIRST, o fecha_inicio)
    cursor.execute(
        """
        SELECT
            e.estacion_id,
            e.codigo,
            ep.nombre_estacion,
            ep.alcaldia,
            ep.latitud,
            ep.longitud,
            ep.activo
        FROM rama.estacion e
        JOIN (
            SELECT DISTINCT ON (estacion_id)
                estacion_id, nombre_estacion, alcaldia, latitud, longitud, activo
            FROM rama.estacion_periodo
            ORDER BY estacion_id, fecha_fin DESC NULLS FIRST, fecha_inicio DESC
        ) ep ON e.estacion_id = ep.estacion_id
        ORDER BY e.estacion_id
        """
    )

    insertadas = 0
    for estacion_id, codigo, nombre, alcaldia_sucia, lat, lon, activo in cursor.fetchall():
        # Limpiar alcaldía
        alcaldia_limpia = limpiar_alcaldia(alcaldia_sucia)

        # Obtener alcaldia_id
        cursor.execute(
            "SELECT alcaldia_id FROM rama_olap.dim_alcaldia WHERE nombre_alcaldia = %s",
            (alcaldia_limpia,),
        )
        alcaldia_row = cursor.fetchone()
        if not alcaldia_row:
            print(f"  WARN: alcaldía '{alcaldia_limpia}' no encontrada en dim_alcaldia")
            continue

        alcaldia_id = alcaldia_row[0]

        cursor.execute(
            """
            INSERT INTO rama_olap.dim_estacion
            (estacion_id, codigo, nombre_estacion, alcaldia_id, latitud, longitud, activo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (estacion_id) DO NOTHING
            """,
            (estacion_id, codigo, nombre, alcaldia_id, lat, lon, activo),
        )
        insertadas += 1

    conn.commit()
    print(f"  ✓ Pobladas {insertadas} estaciones")


def pueblar_tiempo(conn) -> None:
    """Pueblar dim_tiempo vía generate_series (rápido)."""
    print("\n[5/6] Generando dim_tiempo (1986-2025)...")
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO rama_olap.dim_tiempo
        (tiempo_id, fecha_hora, fecha, anio, trimestre, mes, dia, hora, dia_semana,
         es_fin_semana, estacion_del_anio)
        SELECT
            (EXTRACT(EPOCH FROM fh) * 3600)::BIGINT as tiempo_id,
            fh as fecha_hora,
            DATE(fh) as fecha,
            EXTRACT(YEAR FROM fh)::SMALLINT as anio,
            CEIL(EXTRACT(MONTH FROM fh) / 3.0)::SMALLINT as trimestre,
            EXTRACT(MONTH FROM fh)::SMALLINT as mes,
            EXTRACT(DAY FROM fh)::SMALLINT as dia,
            EXTRACT(HOUR FROM fh)::SMALLINT as hora,
            CASE WHEN EXTRACT(ISODOW FROM fh)::SMALLINT IN (6, 7) THEN 7 ELSE EXTRACT(ISODOW FROM fh)::SMALLINT END as dia_semana,
            EXTRACT(ISODOW FROM fh)::SMALLINT IN (6, 7) as es_fin_semana,
            CASE
                WHEN EXTRACT(MONTH FROM fh)::SMALLINT IN (12, 1, 2) THEN 'Invierno'
                WHEN EXTRACT(MONTH FROM fh)::SMALLINT IN (3, 4, 5) THEN 'Primavera'
                WHEN EXTRACT(MONTH FROM fh)::SMALLINT IN (6, 7, 8) THEN 'Verano'
                ELSE 'Otoño'
            END as estacion_del_anio
        FROM GENERATE_SERIES('1986-01-01 00:00:00'::TIMESTAMP, '2025-12-31 23:00:00'::TIMESTAMP, '1 hour'::INTERVAL) fh
        ON CONFLICT DO NOTHING
        """
    )
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM rama_olap.dim_tiempo")
    count = cursor.fetchone()[0]
    print(f"  ✓ Generadas {count:,} horas (1986-2025)")


# Índices de la fact table (mismos que 03_fact.sql). Se sueltan durante la carga
# completa: mantener ~2.7 GB de índices vivos durante un INSERT de 50M filas es lo
# que volvía interminable la carga. Reconstruirlos en bloque toma ~30 s.
INDICES_FACT = {
    "idx_fact_medicion_estacion_tiempo": "(estacion_id, tiempo_id)",
    "idx_fact_medicion_contaminante_tiempo": "(contaminante_id, tiempo_id)",
    "idx_fact_medicion_tiempo": "(tiempo_id)",
    "idx_fact_medicion_est_cont": "(estacion_id, contaminante_id)",
}

FKS_FACT = {
    "fact_medicion_hora_tiempo_id_fkey": "(tiempo_id) REFERENCES rama_olap.dim_tiempo",
    "fact_medicion_hora_estacion_id_fkey": "(estacion_id) REFERENCES rama_olap.dim_estacion",
    "fact_medicion_hora_contaminante_id_fkey": "(contaminante_id) REFERENCES rama_olap.dim_contaminante",
}

SELECT_FACT = """
    SELECT
        (EXTRACT(EPOCH FROM m.medido_en) * 3600)::BIGINT as tiempo_id,
        m.estacion_id,
        dc.contaminante_id,
        m.valor,
        CASE
            WHEN m.valor IS NULL THEN NULL
            ELSE ROUND((100.0 * (m.valor - dc.valor_min) / (dc.valor_max - dc.valor_min))::NUMERIC, 1)::REAL
        END as indice_normalizado
    FROM rama.medicion m
    JOIN rama_olap.dim_contaminante dc ON m.contaminante_codigo = dc.codigo
"""


def pueblar_fact_mediciones(conn, anio_especifico: int = None) -> None:
    """
    Pueblar fact_medicion_hora desde rama.medicion (con índice normalizado).

    Carga completa: suelta índices y FKs, TRUNCATE, INSERT, y los reconstruye
    (~90 s para 50.3M filas). Con --anio se reemplaza sólo ese año y los índices
    se dejan en su lugar (el volumen es 40x menor).
    """
    print("\n[6/6] Poblando fact_medicion_hora...")
    cursor = conn.cursor()

    if anio_especifico:
        cursor.execute(
            """
            DELETE FROM rama_olap.fact_medicion_hora f
            USING rama_olap.dim_tiempo dt
            WHERE f.tiempo_id = dt.tiempo_id AND dt.anio = %s
            """,
            [anio_especifico],
        )
        print(f"  · Borradas {cursor.rowcount:,} filas previas de {anio_especifico}")

        cursor.execute(
            f"""
            INSERT INTO rama_olap.fact_medicion_hora
            (tiempo_id, estacion_id, contaminante_id, valor, indice_normalizado)
            {SELECT_FACT}
            WHERE EXTRACT(YEAR FROM m.medido_en)::INT = %s
            """,
            [anio_especifico],
        )
        total = cursor.rowcount
        conn.commit()
        print(f"  ✓ {total:,} mediciones recargadas para {anio_especifico}")
        return

    # Carga completa
    cursor.execute("SET maintenance_work_mem = '512MB'")
    cursor.execute("SET work_mem = '256MB'")

    print("  · Soltando FKs e índices...")
    for nombre in FKS_FACT:
        cursor.execute(
            sql.SQL("ALTER TABLE rama_olap.fact_medicion_hora DROP CONSTRAINT IF EXISTS {}")
            .format(sql.Identifier(nombre))
        )
    for nombre in INDICES_FACT:
        cursor.execute(
            sql.SQL("DROP INDEX IF EXISTS rama_olap.{}").format(sql.Identifier(nombre))
        )
    conn.commit()

    cursor.execute("TRUNCATE rama_olap.fact_medicion_hora")
    print("  · Insertando (heap sin índices)...")
    cursor.execute(
        f"""
        INSERT INTO rama_olap.fact_medicion_hora
        (tiempo_id, estacion_id, contaminante_id, valor, indice_normalizado)
        {SELECT_FACT}
        """
    )
    total = cursor.rowcount
    conn.commit()

    print("  · Reconstruyendo índices...")
    for nombre, columnas in INDICES_FACT.items():
        cursor.execute(
            sql.SQL(
                "CREATE INDEX {} ON rama_olap.fact_medicion_hora "
                + columnas
                + " WHERE valor IS NOT NULL"
            ).format(sql.Identifier(nombre))
        )
    conn.commit()

    print("  · Restaurando FKs...")
    for nombre, definicion in FKS_FACT.items():
        cursor.execute(
            sql.SQL("ALTER TABLE rama_olap.fact_medicion_hora ADD CONSTRAINT {} FOREIGN KEY " + definicion)
            .format(sql.Identifier(nombre))
        )
    cursor.execute("ANALYZE rama_olap.fact_medicion_hora")
    conn.commit()

    print(f"  ✓ Total: {total:,} mediciones en fact_medicion_hora")


def refrescar_agregados(conn) -> None:
    """Refrescar vistas materializadas."""
    print("\nRefrescando vistas materializadas...")
    cursor = conn.cursor()

    cursor.execute("REFRESH MATERIALIZED VIEW rama_olap.agg_medicion_diaria")
    cursor.execute("REFRESH MATERIALIZED VIEW rama_olap.agg_medicion_mensual")
    conn.commit()
    print("  ✓ agg_medicion_diaria")
    print("  ✓ agg_medicion_mensual")


def validar_carga(conn) -> None:
    """Validación final: conteos de dimensiones y fact."""
    print("\n" + "=" * 80)
    print("VALIDACIÓN FINAL")
    print("=" * 80)

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            (SELECT COUNT(*) FROM rama_olap.dim_tiempo) as dim_tiempo,
            (SELECT COUNT(*) FROM rama_olap.dim_alcaldia) as dim_alcaldia,
            (SELECT COUNT(*) FROM rama_olap.dim_categoria_contaminante) as dim_categoria,
            (SELECT COUNT(*) FROM rama_olap.dim_contaminante) as dim_contaminante,
            (SELECT COUNT(*) FROM rama_olap.dim_estacion) as dim_estacion,
            (SELECT COUNT(*) FROM rama_olap.fact_medicion_hora) as fact_medicion,
            (SELECT COUNT(*) FROM rama_olap.agg_medicion_diaria) as agg_diaria,
            (SELECT COUNT(*) FROM rama_olap.agg_medicion_mensual) as agg_mensual
        """
    )
    row = cursor.fetchone()
    print(f"  dim_tiempo:                  {row[0]:>12,}")
    print(f"  dim_alcaldia (limpia):       {row[1]:>12,}  (de 31 sucias → {row[1]} canónicas)")
    print(f"  dim_categoria_contaminante:  {row[2]:>12,}")
    print(f"  dim_contaminante:            {row[3]:>12,}")
    print(f"  dim_estacion (vigente):      {row[4]:>12,}")
    print(f"  fact_medicion_hora:          {row[5]:>12,}")
    print(f"  agg_medicion_diaria:         {row[6]:>12,}")
    print(f"  agg_medicion_mensual:        {row[7]:>12,}")


def main():
    """Ejecutar construcción completa del cubo OLAP."""
    anio_especifico = None
    if len(sys.argv) > 1 and sys.argv[1] == "--anio":
        if len(sys.argv) > 2:
            try:
                anio_especifico = int(sys.argv[2])
            except ValueError:
                print(f"ERROR: año inválido: {sys.argv[2]}")
                return

    print("=" * 80)
    print("CONSTRUCCIÓN CUBO OLAP — RAMA")
    print("=" * 80)

    try:
        conn = psycopg.connect(DATABASE_URL)
        print("✓ Conectado a PostgreSQL")

        crear_schema_y_dimensiones(conn)
        pueblar_alcaldias(conn)
        pueblar_contaminantes_y_categorias(conn)
        pueblar_estaciones(conn)
        pueblar_tiempo(conn)
        pueblar_fact_mediciones(conn, anio_especifico)
        refrescar_agregados(conn)
        validar_carga(conn)

        print("\n" + "=" * 80)
        print("✓ CUBO OLAP CONSTRUIDO EXITOSAMENTE")
        print("=" * 80)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
