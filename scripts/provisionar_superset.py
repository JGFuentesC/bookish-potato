"""Provisión programática de datasets, charts y dashboards en Apache Superset.

Se conecta a la API REST de Superset (admin/admin) y crea:
  - 4 dashboards OLAP sobre las vistas de finanzas_olap.
Es idempotente: borra y recrea los objetos con prefijo 'finanzas'.
"""
import json
import os
import subprocess
import sys

import requests

from _config import cargar_env

cargar_env()

BASE = os.environ.get("SUPERSET_URL", "http://localhost:8088")
USER = os.environ.get("SUPERSET_ADMIN_USER", "admin")
PASS = os.environ.get("SUPERSET_ADMIN_PASSWORD", "admin")

DS_EMPRESA = "vw_empresa"
DS_MEMBRESIA = "vw_membresia"
DS_DIARIO = "vw_diario"
DS_MENSUAL = "vw_mensual"
NOMBRES_DATASETS = [DS_EMPRESA, DS_MEMBRESIA, DS_DIARIO, DS_MENSUAL]

PREFIJO_CHART = ("OV ", "PF ", "VL ", "LQ ", "ES ")
SLUGS_DASHBOARD = ["finanzas-overview", "finanzas-performance", "finanzas-volatilidad", "finanzas-liquidez", "finanzas-estacionalidad"]


def conectar() -> requests.Session:
    s = requests.Session()
    r = s.post(f"{BASE}/api/v1/security/login",
               json={"username": USER, "password": PASS, "provider": "db", "refresh": True})
    r.raise_for_status()
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    csrf = s.get(f"{BASE}/api/v1/security/csrf_token/").json()["result"]
    s.headers["X-CSRFToken"] = csrf
    return s


def api(s: requests.Session, metodo: str, path: str, body: dict | None = None) -> dict:
    r = s.request(metodo, f"{BASE}{path}", json=body if body is not None else None)
    if r.status_code >= 400:
        raise RuntimeError(f"{metodo} {path} -> {r.status_code}: {r.text[:400]}")
    return r.json() if r.text else {}


def metrica(col: str, agg: str) -> dict:
    return {
        "expressionType": "SIMPLE",
        "column": {"column_name": col},
        "aggregate": agg,
        "label": f"{agg}({col})",
    }


def filtro(col: str, op: str, val) -> dict:
    return {"expressionType": "SIMPLE", "clause": "WHERE", "subject": col, "operator": op, "comparator": val}


def refrescar_datasets(s: requests.Session) -> dict[str, int]:
    mapa: dict[str, int] = {}
    res = api(s, "GET", "/api/v1/dataset/?q=(columns:!(id,table_name,database),page_size:100)").get("result", [])
    for d in res:
        if d.get("table_name") in NOMBRES_DATASETS:
            mapa[d["table_name"]] = d["id"]
    for nombre in NOMBRES_DATASETS:
        if nombre not in mapa:
            r = api(s, "POST", "/api/v1/dataset/",
                    {"database": 2, "schema": "finanzas_olap", "table_name": nombre})
            mapa[nombre] = r["id"]
            print(f"dataset {nombre} creado -> id {r['id']}", flush=True)
            continue
        try:
            api(s, "PUT", f"/api/v1/dataset/{mapa[nombre]}/refresh")
            print(f"dataset {nombre} refrescado", flush=True)
        except RuntimeError:
            try:
                api(s, "DELETE", f"/api/v1/dataset/{mapa[nombre]}")
            except RuntimeError:
                pass
            r = api(s, "POST", "/api/v1/dataset/",
                    {"database": 2, "schema": "finanzas_olap", "table_name": nombre})
            mapa[nombre] = r["id"]
            print(f"dataset {nombre} recreado -> id {r['id']}", flush=True)
    return mapa


def limpiar(s: requests.Session) -> None:
    for dash in api(s, "GET", "/api/v1/dashboard/?q=(columns:!(id,slug),page_size:100)").get("result", []):
        if dash.get("slug") in SLUGS_DASHBOARD:
            try:
                api(s, "DELETE", f"/api/v1/dashboard/{dash['id']}")
                print(f"dashboard '{dash['slug']}' eliminado", flush=True)
            except RuntimeError as e:
                print(f"no se pudo eliminar dashboard {dash['id']}: {e}", flush=True)
    charts = api(s, "GET", "/api/v1/chart/?q=(columns:!(id,slice_name),page_size:500)").get("result", [])
    for c in charts:
        if any(c.get("slice_name", "").startswith(p) for p in PREFIJO_CHART):
            try:
                api(s, "DELETE", f"/api/v1/chart/{c['id']}")
                print(f"chart '{c['slice_name']}' eliminado", flush=True)
            except RuntimeError as e:
                print(f"no se pudo eliminar chart {c['id']}: {e}", flush=True)


def crear_chart(s: requests.Session, nombre: str, ds: int, params: dict) -> int:
    body = {
        "datasource_id": ds,
        "datasource_type": "table",
        "slice_name": nombre,
        "viz_type": params["viz_type"],
        "params": json.dumps(params),
    }
    r = api(s, "POST", "/api/v1/chart/", body)
    return r["id"]


def validar_chart(s: requests.Session, ds: int, params: dict) -> bool:
    query = {
        "time_range": params.get("time_range", "No filter"),
        "metrics": params.get("metrics", [params["metric"]] if "metric" in params else []),
        "filters": [
            {"col": f["subject"], "op": f["operator"], "val": f["comparator"]}
            for f in params.get("adhoc_filters", [])
        ],
        "row_limit": 50,
    }
    tc = params.get("granularity_sqla")
    if tc:
        query["granularity"] = tc
        query["extras"] = {"time_grain_sqla": params.get("time_grain_sqla", "P1D")}
    body = {"datasource": {"type": "table", "id": ds}, "queries": [query]}
    r = s.post(f"{BASE}/api/v1/chart/data", json=body)
    if r.status_code != 200:
        return False
    res = r.json().get("result", [{}])[0]
    return res.get("status") == "success"


def crear_dashboard(s: requests.Session, titulo: str, slug: str, chart_ids: list[int]) -> int:
    body = {"dashboard_title": titulo, "slug": slug, "published": True, "owners": [1]}
    r = api(s, "POST", "/api/v1/dashboard/", body)
    return r["id"]


def construir_posicion(chart_ids: list[int], titulo: str) -> str:
    pos = {
        "DASHBOARD_VERSION_KEY": "v2",
        "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "children": [], "meta": {"text": titulo}},
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"], "meta": {}},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "meta": {}},
    }
    por_fila = 2
    for i, cid in enumerate(chart_ids):
        fila, col = divmod(i, por_fila)
        row_id = f"ROW-{fila}"
        key = f"CHART-{cid}"
        if row_id not in pos:
            pos[row_id] = {
                "type": "ROW", "id": row_id, "children": [],
                "meta": {"0": "ROOT_ID", "1": "GRID_ID", "background": "BACKGROUND_TRANSPARENT"},
            }
            pos["GRID_ID"]["children"].append(row_id)
        pos[row_id]["children"].append(key)
        w = 12 // por_fila
        pos[key] = {
            "type": "CHART", "id": key, "children": [],
            "meta": {"chartId": cid, "width": w, "height": 50,
                     "position": {"i": key, "x": w * col, "y": fila * 50, "w": w, "h": 50},
                     "sliceName": "", "parents": ["ROOT_ID", "GRID_ID", row_id]},
        }
    return json.dumps(pos)


def actualizar_posiciones(s: requests.Session, dash_id: int, titulo: str, chart_ids: list[int]) -> None:
    meta = json.dumps({"chart_configuration": {}, "timed_refresh_immune_slices": [],
                       "expanded_slices": {}, "refresh_frequency": 0, "default_filters": "{}"})
    api(s, "PUT", f"/api/v1/dashboard/{dash_id}",
        {"position_json": construir_posicion(chart_ids, titulo), "json_metadata": meta})


# ---------------------------------------------------------------
# Definición de charts
# ---------------------------------------------------------------

def p_table(nombre, ds, cols, metricas, time_range, row_limit, time_col=None, filters=None, order=None):
    p = {"viz_type": "table", "datasource": f"{ds}__table", "time_range": time_range,
         "granularity_sqla": time_col, "time_grain_sqla": "P1D",
         "columns": cols, "metrics": metricas,
         "groupby": [], "adhoc_filters": filters or [], "row_limit": row_limit,
         "order_by_cols": order or [], "show_cell_bars": True, "page_length": row_limit,
         "server_pagination": False, "percent_metrics": []}
    return p


def p_line(nombre, ds, metricas, time_col, time_range, grain, filters=None, groupby=None):
    return {"viz_type": "line", "datasource": f"{ds}__table", "granularity_sqla": time_col,
            "time_grain_sqla": grain, "time_range": time_range, "metrics": metricas,
            "groupby": groupby or [], "adhoc_filters": filters or [], "show_legend": True,
            "line_interpolation": "linear", "color_scheme": "supersetColors",
            "rolling_type": "None", "time_compare": []}


def p_bar(nombre, ds, metrica_u, time_col, time_range, grain, groupby, filters=None):
    return {"viz_type": "dist_bar", "datasource": f"{ds}__table", "granularity_sqla": time_col,
            "time_grain_sqla": grain, "time_range": time_range, "metrics": [metrica_u],
            "groupby": groupby, "columns": [], "adhoc_filters": filters or [],
            "show_legend": True, "show_bar_value": False, "sort_by_metric": True,
            "y_axis_format": "SMART_NUMBER"}


def p_pie(nombre, ds, metrica_u, groupby, time_col, time_range, filters=None):
    return {"viz_type": "pie", "datasource": f"{ds}__table", "granularity_sqla": time_col,
            "time_range": time_range, "metric": metrica_u, "groupby": groupby,
            "adhoc_filters": filters or [], "show_legend": True, "show_labels": True,
            "label_type": "key", "number_format": "SMART_NUMBER", "outerRadius": 70}


def p_bignum(nombre, ds, metrica_u, time_col, time_range, filtros=None, subheader="", trendline=False):
    p = {"viz_type": "big_number_total", "datasource": f"{ds}__table",
         "granularity_sqla": time_col, "time_grain_sqla": "P1D", "time_range": time_range,
         "metric": metrica_u, "adhoc_filters": filtros or [], "subheader": subheader,
         "y_axis_format": "SMART_NUMBER"}
    if trendline:
        p["viz_type"] = "big_number"
        p["compare_lag"] = "30"
        p["compare_suffix"] = "d"
    return p


def p_heatmap(nombre, ds, x, y, metrica_u, time_range, filters=None):
    return {"viz_type": "heatmap", "datasource": f"{ds}__table", "all_columns_x": x,
            "all_columns_y": y, "metric": metrica_u, "adhoc_filters": filters or [],
            "time_range": time_range, "linear_color_scheme": "fire",
            "xscale_interval": "1", "yscale_interval": "1",
            "normalize_across": "heatmap", "canvas_image_rendering": "pixelated"}


SIN_SECTOR = filtro("sector_nombre", "!=", "Sin clasificar")
PENNY = filtro("close_ultimo", ">", 1)
SP500 = filtro("es_sp500", "==", True)


def definir_charts() -> list[dict]:
    c = []
    # ---- Dashboard 1: Market Overview
    c.append(dict(dash=1, name="OV Tickers cubiertos", ds=DS_EMPRESA,
                  params=p_bignum("", DS_EMPRESA, metrica("empresa_id", "COUNT_DISTINCT"), None, "No filter",
                                  subheader="Empresas únicas en el modelo OLAP")))
    c.append(dict(dash=1, name="OV $ volumen 30d", ds=DS_DIARIO,
                  params=p_bignum("", DS_DIARIO, metrica("volumen_dolares", "SUM"), "fecha", "Last 30 days",
                                  trendline=True, subheader="Últimos 30 días")))
    c.append(dict(dash=1, name="OV Índice S&P500 (retorno diario)", ds=DS_DIARIO,
                  params=p_line("", DS_DIARIO, [metrica("retorno_diario", "AVG")], "fecha", "Last year", "P1D",
                                filters=[SP500, SIN_SECTOR])))
    c.append(dict(dash=1, name="OV Tickers por lista", ds=DS_MEMBRESIA,
                  params=p_pie("", DS_MEMBRESIA, metrica("empresa_id", "COUNT_DISTINCT"),
                               ["lista_nombre"], None, "No filter")))
    c.append(dict(dash=1, name="OV Tickers por sector", ds=DS_EMPRESA,
                  params=p_pie("", DS_EMPRESA, metrica("empresa_id", "COUNT_DISTINCT"),
                               ["sector_nombre"], None, "No filter", filters=[SIN_SECTOR])))

    # ---- Dashboard 2: Performance
    c.append(dict(dash=2, name="PF Top ganadores (mes)", ds=DS_MENSUAL,
                  params=p_table("", DS_MENSUAL, ["simbolo", "sector_nombre"], [metrica("retorno_mensual", "AVG")],
                                 "Last month", 10, time_col="fecha_mes", filters=[PENNY, SIN_SECTOR],
                                 order=[["AVG(retorno_mensual)", False]])))
    c.append(dict(dash=2, name="PF Top perdedores (mes)", ds=DS_MENSUAL,
                  params=p_table("", DS_MENSUAL, ["simbolo", "sector_nombre"], [metrica("retorno_mensual", "AVG")],
                                 "Last month", 10, time_col="fecha_mes",
                                 filters=[PENNY, SIN_SECTOR, filtro("retorno_mensual", "<", 0)],
                                 order=[["AVG(retorno_mensual)", False]])))
    c.append(dict(dash=2, name="PF Retorno por sector (mes)", ds=DS_MENSUAL,
                  params=p_bar("", DS_MENSUAL, metrica("retorno_mensual", "AVG"), "fecha_mes",
                               "Last month", "P1M", ["sector_nombre"], filters=[PENNY, SIN_SECTOR])))
    c.append(dict(dash=2, name="PF Heatmap retorno sector x mes", ds=DS_MENSUAL,
                  params=p_heatmap("", DS_MENSUAL, "mes_nombre", "sector_nombre",
                                   metrica("retorno_mensual", "AVG"), "No filter", filters=[SIN_SECTOR])))

    # ---- Dashboard 3: Volatilidad
    c.append(dict(dash=3, name="VL Top volatilidad (mes)", ds=DS_MENSUAL,
                  params=p_table("", DS_MENSUAL, ["simbolo", "sector_nombre"],
                                 [metrica("volatilidad_mensual", "AVG")],
                                 "Last month", 20, time_col="fecha_mes", filters=[PENNY, SIN_SECTOR],
                                 order=[["AVG(volatilidad_mensual)", False]])))
    c.append(dict(dash=3, name="VL Volatilidad de mercado", ds=DS_MENSUAL,
                  params=p_line("", DS_MENSUAL, [metrica("volatilidad_mensual", "AVG")], "fecha_mes",
                                "Last 5 years", "P1M", filters=[SIN_SECTOR])))
    c.append(dict(dash=3, name="VL Rango medio diario (30d)", ds=DS_DIARIO,
                  params=p_bignum("", DS_DIARIO, metrica("rango", "AVG"), "fecha", "Last 30 days",
                                  subheader="Amplitud intradía promedio (USD)")))
    c.append(dict(dash=3, name="VL Rango medio diario en el tiempo", ds=DS_DIARIO,
                  params=p_line("", DS_DIARIO, [metrica("rango", "AVG")], "fecha",
                                "Last 6 months", "P1D", filters=[SIN_SECTOR])))

    # ---- Dashboard 4: Liquidez
    c.append(dict(dash=4, name="LQ Top $ volumen (30d)", ds=DS_DIARIO,
                  params=p_table("", DS_DIARIO, ["simbolo", "nombre"], [metrica("volumen_dolares", "SUM")],
                                 "Last 30 days", 20, time_col="fecha",
                                 order=[["SUM(volumen_dolares)", False]])))
    c.append(dict(dash=4, name="LQ Top volumen (30d)", ds=DS_DIARIO,
                  params=p_table("", DS_DIARIO, ["simbolo", "nombre"], [metrica("volumen", "SUM")],
                                 "Last 30 days", 20, time_col="fecha",
                                 order=[["SUM(volumen)", False]])))
    c.append(dict(dash=4, name="LQ $ volumen por sector (30d)", ds=DS_DIARIO,
                  params=p_bar("", DS_DIARIO, metrica("volumen_dolares", "SUM"), "fecha",
                               "Last 30 days", "P1D", ["sector_nombre"], filters=[SIN_SECTOR])))
    c.append(dict(dash=4, name="LQ $ volumen diario total (1a)", ds=DS_DIARIO,
                  params=p_line("", DS_DIARIO, [metrica("volumen_dolares", "SUM")], "fecha",
                                "Last year", "P1D")))

    # ---- Dashboard 5: Estacionalidad
    c.append(dict(dash=5, name="ES Retorno por mes del año", ds=DS_MENSUAL,
                  params=p_bar("", DS_MENSUAL, metrica("retorno_mensual", "AVG"), "fecha_mes",
                               "No filter", "P1M", ["mes_nombre"], filters=[PENNY, SIN_SECTOR])))
    c.append(dict(dash=5, name="ES Retorno mensual en el tiempo", ds=DS_MENSUAL,
                  params=p_line("", DS_MENSUAL, [metrica("retorno_mensual", "AVG")], "fecha_mes",
                                "Last 5 years", "P1M", filters=[SIN_SECTOR])))
    c.append(dict(dash=5, name="ES Retorno por día de semana", ds=DS_DIARIO,
                  params=p_bar("", DS_DIARIO, metrica("retorno_diario", "AVG"), "fecha",
                               "Last year", "P1D", ["dia_semana_nombre"], filters=[SIN_SECTOR])))
    c.append(dict(dash=5, name="ES $ volumen por año", ds=DS_MENSUAL,
                  params=p_bar("", DS_MENSUAL, metrica("volumen_total", "SUM"), "fecha_mes",
                               "Last 5 years", "P1Y", ["anio_id"])))
    return c


DASHBOARDS = {
    1: ("Market Overview", "finanzas-overview"),
    2: ("Performance", "finanzas-performance"),
    3: ("Volatilidad", "finanzas-volatilidad"),
    4: ("Liquidez", "finanzas-liquidez"),
    5: ("Estacionalidad", "finanzas-estacionalidad"),
}


def asociar_charts_en_superset() -> None:
    """Asocia los charts a sus dashboards vía el modelo interno de Superset."""
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run(
        ["docker", "cp", os.path.join(raiz, "docker/superset/init/asociar_charts.py"),
         "finanzas-superset:/tmp/asociar_charts.py"],
        check=True,
    )
    subprocess.run(
        ["docker", "compose", "exec", "superset", "python", "/tmp/asociar_charts.py"],
        check=True,
    )


def main() -> None:
    s = conectar()
    mapa = refrescar_datasets(s)
    limpiar(s)

    charts_creados: dict[int, list[int]] = {d: [] for d in DASHBOARDS}
    errores = 0
    for c in definir_charts():
        c["params"]["datasource"] = f"{mapa[c['ds']]}__table"
        ok = validar_chart(s, mapa[c["ds"]], c["params"])
        if not ok:
            print(f"[ERROR] validación falló para '{c['name']}'", flush=True)
            errores += 1
        cid = crear_chart(s, c["name"], mapa[c["ds"]], c["params"])
        charts_creados[c["dash"]].append(cid)
        print(f"chart '{c['name']}' -> id {cid} (validación {'OK' if ok else 'FALLO'})", flush=True)

    for dash, (titulo, slug) in DASHBOARDS.items():
        ids = charts_creados[dash]
        if not ids:
            continue
        did = crear_dashboard(s, titulo, slug, ids)
        actualizar_posiciones(s, did, titulo, ids)
        print(f"dashboard '{titulo}' -> id {did} ({len(ids)} charts)", flush=True)

    asociar_charts_en_superset()

    print(f"fin. errores de validación: {errores}", flush=True)
    if errores:
        sys.exit(1)


if __name__ == "__main__":
    main()
