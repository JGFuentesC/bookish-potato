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
                SELECT contaminante_id, TRIM(codigo) AS codigo, nombre, unidad, categoria_id
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
                SELECT estacion_id, TRIM(codigo) AS codigo, nombre_estacion, alcaldia_id, latitud, longitud, activo
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
    """
    Obtener rango de fechas con datos.

    Se resuelve sobre agg_medicion_diaria (2M filas) y no sobre la fact de 50M:
    esta función se llama en cada request que no trae fechas explícitas.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MIN(fecha)::DATE, MAX(fecha)::DATE
            FROM rama_olap.agg_medicion_diaria
            WHERE mediciones_validas > 0
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
            _, fecha_max_str = obtener_rango_fechas_disponibles()
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

        # Filtros dinámicos con placeholders — los valores nunca se interpolan
        where_clauses = ["d.fecha >= %s::DATE", "d.fecha <= %s::DATE"]
        params: list = [fecha_inicio_str, fecha_fin_str]

        if contaminante:
            where_clauses.append("dc.codigo = %s")
            params.append(contaminante)

        if alcaldia_id:
            where_clauses.append("de.alcaldia_id = %s")
            params.append(alcaldia_id)

        where_clause = " AND ".join(where_clauses)

        # Se lee del agregado diario, no de la fact de 50M: sobre la fact este
        # query tardaba ~3.5 s
        cursor.execute(f"""
            SELECT
                ROUND(AVG(d.indice_normalizado)::NUMERIC, 1) as promedio_indice,
                ROUND(100.0 * SUM(d.mediciones_validas)
                      / NULLIF(SUM(d.mediciones_totales), 0)::NUMERIC, 1) as pct_completitud,
                COUNT(DISTINCT d.estacion_id) as estaciones_activas,
                COUNT(DISTINCT d.contaminante_id) as contaminantes_monitoreados,
                COALESCE(SUM(d.mediciones_totales), 0) as total_mediciones
            FROM rama_olap.agg_medicion_diaria d
            JOIN rama_olap.dim_contaminante dc ON d.contaminante_id = dc.contaminante_id
            JOIN rama_olap.dim_estacion de ON d.estacion_id = de.estacion_id
            WHERE {where_clause}
        """, params)

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
            # Ventana por defecto según granularidad: con 30 días la vista
            # mensual devolvía un solo punto
            dias_default = {"hora": 7, "dia": 30, "mes": 730}.get(granularidad, 30)
            f = datetime.fromisoformat(fecha_fin)
            fecha_inicio = (f - timedelta(days=dias_default)).date().isoformat()

        # Seleccionar tabla según granularidad
        if granularidad == "hora":
            # Direct from fact (guardrail: solo 90 días + estacion requerida)
            estacion_codigo = estacion.upper()
            cursor.execute(f"""
                SELECT
                    dt.fecha_hora::TEXT as fecha,
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
                WHERE dc.codigo = %s
                  AND de.codigo = %s
                  AND dt.fecha >= %s::DATE
                  AND dt.fecha <= %s::DATE
                GROUP BY dt.fecha_hora
                ORDER BY dt.fecha_hora ASC
            """, [contaminante, estacion_codigo, fecha_inicio, fecha_fin])

        elif granularidad == "dia":
            tabla = "rama_olap.agg_medicion_diaria"
            where = "dt.codigo = %s AND d.fecha >= %s::DATE AND d.fecha <= %s::DATE"
            params: list = [contaminante, fecha_inicio, fecha_fin]
            if estacion:
                where += " AND de.codigo = %s"
                params.append(estacion.upper())
            if alcaldia_id:
                where += " AND de.alcaldia_id = %s"
                params.append(alcaldia_id)

            # Agregamos sobre estaciones: un punto por fecha (si no, el gráfico
            # recibe una fila por estación y los puntos se duplican)
            cursor.execute(f"""
                SELECT
                    d.fecha::TEXT,
                    ROUND(AVG(d.valor_promedio)::NUMERIC, 2),
                    MIN(d.valor_minimo),
                    MAX(d.valor_maximo),
                    ROUND(AVG(d.indice_normalizado)::NUMERIC, 1),
                    SUM(d.mediciones_validas),
                    ROUND(100.0 * SUM(d.mediciones_validas)
                          / NULLIF(SUM(d.mediciones_totales), 0)::NUMERIC, 1)
                FROM {tabla} d
                JOIN rama_olap.dim_contaminante dt ON d.contaminante_id = dt.contaminante_id
                JOIN rama_olap.dim_estacion de ON d.estacion_id = de.estacion_id
                WHERE {where}
                GROUP BY d.fecha
                ORDER BY d.fecha ASC
            """, params)

        elif granularidad == "mes":
            tabla = "rama_olap.agg_medicion_mensual"
            where = ("dt.codigo = %s AND m.fecha_primer_dia_mes >= %s::DATE "
                     "AND m.fecha_primer_dia_mes <= %s::DATE")
            params = [contaminante, fecha_inicio, fecha_fin]
            if estacion:
                where += " AND de.codigo = %s"
                params.append(estacion.upper())
            if alcaldia_id:
                where += " AND de.alcaldia_id = %s"
                params.append(alcaldia_id)

            cursor.execute(f"""
                SELECT
                    m.fecha_primer_dia_mes::TEXT,
                    ROUND(AVG(m.valor_promedio)::NUMERIC, 2),
                    MIN(m.valor_minimo),
                    MAX(m.valor_maximo),
                    ROUND(AVG(m.indice_normalizado)::NUMERIC, 1),
                    SUM(m.mediciones_validas),
                    ROUND(100.0 * SUM(m.mediciones_validas)
                          / NULLIF(SUM(m.mediciones_totales), 0)::NUMERIC, 1)
                FROM {tabla} m
                JOIN rama_olap.dim_contaminante dt ON m.contaminante_id = dt.contaminante_id
                JOIN rama_olap.dim_estacion de ON m.estacion_id = de.estacion_id
                WHERE {where}
                GROUP BY m.fecha_primer_dia_mes
                ORDER BY m.fecha_primer_dia_mes ASC
            """, params)

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
            cursor.execute("""
                SELECT MAX(d.fecha)::TEXT
                FROM rama_olap.agg_medicion_diaria d
                JOIN rama_olap.dim_contaminante dc ON d.contaminante_id = dc.contaminante_id
                WHERE dc.codigo = %s
            """, [contaminante])
            fecha = cursor.fetchone()[0]
            if not fecha:
                fecha = "1986-01-01"

        cursor.execute("""
            SELECT
                de.estacion_id,
                TRIM(de.codigo),
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
            WHERE dc.codigo = %s
              AND d.fecha = %s::DATE
            ORDER BY de.codigo
        """, [contaminante, fecha])

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
                    TRIM(de.codigo) AS codigo,
                    de.nombre_estacion,
                    da.nombre_alcaldia,
                    ROUND(AVG(d.valor_promedio)::NUMERIC, 2) as valor_promedio,
                    ROUND(AVG(d.indice_normalizado)::NUMERIC, 1) as indice_normalizado
                FROM rama_olap.agg_medicion_diaria d
                JOIN rama_olap.dim_contaminante dc ON d.contaminante_id = dc.contaminante_id
                JOIN rama_olap.dim_estacion de ON d.estacion_id = de.estacion_id
                JOIN rama_olap.dim_alcaldia da ON de.alcaldia_id = da.alcaldia_id
                WHERE dc.codigo = %s
                  AND d.fecha >= %s::DATE
                  AND d.fecha <= %s::DATE
                GROUP BY de.estacion_id, de.codigo, de.nombre_estacion, da.nombre_alcaldia
                HAVING AVG(d.indice_normalizado) IS NOT NULL
            )
            SELECT posicion, codigo, nombre_estacion, nombre_alcaldia, valor_promedio, indice_normalizado
            FROM ranking
            ORDER BY posicion ASC
            LIMIT %s
        """, [contaminante, fecha_inicio, fecha_fin, limit])

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
        filtros = ["d.fecha >= %s::DATE", "d.fecha <= %s::DATE"]
        params: list = [fecha_inicio, fecha_fin]

        if estacion:
            filtros.append("de.codigo = %s")
            params.append(estacion.upper())

        if alcaldia_id:
            filtros.append("de.alcaldia_id = %s")
            params.append(alcaldia_id)

        where_clause = " AND ".join(filtros)

        cursor.execute(f"""
            WITH ranking AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY AVG(d.indice_normalizado) DESC) as posicion,
                    TRIM(dc.codigo) AS codigo,
                    dc.nombre,
                    dcat.nombre_categoria,
                    ROUND(AVG(d.indice_normalizado)::NUMERIC, 1) as indice_promedio
                FROM rama_olap.agg_medicion_diaria d
                JOIN rama_olap.dim_contaminante dc ON d.contaminante_id = dc.contaminante_id
                JOIN rama_olap.dim_categoria_contaminante dcat ON dc.categoria_id = dcat.categoria_id
                JOIN rama_olap.dim_estacion de ON d.estacion_id = de.estacion_id
                WHERE {where_clause}
                GROUP BY dc.contaminante_id, dc.codigo, dc.nombre, dcat.nombre_categoria
                HAVING AVG(d.indice_normalizado) IS NOT NULL
            )
            SELECT posicion, codigo, nombre, nombre_categoria, indice_promedio
            FROM ranking
            ORDER BY posicion ASC
            LIMIT %s
        """, params + [limit])

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
                    TRIM(dc.codigo) as clave,
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
                    TRIM(de.codigo) as clave,
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
