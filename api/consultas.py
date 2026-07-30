"""
Consultas SQL contra el cubo OLAP (rama_olap.*).

Cada función ejecuta un query contra dimensiones/fact/agregados
y retorna datos compatibles con los schemas de respuesta.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from api.db import get_connection, return_connection


def obtener_dimensiones(tipo: str) -> List[dict]:
    """
    Obtener dimensiones: contaminantes, categorias, estaciones, alcaldias.

    Args:
        tipo: 'contaminantes', 'categorias', 'estaciones', 'alcaldias'

    Returns:
        Lista de dicts con items de la dimensión
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        if tipo == "contaminantes":
            cursor.execute("""
                SELECT contaminante_id, codigo, nombre, unidad, categoria_id
                FROM rama_olap.dim_contaminante
                ORDER BY codigo
            """)
            cols = ["contaminante_id", "codigo", "nombre", "unidad", "categoria_id"]

        elif tipo == "categorias":
            cursor.execute("""
                SELECT categoria_id, nombre_categoria
                FROM rama_olap.dim_categoria_contaminante
                ORDER BY nombre_categoria
            """)
            cols = ["categoria_id", "nombre_categoria"]

        elif tipo == "estaciones":
            cursor.execute("""
                SELECT estacion_id, codigo, nombre_estacion, alcaldia_id, latitud, longitud, activo
                FROM rama_olap.dim_estacion
                ORDER BY codigo
            """)
            cols = ["estacion_id", "codigo", "nombre_estacion", "alcaldia_id", "latitud", "longitud", "activo"]

        elif tipo == "alcaldias":
            cursor.execute("""
                SELECT alcaldia_id, nombre_alcaldia, entidad
                FROM rama_olap.dim_alcaldia
                ORDER BY nombre_alcaldia
            """)
            cols = ["alcaldia_id", "nombre_alcaldia", "entidad"]

        else:
            return []

        rows = cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]

    finally:
        return_connection(conn)


def obtener_rango_fechas_disponibles() -> Tuple[str, str]:
    """Obtener rango de fechas con datos en fact table."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MIN(dt.fecha)::DATE, MAX(dt.fecha)::DATE
            FROM rama_olap.fact_medicion_hora f
            JOIN rama_olap.dim_tiempo dt ON f.tiempo_id = dt.tiempo_id
            WHERE f.valor IS NOT NULL
        """)
        fecha_min, fecha_max = cursor.fetchone()
        return (fecha_min.isoformat() if fecha_min else "1986-01-01",
                fecha_max.isoformat() if fecha_max else "2025-12-31")
    finally:
        return_connection(conn)


def obtener_kpis(
    contaminante: Optional[str] = None,
    alcaldia_id: Optional[int] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
) -> dict:
    """
    Calcular KPIs: promedio índice, % completitud, estaciones, contaminantes, total mediciones.

    Si no se pasan fechas, usa últimos 12 meses.
    """
    conn = get_connection()
    try:
        # Resolver fechas por defecto
        if not fecha_fin:
            fecha_max_str, _ = obtener_rango_fechas_disponibles()
            fecha_fin_dt = datetime.fromisoformat(fecha_max_str)
        else:
            fecha_fin_dt = datetime.fromisoformat(fecha_fin)

        if not fecha_inicio:
            fecha_inicio_dt = fecha_fin_dt - timedelta(days=365)
        else:
            fecha_inicio_dt = datetime.fromisoformat(fecha_inicio)

        fecha_inicio_str = fecha_inicio_dt.date().isoformat()
        fecha_fin_str = fecha_fin_dt.date().isoformat()

        cursor = conn.cursor()

        # Construir filtros SQL dinámicos
        where_clauses = [
            f"dt.fecha >= '{fecha_inicio_str}'::DATE",
            f"dt.fecha <= '{fecha_fin_str}'::DATE",
        ]

        if contaminante:
            where_clauses.append(f"dc.codigo = '{contaminante}'")

        if alcaldia_id:
            where_clauses.append(f"de.alcaldia_id = {alcaldia_id}")

        where_clause = " AND ".join(where_clauses)

        cursor.execute(f"""
            SELECT
                ROUND(AVG(f.indice_normalizado)::NUMERIC, 1) as promedio_indice,
                ROUND(100.0 * COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END)
                      / NULLIF(COUNT(*), 0)::NUMERIC, 1) as pct_completitud,
                COUNT(DISTINCT f.estacion_id) as estaciones_activas,
                COUNT(DISTINCT f.contaminante_id) as contaminantes_monitoreados,
                COUNT(*) as total_mediciones
            FROM rama_olap.fact_medicion_hora f
            JOIN rama_olap.dim_tiempo dt ON f.tiempo_id = dt.tiempo_id
            JOIN rama_olap.dim_contaminante dc ON f.contaminante_id = dc.contaminante_id
            JOIN rama_olap.dim_estacion de ON f.estacion_id = de.estacion_id
            WHERE {where_clause}
        """)

        row = cursor.fetchone()
        if not row or row[0] is None:
            row = (0.0, 0.0, 0, 0, 0)

        return {
            "periodo": {
                "fecha_inicio": fecha_inicio_str,
                "fecha_fin": fecha_fin_str,
            },
            "promedio_indice_normalizado": float(row[0] or 0),
            "pct_completitud": float(row[1] or 0),
            "estaciones_activas": int(row[2] or 0),
            "contaminantes_monitoreados": int(row[3] or 0),
            "total_mediciones": int(row[4] or 0),
        }
    finally:
        return_connection(conn)


def obtener_series_tiempo(
    contaminante: str,
    granularidad: str = "dia",
    estacion: Optional[str] = None,
    alcaldia_id: Optional[int] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
) -> List[dict]:
    """
    Obtener serie de tiempo: valores agregados por granularidad (hora/dia/mes).

    Si granularidad='hora', requiere estacion y limita a 90 días.
    Lee de agregados (agg_medicion_diaria, agg_medicion_mensual) para performance.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Validar granularidad='hora'
        if granularidad == "hora":
            if not estacion:
                raise ValueError("granularidad='hora' requiere parámetro 'estacion'")
            if fecha_inicio and fecha_fin:
                f_inicio = datetime.fromisoformat(fecha_inicio)
                f_fin = datetime.fromisoformat(fecha_fin)
                if (f_fin - f_inicio).days > 90:
                    raise ValueError("granularidad='hora' limitada a 90 días máximo")

        # Resolver fechas
        if not fecha_fin:
            _, fecha_max_str = obtener_rango_fechas_disponibles()
            fecha_fin = fecha_max_str

        if not fecha_inicio:
            f = datetime.fromisoformat(fecha_fin)
            fecha_inicio = (f - timedelta(days=30)).date().isoformat()

        # Seleccionar tabla según granularidad
        if granularidad == "hora":
            # Direct from fact (guardrail: solo 90 días + estacion requerida)
            estacion_codigo = estacion.upper()
            cursor.execute(f"""
                SELECT
                    dt.fecha_hora::DATE::TEXT as fecha,
                    ROUND(AVG(f.valor)::NUMERIC, 2) as valor_promedio,
                    MIN(f.valor) as valor_min,
                    MAX(f.valor) as valor_max,
                    ROUND(AVG(f.indice_normalizado)::NUMERIC, 1) as indice_normalizado,
                    COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END) as mediciones_validas,
                    ROUND(100.0 * COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END)
                          / NULLIF(COUNT(*), 0)::NUMERIC, 1) as pct_completitud
                FROM rama_olap.fact_medicion_hora f
                JOIN rama_olap.dim_tiempo dt ON f.tiempo_id = dt.tiempo_id
                JOIN rama_olap.dim_contaminante dc ON f.contaminante_id = dc.contaminante_id
                JOIN rama_olap.dim_estacion de ON f.estacion_id = de.estacion_id
                WHERE dc.codigo = '{contaminante}'
                  AND de.codigo = '{estacion_codigo}'
                  AND dt.fecha >= '{fecha_inicio}'::DATE
                  AND dt.fecha <= '{fecha_fin}'::DATE
                GROUP BY dt.fecha_hora::DATE
                ORDER BY dt.fecha_hora ASC
            """)

        elif granularidad == "dia":
            tabla = "rama_olap.agg_medicion_diaria"
            where = f"dt.codigo = '{contaminante}' AND d.fecha >= '{fecha_inicio}'::DATE AND d.fecha <= '{fecha_fin}'::DATE"
            if estacion:
                where += f" AND de.codigo = '{estacion.upper()}'"
            if alcaldia_id:
                where += f" AND de.alcaldia_id = {alcaldia_id}"

            cursor.execute(f"""
                SELECT
                    d.fecha::TEXT,
                    d.valor_promedio,
                    d.valor_minimo,
                    d.valor_maximo,
                    d.indice_normalizado,
                    d.mediciones_validas,
                    d.pct_completitud
                FROM {tabla} d
                JOIN rama_olap.dim_contaminante dt ON d.contaminante_id = dt.contaminante_id
                JOIN rama_olap.dim_estacion de ON d.estacion_id = de.estacion_id
                WHERE {where}
                ORDER BY d.fecha ASC
            """)

        elif granularidad == "mes":
            tabla = "rama_olap.agg_medicion_mensual"
            where = f"dt.codigo = '{contaminante}' AND m.fecha_primer_dia_mes >= '{fecha_inicio}'::DATE AND m.fecha_primer_dia_mes <= '{fecha_fin}'::DATE"
            if estacion:
                where += f" AND de.codigo = '{estacion.upper()}'"
            if alcaldia_id:
                where += f" AND de.alcaldia_id = {alcaldia_id}"

            cursor.execute(f"""
                SELECT
                    m.fecha_primer_dia_mes::TEXT,
                    m.valor_promedio,
                    m.valor_minimo,
                    m.valor_maximo,
                    m.indice_normalizado,
                    m.mediciones_validas,
                    m.pct_completitud
                FROM {tabla} m
                JOIN rama_olap.dim_contaminante dt ON m.contaminante_id = dt.contaminante_id
                JOIN rama_olap.dim_estacion de ON m.estacion_id = de.estacion_id
                WHERE {where}
                ORDER BY m.fecha_primer_dia_mes ASC
            """)

        else:
            raise ValueError("granularidad inválida")

        rows = cursor.fetchall()
        puntos = []
        for row in rows:
            puntos.append({
                "fecha": row[0],
                "valor_promedio": float(row[1]) if row[1] is not None else None,
                "valor_min": float(row[2]) if row[2] is not None else None,
                "valor_max": float(row[3]) if row[3] is not None else None,
                "indice_normalizado": float(row[4]) if row[4] is not None else None,
                "mediciones_validas": int(row[5] or 0),
                "pct_completitud": float(row[6] or 0),
            })

        return puntos

    finally:
        return_connection(conn)


def obtener_mapa_estaciones(
    contaminante: str,
    fecha: Optional[str] = None,
) -> Tuple[str, List[dict]]:
    """
    Última lectura por estación de un contaminante.

    Si no se pasa fecha, usa la última fecha con datos.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Resolver fecha
        if not fecha:
            cursor.execute(f"""
                SELECT MAX(d.fecha)::TEXT
                FROM rama_olap.agg_medicion_diaria d
                JOIN rama_olap.dim_contaminante dc ON d.contaminante_id = dc.contaminante_id
                WHERE dc.codigo = '{contaminante}'
            """)
            fecha = cursor.fetchone()[0]
            if not fecha:
                fecha = "1986-01-01"

        cursor.execute(f"""
            SELECT
                de.estacion_id,
                de.codigo,
                de.nombre_estacion,
                da.nombre_alcaldia,
                de.latitud,
                de.longitud,
                d.valor_promedio,
                d.indice_normalizado
            FROM rama_olap.agg_medicion_diaria d
            JOIN rama_olap.dim_contaminante dc ON d.contaminante_id = dc.contaminante_id
            JOIN rama_olap.dim_estacion de ON d.estacion_id = de.estacion_id
            JOIN rama_olap.dim_alcaldia da ON de.alcaldia_id = da.alcaldia_id
            WHERE dc.codigo = '{contaminante}'
              AND d.fecha = '{fecha}'::DATE
            ORDER BY de.codigo
        """)

        rows = cursor.fetchall()
        estaciones = []
        for row in rows:
            estaciones.append({
                "estacion_id": int(row[0]),
                "codigo": row[1],
                "nombre": row[2],
                "alcaldia": row[3],
                "latitud": float(row[4]),
                "longitud": float(row[5]),
                "valor": float(row[6]) if row[6] is not None else None,
                "indice_normalizado": float(row[7]) if row[7] is not None else None,
            })

        return fecha, estaciones

    finally:
        return_connection(conn)


def obtener_ranking_estaciones(
    contaminante: str,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    orden: str = "desc",
    limit: int = 10,
) -> Tuple[str, str, List[dict]]:
    """Ranking de estaciones por índice normalizado (promedio del período)."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Resolver fechas
        if not fecha_fin:
            _, fecha_max_str = obtener_rango_fechas_disponibles()
            fecha_fin = fecha_max_str

        if not fecha_inicio:
            f = datetime.fromisoformat(fecha_fin)
            fecha_inicio = (f - timedelta(days=30)).date().isoformat()

        orden_sql = "DESC" if orden.lower() == "desc" else "ASC"

        cursor.execute(f"""
            WITH ranking AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY AVG(d.indice_normalizado) {orden_sql}) as posicion,
                    de.codigo,
                    de.nombre_estacion,
                    da.nombre_alcaldia,
                    ROUND(AVG(d.valor_promedio)::NUMERIC, 2) as valor_promedio,
                    ROUND(AVG(d.indice_normalizado)::NUMERIC, 1) as indice_normalizado
                FROM rama_olap.agg_medicion_diaria d
                JOIN rama_olap.dim_contaminante dc ON d.contaminante_id = dc.contaminante_id
                JOIN rama_olap.dim_estacion de ON d.estacion_id = de.estacion_id
                JOIN rama_olap.dim_alcaldia da ON de.alcaldia_id = da.alcaldia_id
                WHERE dc.codigo = '{contaminante}'
                  AND d.fecha >= '{fecha_inicio}'::DATE
                  AND d.fecha <= '{fecha_fin}'::DATE
                GROUP BY de.estacion_id, de.codigo, de.nombre_estacion, da.nombre_alcaldia
            )
            SELECT posicion, codigo, nombre_estacion, nombre_alcaldia, valor_promedio, indice_normalizado
            FROM ranking
            ORDER BY posicion ASC
            LIMIT {limit}
        """)

        rows = cursor.fetchall()
        ranking = []
        for row in rows:
            ranking.append({
                "posicion": int(row[0]),
                "codigo": row[1],
                "nombre": row[2],
                "alcaldia": row[3],
                "valor_promedio": float(row[4]) if row[4] is not None else None,
                "indice_normalizado": float(row[5]) if row[5] is not None else None,
            })

        return fecha_inicio, fecha_fin, ranking

    finally:
        return_connection(conn)


def obtener_ranking_contaminantes(
    estacion: Optional[str] = None,
    alcaldia_id: Optional[int] = None,
    fecha_inicio: Optional[str] = None,
    fecha_fin: Optional[str] = None,
    limit: int = 9,
) -> Tuple[str, str, List[dict]]:
    """Ranking de contaminantes por índice normalizado."""
    conn = get_connection()
    try:
        cursor = conn.cursor()

        # Resolver fechas
        if not fecha_fin:
            _, fecha_max_str = obtener_rango_fechas_disponibles()
            fecha_fin = fecha_max_str

        if not fecha_inicio:
            f = datetime.fromisoformat(fecha_fin)
            fecha_inicio = (f - timedelta(days=30)).date().isoformat()

        # Construir filtros
        filtros = [
            f"d.fecha >= '{fecha_inicio}'::DATE",
            f"d.fecha <= '{fecha_fin}'::DATE",
        ]

        if estacion:
            filtros.append(f"de.codigo = '{estacion.upper()}'")

        if alcaldia_id:
            filtros.append(f"de.alcaldia_id = {alcaldia_id}")

        where_clause = " AND ".join(filtros)

        cursor.execute(f"""
            WITH ranking AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY AVG(d.indice_normalizado) DESC) as posicion,
                    dc.codigo,
                    dc.nombre,
                    dcat.nombre_categoria,
                    ROUND(AVG(d.indice_normalizado)::NUMERIC, 1) as indice_promedio
                FROM rama_olap.agg_medicion_diaria d
                JOIN rama_olap.dim_contaminante dc ON d.contaminante_id = dc.contaminante_id
                JOIN rama_olap.dim_categoria_contaminante dcat ON dc.categoria_id = dcat.categoria_id
                JOIN rama_olap.dim_estacion de ON d.estacion_id = de.estacion_id
                WHERE {where_clause}
                GROUP BY dc.contaminante_id, dc.codigo, dc.nombre, dcat.nombre_categoria
            )
            SELECT posicion, codigo, nombre, nombre_categoria, indice_promedio
            FROM ranking
            ORDER BY posicion ASC
            LIMIT {limit}
        """)

        rows = cursor.fetchall()
        ranking = []
        for row in rows:
            ranking.append({
                "posicion": int(row[0]),
                "codigo": row[1],
                "nombre": row[2],
                "categoria": row[3],
                "indice_normalizado_promedio": float(row[4]) if row[4] is not None else None,
            })

        return fecha_inicio, fecha_fin, ranking

    finally:
        return_connection(conn)


def obtener_completitud(
    agrupar_por: str = "contaminante",
    contaminante: Optional[str] = None,
    estacion: Optional[str] = None,
    alcaldia_id: Optional[int] = None,
) -> List[dict]:
    """
    % de completitud agrupado por contaminante/estacion/año.

    Explota el hecho de que 18-38% son NULLs reales (sensor inactivo).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        if agrupar_por == "contaminante":
            cursor.execute("""
                SELECT
                    dc.codigo as clave,
                    dc.nombre as etiqueta,
                    COUNT(*) as mediciones_totales,
                    COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END) as mediciones_validas,
                    ROUND(100.0 * COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END)
                          / NULLIF(COUNT(*), 0)::NUMERIC, 1) as pct_completitud
                FROM rama_olap.fact_medicion_hora f
                JOIN rama_olap.dim_contaminante dc ON f.contaminante_id = dc.contaminante_id
                GROUP BY dc.contaminante_id, dc.codigo, dc.nombre
                ORDER BY dc.codigo
            """)

        elif agrupar_por == "estacion":
            cursor.execute("""
                SELECT
                    de.codigo as clave,
                    de.nombre_estacion as etiqueta,
                    COUNT(*) as mediciones_totales,
                    COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END) as mediciones_validas,
                    ROUND(100.0 * COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END)
                          / NULLIF(COUNT(*), 0)::NUMERIC, 1) as pct_completitud
                FROM rama_olap.fact_medicion_hora f
                JOIN rama_olap.dim_estacion de ON f.estacion_id = de.estacion_id
                GROUP BY de.estacion_id, de.codigo, de.nombre_estacion
                ORDER BY de.codigo
            """)

        elif agrupar_por == "anio":
            cursor.execute("""
                SELECT
                    CAST(dt.anio AS TEXT) as clave,
                    'Año ' || CAST(dt.anio AS TEXT) as etiqueta,
                    COUNT(*) as mediciones_totales,
                    COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END) as mediciones_validas,
                    ROUND(100.0 * COUNT(CASE WHEN f.valor IS NOT NULL THEN 1 END)
                          / NULLIF(COUNT(*), 0)::NUMERIC, 1) as pct_completitud
                FROM rama_olap.fact_medicion_hora f
                JOIN rama_olap.dim_tiempo dt ON f.tiempo_id = dt.tiempo_id
                GROUP BY dt.anio
                ORDER BY dt.anio DESC
            """)

        else:
            raise ValueError("agrupar_por inválido")

        rows = cursor.fetchall()
        items = []
        for row in rows:
            items.append({
                "clave": row[0],
                "etiqueta": row[1],
                "mediciones_totales": int(row[2]),
                "mediciones_validas": int(row[3]),
                "pct_completitud": float(row[4] or 0),
            })

        return items

    finally:
        return_connection(conn)
