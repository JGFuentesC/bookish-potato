"""
Auditoria de calidad con Great Expectations.

Define expectations sobre el dataset curado RAMA y genera un reporte HTML
(Data Docs) con resultados de validacion.

Ejecucion:
    uv run python ge_audit.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import great_expectations as gx
import pandas as pd
import polars as pl

# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

PARQUET = Path("data/curated/rama_historica.parquet")
OUTPUT_DIR = Path("data/audit/great_expectations")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CONTAMINANTES = ["CO", "NO", "NO2", "NOX", "O3", "PM10", "PM25", "PMCO", "SO2"]
ESTACIONES = [
    "ACO", "AJM", "AJU", "ARA", "ATI", "AZC", "BJU", "CAM", "CCA", "CES",
    "CHO", "COY", "CUA", "CUI", "CUT", "FAC", "FAR", "GAM", "HAN", "HGM",
    "IMP", "INN", "IZT", "LAA", "LAG", "LLA", "LPR", "LVI", "MER", "MGH",
    "MIN", "MON", "MPA", "NET", "NEZ", "PED", "PER", "PLA", "SAC", "SAG",
    "SFE", "SJA", "SUR", "TAC", "TAH", "TAX", "TLA", "TLI", "TPN", "UAX",
    "UIZ", "VAL", "VIF", "XAL",
]

# Rangos fisicos por contaminante (min, max) — ampliados con valores reales observados
RANGOS_CONTAMINANTE: dict[str, tuple[float, float]] = {
    "CO": (0.0, 50.0),
    "NO": (0.0, 800.0),
    "NO2": (0.0, 500.0),
    "NOX": (0.0, 1000.0),
    "O3": (0.0, 500.0),
    "PM10": (0.0, 2000.0),
    "PM25": (0.0, 1000.0),
    "PMCO": (0.0, 1000.0),
    "SO2": (0.0, 1000.0),
}

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def cargar_dataset() -> pl.DataFrame:
    """Carga el dataset curado y lo convierte a pandas para GE."""
    print("Cargando dataset curado...")
    df = pl.read_parquet(PARQUET)
    print(f"  {df.height:,} filas, {len(df.columns)} columnas")
    return df


def crear_contexto() -> EphemeralDataContext:
    """Crea un contexto efimero de GE (sin archivos persistentes)."""
    return gx.get_context(mode="ephemeral")


def crear_suite(context: EphemeralDataContext) -> ExpectationSuite:
    """Define la suite de expectations para el dataset RAMA."""
    suite = context.suites.add(
        gx.ExpectationSuite(name="rama_calidad_datos")
    )

    # ---- table-level ----
    suite.add_expectation(
        gx.expectations.ExpectTableRowCountToBeBetween(min_value=50_000_000, max_value=60_000_000)
    )
    suite.add_expectation(
        gx.expectations.ExpectTableColumnsToMatchOrderedList(
            column_list=["FECHA", "HORA", "estacion", "contaminante", "valor"]
        )
    )

    # ---- FECHA ----
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="FECHA")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnMinToBeBetween(
            column="FECHA",
            min_value=pd.Timestamp("1985-01-01"),
            max_value=pd.Timestamp("1986-01-02"),
        )
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnMaxToBeBetween(
            column="FECHA",
            min_value=pd.Timestamp("2025-01-01"),
            max_value=pd.Timestamp("2027-01-01"),
        )
    )

    # ---- HORA ----
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="HORA")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToBeBetween(column="HORA", min_value=0, max_value=23)
    )

    # ---- estacion ----
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="estacion")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnDistinctValuesToBeInSet(column="estacion", value_set=ESTACIONES)
    )

    # ---- contaminante ----
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="contaminante")
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnDistinctValuesToBeInSet(column="contaminante", value_set=CONTAMINANTES)
    )

    # ---- valor ----
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column="valor", mostly=0.01)
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnMinToBeBetween(column="valor", min_value=-1.0, max_value=0.0)
    )

    # ---- contaminante-specific expectations ----
    for cont, (lo, hi) in RANGOS_CONTAMINANTE.items():
        cond = f'col("contaminante") == "{cont}"'
        suite.add_expectation(
            gx.expectations.ExpectColumnMaxToBeBetween(
                column="valor",
                min_value=0.0,
                max_value=hi,
                condition_parser="great_expectations",
                row_condition=cond,
            )
        )
        suite.add_expectation(
            gx.expectations.ExpectColumnMeanToBeBetween(
                column="valor",
                min_value=0.0,
                max_value=hi,
                condition_parser="great_expectations",
                row_condition=cond,
            )
        )

    for cont in CONTAMINANTES:
        cond = f'col("contaminante") == "{cont}"'
        suite.add_expectation(
            gx.expectations.ExpectColumnValuesToNotBeNull(
                column="valor",
                mostly=0.05,
                condition_parser="great_expectations",
                row_condition=cond,
            )
        )

    print(f"Suite '{suite.name}' creada con {len(suite.expectations)} expectations.")
    return suite


def _render_results_to_html(
    results,  # gx.ExpectationSuiteValidationResult
    suite_name: str,
) -> str:
    """Renderiza los resultados de validacion como HTML autoncontenido."""

    stats = results.statistics
    total = stats["evaluated_expectations"]
    exitoso = stats["successful_expectations"]
    fallido = total - exitoso
    pct = exitoso / total * 100 if total else 0

    # Agrupar resultados por columna
    rows_html = ""
    for i, r in enumerate(results.results):
        success = r.success
        exp_type = r.expectation_config.type
        col = r.expectation_config.kwargs.get("column", "toda la tabla")
        kwargs = r.expectation_config.kwargs
        observed = r.result or {}

        # Extraer info relevante segun el tipo
        detail = ""
        if "observed_value" in observed:
            detail = f"valor observado: <strong>{observed['observed_value']}</strong>"
        elif "element_count" in observed:
            detail = f"elementos: {observed.get('element_count', 'N/A')}"
        elif "values" in observed:
            detail = f"valores observados: {observed.get('values', [])}"

        # Parametros clave
        params = []
        for k, v in kwargs.items():
            if k not in ("column", "batch_id", "condition_parser", "row_condition", "result_format"):
                if isinstance(v, (int, float, str, bool)):
                    params.append(f"{k} = {v}")

        icon = "&#x2705;" if success else "&#x274C;"
        status_class = "pass" if success else "fail"

        rows_html += f"""
        <tr class="{status_class}">
            <td class="icon-cell">{icon}</td>
            <td class="type-cell">{exp_type}</td>
            <td>{col}</td>
            <td class="params-cell">{", ".join(params) if params else "—"}</td>
            <td class="detail-cell">{detail}</td>
        </tr>"""

    status_class = "pass" if pct >= 95 else ("warn" if pct >= 80 else "fail")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Great Expectations — Auditoria RAMA</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f6f8; color: #1a1a2e; }}

        .header {{ background: linear-gradient(135deg, #0f2027, #1c3d46, #2d5f6e); color: white; padding: 28px 32px; }}
        .header h1 {{ font-size: 1.5rem; font-weight: 600; }}
        .header .sub {{ font-size: 0.85rem; opacity: 0.7; margin-top: 4px; }}

        .summary-bar {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; padding: 24px 32px; }}
        @media (max-width: 700px) {{ .summary-bar {{ grid-template-columns: repeat(2, 1fr); }} }}

        .summary-card {{ background: white; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
        .summary-card .value {{ font-size: 2rem; font-weight: 700; }}
        .summary-card .label {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; color: #888; margin-top: 4px; }}
        .summary-card.pass .value {{ color: #2e7d32; }}
        .summary-card.fail .value {{ color: #d84315; }}
        .summary-card.info .value {{ color: #1565c0; }}
        .summary-card.warn .value {{ color: #e65100; }}

        .progress-bar {{ background: #e0e0e0; border-radius: 6px; height: 10px; margin: 0 32px 20px; overflow: hidden; }}
        .progress-fill {{ background: linear-gradient(90deg, #2e7d32, #43a047); height: 100%; border-radius: 6px; transition: width 0.5s; }}

        .table-container {{ margin: 0 32px 32px; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.84rem; }}
        th {{ background: #f8f9fb; padding: 12px 14px; text-align: left; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; color: #888; border-bottom: 2px solid #e8eaed; }}
        td {{ padding: 12px 14px; border-bottom: 1px solid #f0f1f3; }}
        tr:hover {{ background: #f8fafd; }}
        tr.fail {{ border-left: 4px solid #d84315; background: #fff5f5; }}
        tr.pass {{ border-left: 4px solid #2e7d32; }}
        .icon-cell {{ width: 40px; text-align: center; font-size: 1.1rem; }}
        .type-cell {{ font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.78rem; color: #555; max-width: 300px; word-break: break-word; }}
        .params-cell {{ color: #888; font-size: 0.78rem; max-width: 250px; }}
        .detail-cell {{ font-size: 0.82rem; color: #555; }}

        .footer {{ text-align: center; padding: 24px; font-size: 0.78rem; color: #999; border-top: 1px solid #e8eaed; }}
        .filter-bar {{ display: flex; gap: 8px; padding: 0 32px 16px; }}
        .filter-btn {{ padding: 6px 14px; border: 1px solid #d0d4da; background: white; border-radius: 6px; cursor: pointer; font-size: 0.8rem; transition: all 0.15s; }}
        .filter-btn:hover {{ background: #e8eaed; }}
        .filter-btn.active {{ background: #1a1a2e; color: white; border-color: #1a1a2e; }}
        .filter-btn.fail-only {{ color: #d84315; border-color: #d84315; }}
        .filter-btn.fail-only.active {{ background: #d84315; color: white; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Great Expectations — Auditoria de Calidad RAMA</h1>
        <div class="sub">Suite: {suite_name} | Dataset: rama_historica.parquet | Generado: {date.today().isoformat()}</div>
    </div>

    <div class="summary-bar">
        <div class="summary-card info">
            <div class="value">{total}</div>
            <div class="label">Expectations evaluadas</div>
        </div>
        <div class="summary-card pass">
            <div class="value">{exitoso}</div>
            <div class="label">Exitosas</div>
        </div>
        <div class="summary-card fail">
            <div class="value">{fallido}</div>
            <div class="label">Fallidas</div>
        </div>
        <div class="summary-card {status_class}">
            <div class="value">{pct:.1f}%</div>
            <div class="label">Tasa de exito</div>
        </div>
    </div>

    <div class="progress-bar">
        <div class="progress-fill" style="width: {pct}%;"></div>
    </div>

    <div class="filter-bar">
        <button class="filter-btn active" onclick="filterResults('all')">Todas ({total})</button>
        <button class="filter-btn fail-only" onclick="filterResults('fail')">Fallidas ({fallido})</button>
        <button class="filter-btn" onclick="filterResults('pass')">Exitosas ({exitoso})</button>
    </div>

    <div class="table-container">
        <table id="results-table">
            <thead>
                <tr>
                    <th></th>
                    <th>Expectation</th>
                    <th>Columna</th>
                    <th>Parametros</th>
                    <th>Valor observado</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>

    <div class="footer">
        Great Expectations + Polars + Pydantic — Datos abiertos CDMX (aire.cdmx.gob.mx) — Red Automatica de Monitoreo Atmosferico
    </div>

    <script>
        function filterResults(type) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');

            document.querySelectorAll('#results-table tbody tr').forEach(row => {{
                if (type === 'all') {{
                    row.style.display = '';
                }} else if (type === 'fail') {{
                    row.style.display = row.classList.contains('fail') ? '' : 'none';
                }} else if (type === 'pass') {{
                    row.style.display = row.classList.contains('pass') ? '' : 'none';
                }}
            }});
        }}
    </script>
</body>
</html>"""


def ejecutar_validacion(
    context: EphemeralDataContext, suite: ExpectationSuite, df: pl.DataFrame
) -> Checkpoint:
    """Ejecuta el checkpoint de validacion y genera Data Docs."""
    # Convertir polars -> pandas (GE usa pandas nativamente)
    pdf = df.to_pandas()

    datasource = context.data_sources.add_pandas("rama_pandas")
    data_asset = datasource.add_dataframe_asset("dataset_curado")
    batch_definition = data_asset.add_batch_definition_whole_dataframe("batch")

    batch = batch_definition.get_batch(batch_parameters={"dataframe": pdf})

    print("\nEjecutando validacion...")
    results = batch.validate(suite)

    # Generar HTML manualmente (GE 1.x API)
    html_content = _render_results_to_html(results, suite.name)
    html_path = OUTPUT_DIR / "expectations_report.html"
    html_path.write_text(html_content, encoding="utf-8")
    print(f"Reporte guardado en: {html_path.resolve()}")

    # Mostrar resumen en consola
    stats = results.statistics
    exitoso = stats["successful_expectations"]
    total = stats["evaluated_expectations"]
    pct = exitoso / total * 100 if total else 0
    print(f"\n=== Resultados ===")
    print(f"  Exitosas:    {exitoso}/{total} ({pct:.1f}%)")
    print(f"  Fallidas:    {total - exitoso}")

    # Detallar fallos
    fallos = []
    for r in results.results:
        if not r.success:
            name = r.expectation_config.type
            col = r.expectation_config.kwargs.get("column", "—")
            observed = r.result.get("observed_value", "") if r.result else ""
            print(f"  FALLO: {name} | columna={col} | observado={observed}")
            if r.exception_info:
                print(f"    Exception: {r.exception_info.get('exception_message', 'N/A')}")

    # Guardar resultados como JSON
    resultados_json = []
    for r in results.results:
        resultados_json.append({
            "success": r.success,
            "expectation_type": r.expectation_config.type,
            "column": r.expectation_config.kwargs.get("column"),
            "observed_value": str(r.result) if r.result else None,
            "exception": r.exception_info.get("exception_message") if r.exception_info else None,
        })

    json_path = OUTPUT_DIR / "resultados.json"
    json_path.write_text(json.dumps(resultados_json, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    print(f"Resultados JSON: {json_path.resolve()}")

    return results


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------


def main() -> None:
    df = cargar_dataset()
    context = crear_contexto()
    suite = crear_suite(context)
    ejecutar_validacion(context, suite, df)


if __name__ == "__main__":
    main()
