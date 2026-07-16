"""
Auditoria de calidad de datos RAMA.

Genera cartas de control (estilo bell curve McKenzie) con bandas 2-sigma y 3-sigma,
analisis de tendencia, cuartiles, y pruebas de hipotesis para cada contaminante.
Output: SPA HTML navegable con Plotly.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import polars as pl
import scipy.stats as st
from pydantic import BaseModel, Field, computed_field

# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

PARQUET = Path("data/curated/rama_historica.parquet")
OUTPUT = Path("data/audit/calidad_rama.html")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

CONTAMINANTES: list[str] = ["CO", "NO", "NO2", "NOX", "O3", "PM10", "PM25", "PMCO", "SO2"]

# ---------------------------------------------------------------------------
# modelos
# ---------------------------------------------------------------------------


class PruebaHipotesis(BaseModel):
    nombre: str
    estadistico: float
    p_valor: float
    conclusion: str
    interpretacion: str


class ResultadoContaminante(BaseModel):
    contaminante: str
    n_dias: int
    n_estaciones: int
    media: float
    std: float | None
    q1: float
    q2: float
    q3: float
    min_val: float
    max_val: float
    tendencia_pendiente: float | None
    tendencia_p_valor: float | None
    pruebas: list[PruebaHipotesis]
    fechas: list[str] = Field(default_factory=list)
    valores_diarios: list[float | None] = Field(default_factory=list)
    # Para el grafico de control
    media_linea: list[float] = Field(default_factory=list)
    sigma2_sup: list[float] = Field(default_factory=list)
    sigma2_inf: list[float] = Field(default_factory=list)
    sigma3_sup: list[float] = Field(default_factory=list)
    sigma3_inf: list[float] = Field(default_factory=list)
    # Para boxplots mensuales
    meses_labels: list[str] = Field(default_factory=list)
    meses_boxes: list[dict[str, Any]] = Field(default_factory=list)
    # Para histograma bell curve
    hist_x: list[float] = Field(default_factory=list)
    hist_y: list[float] = Field(default_factory=list)
    bell_x: list[float] = Field(default_factory=list)
    bell_y: list[float] = Field(default_factory=list)

    @computed_field
    @property
    def cv(self) -> float | None:
        """Coeficiente de variacion."""
        if self.media and self.std and self.media != 0:
            return self.std / self.media
        return None

    @computed_field
    @property
    def pct_fuera_2sigma(self) -> float:
        arr = np.array(self.valores_diarios, dtype=np.float64)
        valid = arr[~np.isnan(arr)]
        if len(valid) == 0 or self.std is None or self.std == 0:
            return 0.0
        upper = self.media + 2 * self.std
        lower = self.media - 2 * self.std
        return float(np.sum((valid > upper) | (valid < lower)) / len(valid) * 100)

    @computed_field
    @property
    def pct_fuera_3sigma(self) -> float:
        arr = np.array(self.valores_diarios, dtype=np.float64)
        valid = arr[~np.isnan(arr)]
        if len(valid) == 0 or self.std is None or self.std == 0:
            return 0.0
        upper = self.media + 3 * self.std
        lower = self.media - 3 * self.std
        return float(np.sum((valid > upper) | (valid < lower)) / len(valid) * 100)


class AuditoriaReporte(BaseModel):
    titulo: str = "Auditoria de Calidad — Datos Historicos RAMA"
    fecha_generacion: str = Field(default_factory=lambda: date.today().isoformat())
    contaminantes: list[ResultadoContaminante]


# ---------------------------------------------------------------------------
# analisis
# ---------------------------------------------------------------------------


def shapiro_test(valores: np.ndarray) -> PruebaHipotesis:
    """Shapiro-Wilk: normalidad. Usa muestra aleatoria si n > 5000."""
    v = valores[~np.isnan(valores)]
    if len(v) < 3:
        return PruebaHipotesis(
            nombre="Shapiro-Wilk (normalidad)",
            estadistico=float("nan"),
            p_valor=float("nan"),
            conclusion="datos insuficientes",
            interpretacion="Se requieren al menos 3 observaciones.",
        )
    if len(v) > 5000:
        rng = np.random.default_rng(42)
        v = rng.choice(v, size=5000, replace=False)
    stat, p = st.shapiro(v)
    normal = p > 0.05
    return PruebaHipotesis(
        nombre="Shapiro-Wilk (normalidad)",
        estadistico=float(stat),
        p_valor=float(p),
        conclusion="normal" if normal else "no normal",
        interpretacion=(
            "Los datos siguen una distribucion normal (p > 0.05)."
            if normal
            else "Los datos NO siguen una distribucion normal (p <= 0.05). "
            "Esto es esperable en datos ambientales; las cartas de control "
            "siguen siendo utiles como referencia."
        ),
    )


def mann_kendall_test(valores: np.ndarray) -> PruebaHipotesis:
    """Mann-Kendall: tendencia monotona."""
    v = valores[~np.isnan(valores)]
    if len(v) < 4:
        return PruebaHipotesis(
            nombre="Mann-Kendall (tendencia)",
            estadistico=float("nan"),
            p_valor=float("nan"),
            conclusion="datos insuficientes",
            interpretacion="Se requieren al menos 4 observaciones.",
        )
    # Kendall tau
    tau, p = st.kendalltau(np.arange(len(v)), v)
    # Theil-Sen slope
    slope, intercept, lo, hi = st.mstats.theilslopes(v, np.arange(len(v)))
    tendencia = "creciente" if slope > 0 else "decreciente"
    sig = "significativa" if p < 0.05 else "no significativa"
    return PruebaHipotesis(
        nombre="Mann-Kendall (tendencia)",
        estadistico=float(slope),
        p_valor=float(p),
        conclusion=f"{tendencia} ({sig})",
        interpretacion=(
            f"Tendencia {tendencia} {sig} (tau={tau:.4f}, p={p:.4f}). "
            f"Pendiente Theil-Sen: {slope:.4f} unidades/dia."
        ),
    )


def anderson_darling_test(valores: np.ndarray) -> PruebaHipotesis:
    """Anderson-Darling: normalidad."""
    v = valores[~np.isnan(valores)]
    if len(v) < 3:
        return PruebaHipotesis(
            nombre="Anderson-Darling (normalidad)",
            estadistico=float("nan"),
            p_valor=float("nan"),
            conclusion="datos insuficientes",
            interpretacion="Se requieren al menos 3 observaciones.",
        )
    if len(v) > 5000:
        rng = np.random.default_rng(42)
        v = rng.choice(v, size=5000, replace=False)
    result = st.anderson(v, dist="norm", method="interpolate")
    stat = float(result.statistic)
    p = float(result.pvalue)
    normal = p > 0.05
    return PruebaHipotesis(
        nombre="Anderson-Darling (normalidad)",
        estadistico=stat,
        p_valor=p,
        conclusion="normal" if normal else "no normal",
        interpretacion=(
            f"Estadistico A²={stat:.4f}, p={p:.4f}. "
            + ("Los datos pasan la prueba de normalidad." if normal else "Los datos NO pasan la prueba de normalidad.")
        ),
    )


def analizar_contaminante(df: pl.DataFrame, contaminante: str) -> ResultadoContaminante:
    """Ejecuta el analisis completo para un contaminante."""
    sub = df.filter(pl.col("contaminante") == contaminante)

    # Agregar a promedio diario (media de todas las estaciones)
    diario = (
        sub.filter(pl.col("valor").is_not_null())
        .group_by("FECHA")
        .agg(
            pl.col("valor").mean().alias("media_diaria"),
            pl.col("estacion").n_unique().alias("n_estaciones"),
        )
        .sort("FECHA")
    )

    valores = diario["media_diaria"].to_numpy()
    fechas_py = diario["FECHA"].to_list()
    fechas_str = [str(d) for d in fechas_py]
    n_estaciones = int(sub["estacion"].n_unique())

    # Estadisticos basicos
    media = float(np.nanmean(valores))
    std = float(np.nanstd(valores)) if not np.all(np.isnan(valores)) else None
    q1 = float(np.nanpercentile(valores, 25))
    q2 = float(np.nanpercentile(valores, 50))
    q3 = float(np.nanpercentile(valores, 75))
    min_val = float(np.nanmin(valores))
    max_val = float(np.nanmax(valores))

    # Tendencia: regresion lineal simple
    x_idx = np.arange(len(valores), dtype=np.float64)
    mask = ~np.isnan(valores)
    if mask.sum() >= 3 and std and std > 0:
        slope, intercept, r_value, p_value, _ = st.linregress(x_idx[mask], valores[mask])
        tendencia_pendiente = float(slope)
        tendencia_p_valor = float(p_value)
        # Lineas de control
        media_linea = [media] * len(valores)
        sigma2_sup = [media + 2 * std] * len(valores)
        sigma2_inf = [media - 2 * std] * len(valores)
        sigma3_sup = [media + 3 * std] * len(valores)
        sigma3_inf = [media - 3 * std] * len(valores)
        # Liena de tendencia para grafico
        tendencia_y = [intercept + slope * i for i in x_idx]
    else:
        tendencia_pendiente = None
        tendencia_p_valor = None
        media_linea = [media] * len(valores) if not np.isnan(media) else []
        sigma2_sup = [(media + 2 * std) if std else 0] * len(valores)
        sigma2_inf = [(media - 2 * std) if std else 0] * len(valores)
        sigma3_sup = [(media + 3 * std) if std else 0] * len(valores)
        sigma3_inf = [(media - 3 * std) if std else 0] * len(valores)
        tendencia_y = []

    # Pruebas de hipotesis
    pruebas = [
        shapiro_test(valores),
        anderson_darling_test(valores),
        mann_kendall_test(valores),
    ]

    # Boxplots mensuales
    if len(valores) >= 12:
        df_diario_pl = diario.with_columns(pl.col("FECHA").dt.month().alias("mes"))
        meses_data: dict[int, list[float]] = {}
        for row in df_diario_pl.iter_rows(named=True):
            m = row["mes"]
            v = row["media_diaria"]
            if v is not None and not np.isnan(v):
                meses_data.setdefault(m, []).append(v)

        meses_ordenados = sorted(meses_data.keys())
        meses_nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        meses_labels = [meses_nombres[m - 1] for m in meses_ordenados]
        meses_boxes = [
            {
                "label": meses_nombres[m - 1],
                "q1": float(np.percentile(meses_data[m], 25)),
                "median": float(np.percentile(meses_data[m], 50)),
                "q3": float(np.percentile(meses_data[m], 75)),
                "lowerfence": float(np.percentile(meses_data[m], 5)),
                "upperfence": float(np.percentile(meses_data[m], 95)),
                "min": float(np.min(meses_data[m])),
                "max": float(np.max(meses_data[m])),
            }
            for m in meses_ordenados
        ]
    else:
        meses_labels = []
        meses_boxes = []

    # Histograma + bell curve
    v_clean = valores[~np.isnan(valores)]
    if len(v_clean) >= 3 and std and std > 0:
        hist, bins = np.histogram(v_clean, bins=min(60, len(v_clean) // 10), density=True)
        hist_x = [(bins[i] + bins[i + 1]) / 2 for i in range(len(hist))]
        hist_y = hist.tolist()
        bell_x = np.linspace(media - 4 * std, media + 4 * std, 200)
        bell_y = st.norm.pdf(bell_x, media, std)
        bell_x = bell_x.tolist()
        bell_y = bell_y.tolist()
    else:
        hist_x, hist_y, bell_x, bell_y = [], [], [], []

    return ResultadoContaminante(
        contaminante=contaminante,
        n_dias=len(valores),
        n_estaciones=n_estaciones,
        media=media,
        std=std,
        q1=q1,
        q2=q2,
        q3=q3,
        min_val=min_val,
        max_val=max_val,
        tendencia_pendiente=tendencia_pendiente,
        tendencia_p_valor=tendencia_p_valor,
        pruebas=pruebas,
        fechas=fechas_str,
        valores_diarios=[float(v) if not np.isnan(v) else None for v in valores],
        media_linea=media_linea,
        sigma2_sup=sigma2_sup,
        sigma2_inf=sigma2_inf,
        sigma3_sup=sigma3_sup,
        sigma3_inf=sigma3_inf,
        meses_labels=meses_labels,
        meses_boxes=meses_boxes,
        hist_x=hist_x,
        hist_y=hist_y,
        bell_x=bell_x,
        bell_y=bell_y,
    )


# ---------------------------------------------------------------------------
# graficos plotly
# ---------------------------------------------------------------------------


def _trazas_control(r: ResultadoContaminante, fig: go.Figure) -> None:
    """Agrega las bandas de control 2-sigma y 3-sigma a la figura."""
    n = len(r.fechas)

    fig.add_trace(go.Scatter(
        x=r.fechas,
        y=r.sigma3_sup,
        mode="lines",
        line={"dash": "dot", "width": 1, "color": "rgba(255,0,0,0.5)"},
        name="+3\u03c3",
        showlegend=True,
        legendgroup="control",
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=r.fechas,
        y=r.sigma2_sup,
        mode="lines",
        line={"dash": "dash", "width": 1, "color": "rgba(255,165,0,0.6)"},
        name="+2\u03c3",
        showlegend=True,
        legendgroup="control",
        hoverinfo="skip",
        fill="tonexty",
        fillcolor="rgba(255,165,0,0.05)",
    ))
    fig.add_trace(go.Scatter(
        x=r.fechas,
        y=r.media_linea,
        mode="lines",
        line={"width": 1.5, "color": "rgba(0,0,0,0.5)"},
        name="media",
        showlegend=True,
        legendgroup="control",
        hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=r.fechas,
        y=r.sigma2_inf,
        mode="lines",
        line={"dash": "dash", "width": 1, "color": "rgba(255,165,0,0.6)"},
        name="-2\u03c3",
        showlegend=True,
        legendgroup="control",
        hoverinfo="skip",
        fill="tonexty",
        fillcolor="rgba(255,165,0,0.05)",
    ))
    fig.add_trace(go.Scatter(
        x=r.fechas,
        y=r.sigma3_inf,
        mode="lines",
        line={"dash": "dot", "width": 1, "color": "rgba(255,0,0,0.5)"},
        name="-3\u03c3",
        showlegend=True,
        legendgroup="control",
        hoverinfo="skip",
    ))


def grafico_serie_temporal(r: ResultadoContaminante) -> str:
    """Serie de tiempo con bandas de control, media y tendencia."""
    fig = go.Figure()

    _trazas_control(r, fig)

    # Datos reales
    fig.add_trace(go.Scatter(
        x=r.fechas,
        y=r.valores_diarios,
        mode="markers",
        marker={"size": 2, "color": "rgba(31,119,180,0.5)"},
        name="promedio diario",
        showlegend=True,
        legendgroup="datos",
    ))

    # Tendencia
    if r.tendencia_pendiente is not None and r.tendencia_p_valor is not None:
        x_idx = np.arange(len(r.fechas))
        intercept = r.media - r.tendencia_pendiente * (len(x_idx) / 2)
        tend_y = [intercept + r.tendencia_pendiente * i for i in x_idx]
        fig.add_trace(go.Scatter(
            x=r.fechas,
            y=tend_y,
            mode="lines",
            line={"width": 2, "color": "red"},
            name=f"tendencia (p={r.tendencia_p_valor:.2e})",
        ))

    fig.update_layout(
        title=f"{r.contaminante} — Serie temporal diaria con cartas de control",
        xaxis_title="Fecha",
        yaxis_title="Concentracion",
        hovermode="x unified",
        template="plotly_white",
        height=420,
        margin={"l": 60, "r": 20, "t": 50, "b": 40},
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs=False)


def grafico_bell_curve(r: ResultadoContaminante) -> str:
    """Histograma con curva normal teorica y bandas sigma (bell curve)."""
    fig = go.Figure()

    # Histograma
    if r.hist_x:
        fig.add_trace(go.Bar(
            x=r.hist_x,
            y=r.hist_y,
            name="Distribucion observada",
            marker={"color": "rgba(31,119,180,0.6)"},
            width=(r.hist_x[1] - r.hist_x[0]) * 0.9 if len(r.hist_x) > 1 else 1,
        ))

    # Curva normal
    if r.bell_x:
        fig.add_trace(go.Scatter(
            x=r.bell_x,
            y=r.bell_y,
            mode="lines",
            line={"width": 2, "color": "black"},
            name="Normal teorica",
        ))

    # Lineas sigma
    if r.std and r.std > 0:
        for s, color, label in [
            (1, "green", "+1\u03c3"),
            (2, "orange", "+2\u03c3"),
            (3, "red", "+3\u03c3"),
        ]:
            x_pos = r.media + s * r.std
            fig.add_vline(x=x_pos, line_width=1.5, line_dash="dash" if s < 3 else "dot",
                          line_color=color, annotation_text=label,
                          annotation_position="top right")
            x_neg = r.media - s * r.std
            fig.add_vline(x=x_neg, line_width=1.5, line_dash="dash" if s < 3 else "dot",
                          line_color=color)

    fig.update_layout(
        title=f"{r.contaminante} — Distribucion y campana de Gauss (bell curve)",
        xaxis_title="Concentracion",
        yaxis_title="Densidad",
        template="plotly_white",
        height=400,
        margin={"l": 60, "r": 20, "t": 50, "b": 40},
        showlegend=True,
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs=False)


def grafico_boxplot_mensual(r: ResultadoContaminante) -> str:
    """Boxplots mensuales para detectar estacionalidad."""
    fig = go.Figure()

    if r.meses_boxes:
        fig.add_trace(go.Box(
            name="",
            q1=[b["q1"] for b in r.meses_boxes],
            median=[b["median"] for b in r.meses_boxes],
            q3=[b["q3"] for b in r.meses_boxes],
            lowerfence=[b["lowerfence"] for b in r.meses_boxes],
            upperfence=[b["upperfence"] for b in r.meses_boxes],
            x=r.meses_labels,
            marker={"color": "rgba(31,119,180,0.7)"},
            showlegend=False,
        ))

    fig.update_layout(
        title=f"{r.contaminante} — Distribucion mensual (todos los anos)",
        xaxis_title="Mes",
        yaxis_title="Concentracion diaria promedio",
        template="plotly_white",
        height=360,
        margin={"l": 60, "r": 20, "t": 50, "b": 40},
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs=False)


def tarjeta_metricas(r: ResultadoContaminante) -> str:
    """HTML con tarjetas de metricas y pruebas de hipotesis."""
    pruebas_html = ""
    for p in r.pruebas:
        p_val_fmt = f"{p.p_valor:.4f}" if not np.isnan(p.p_valor) else "N/A"
        pruebas_html += f"""
        <div class="test-card">
            <div class="test-name">{p.nombre}</div>
            <div class="test-stats">
                <span>Estadistico: <strong>{p.estadistico:.4f}</strong></span>
                <span>p-valor: <strong>{p_val_fmt}</strong></span>
                <span class="conclusion {'ok' if 'normal' in p.conclusion.lower() or 'creciente' in p.conclusion.lower() or 'significativa' in p.conclusion.lower() else 'warn'}">{p.conclusion}</span>
            </div>
            <div class="test-interp">{p.interpretacion}</div>
        </div>"""

    std_str = f"{r.std:.4f}" if r.std else "N/A"
    cv_str = f"{r.cv:.2%}" if r.cv else "N/A"
    tend_str = f"{r.tendencia_pendiente:.2e}" if r.tendencia_pendiente else "N/A"

    return f"""
    <div class="metrics-grid">
        <div class="metric-card">
            <div class="metric-label">Media (&mu;)</div>
            <div class="metric-value">{r.media:.4f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Desv. Est. (&sigma;)</div>
            <div class="metric-value">{std_str}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">CV (&sigma;/&mu;)</div>
            <div class="metric-value">{cv_str}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Dias</div>
            <div class="metric-value">{r.n_dias:,}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Estaciones (max)</div>
            <div class="metric-value">{r.n_estaciones}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Q1 / Q2 / Q3</div>
            <div class="metric-value small">{r.q1:.2f} / {r.q2:.2f} / {r.q3:.2f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Min / Max</div>
            <div class="metric-value small">{r.min_val:.2f} / {r.max_val:.2f}</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Fuera ±2&sigma;</div>
            <div class="metric-value">{r.pct_fuera_2sigma:.1f}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Fuera ±3&sigma;</div>
            <div class="metric-value">{r.pct_fuera_3sigma:.1f}%</div>
        </div>
        <div class="metric-card">
            <div class="metric-label">Pendiente tendencia</div>
            <div class="metric-value">{tend_str}</div>
        </div>
    </div>
    <div class="tests-section">
        <h3>Pruebas de hipotesis</h3>
        {pruebas_html}
    </div>
    """


# ---------------------------------------------------------------------------
# SPA HTML
# ---------------------------------------------------------------------------


def generar_html(reporte: AuditoriaReporte) -> str:
    """Construye la SPA HTML completa con navegacion por pestanas."""
    # Generar graficos para cada contaminante
    paneles = ""
    tabs = ""
    for i, r in enumerate(reporte.contaminantes):
        active = "active" if i == 0 else ""
        tabs += f'<button class="tab-btn {active}" onclick="openTab(event, \'{r.contaminante}\')">{r.contaminante}</button>'

        serie = grafico_serie_temporal(r)
        bell = grafico_bell_curve(r)
        boxplot = grafico_boxplot_mensual(r)
        metricas = tarjeta_metricas(r)

        paneles += f"""
        <div id="{r.contaminante}" class="tab-content {active}">
            <h2>{r.contaminante}</h2>
            <div class="charts-row">
                <div class="chart-card">{serie}</div>
                <div class="chart-card">{bell}</div>
            </div>
            <div class="charts-row">
                <div class="chart-card">{boxplot}</div>
                <div class="chart-card">{metricas}</div>
            </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auditoria de Calidad — RAMA</title>
    <script src="https://cdn.plot.ly/plotly-3.1.0.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f6f8; color: #1a1a2e; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e, #16213e); color: white; padding: 24px 32px; }}
        .header h1 {{ font-size: 1.5rem; font-weight: 600; }}
        .header .subtitle {{ font-size: 0.85rem; opacity: 0.7; margin-top: 4px; }}
        .tab-bar {{ display: flex; flex-wrap: wrap; gap: 2px; background: #e8eaed; padding: 8px 8px 0 8px; border-bottom: 2px solid #d0d4da; position: sticky; top: 0; z-index: 10; }}
        .tab-btn {{ padding: 10px 18px; border: none; background: transparent; cursor: pointer; font-size: 0.85rem; font-weight: 500; color: #555; border-radius: 6px 6px 0 0; transition: all 0.15s; }}
        .tab-btn:hover {{ background: rgba(255,255,255,0.7); }}
        .tab-btn.active {{ background: white; color: #1a1a2e; font-weight: 600; }}
        .tab-content {{ display: none; padding: 24px; }}
        .tab-content.active {{ display: block; }}
        .tab-content h2 {{ font-size: 1.15rem; margin-bottom: 16px; color: #333; }}
        .charts-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }}
        @media (max-width: 1200px) {{ .charts-row {{ grid-template-columns: 1fr; }} }}
        .chart-card {{ background: white; border-radius: 10px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
        .metrics-grid {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 20px; }}
        @media (max-width: 800px) {{ .metrics-grid {{ grid-template-columns: repeat(3, 1fr); }} }}
        .metric-card {{ background: #f8f9fb; border-radius: 8px; padding: 14px; text-align: center; border: 1px solid #e8eaed; }}
        .metric-label {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px; color: #888; margin-bottom: 4px; }}
        .metric-value {{ font-size: 1.3rem; font-weight: 700; color: #1a1a2e; }}
        .metric-value.small {{ font-size: 0.95rem; }}
        .tests-section {{ background: white; border-radius: 10px; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
        .tests-section h3 {{ font-size: 0.95rem; margin-bottom: 14px; color: #555; }}
        .test-card {{ background: #f8f9fb; border-radius: 8px; padding: 14px; margin-bottom: 10px; border-left: 4px solid #4a90d9; }}
        .test-name {{ font-weight: 600; font-size: 0.9rem; margin-bottom: 6px; color: #333; }}
        .test-stats {{ display: flex; gap: 20px; font-size: 0.82rem; color: #666; margin-bottom: 6px; flex-wrap: wrap; }}
        .test-interp {{ font-size: 0.8rem; color: #888; line-height: 1.4; }}
        .conclusion.ok {{ color: #2e7d32; font-weight: 600; }}
        .conclusion.warn {{ color: #d84315; font-weight: 600; }}
        .footer {{ text-align: center; padding: 24px; font-size: 0.78rem; color: #999; border-top: 1px solid #e8eaed; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{reporte.titulo}</h1>
        <div class="subtitle">Red Automatica de Monitoreo Atmosferico — CDMX | Generado: {reporte.fecha_generacion} | Contaminantes: {len(reporte.contaminantes)} | Fuente: aire.cdmx.gob.mx</div>
    </div>
    <div class="tab-bar">{tabs}</div>
    <div class="main-content">{paneles}</div>
    <div class="footer">
        Cartas de control estilo bell curve (McKenzie) — Bandas ±2&sigma; y ±3&sigma; — Pruebas: Shapiro-Wilk, Anderson-Darling, Mann-Kendall — Generado con Plotly + Polars + SciPy
    </div>
    <script>
        function openTab(evt, contaminante) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(contaminante).classList.add('active');
            evt.currentTarget.classList.add('active');
        }}
    </script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    print("Cargando dataset curado...")
    df = pl.read_parquet(PARQUET)
    print(f"  {df.height:,} filas cargadas\n")

    resultados: list[ResultadoContaminante] = []
    for contaminante in CONTAMINANTES:
        print(f"Analizando {contaminante}...")
        try:
            r = analizar_contaminante(df, contaminante)
            resultados.append(r)
            s = f"{r.std:.4f}" if r.std else "N/A"
            print(f"  {r.n_dias:,} dias, {r.n_estaciones} estaciones, "
                  f"media={r.media:.4f}, std={s}")
        except Exception as e:
            print(f"  ERROR: {e}")

    reporte = AuditoriaReporte(contaminantes=resultados)

    print(f"\nGenerando HTML: {OUTPUT}...")
    html = generar_html(reporte)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"Listo. Tamano: {OUTPUT.stat().st_size / 1_048_576:.1f} MB")
    print(f"Abrir: file://{OUTPUT.resolve()}")


if __name__ == "__main__":
    main()
