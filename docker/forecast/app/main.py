"""Forecast API — FastAPI.

Sirve el front estático (vanilla JS) en la raíz y expone la API bajo
``/api/v1``.

Almacenamiento (``DATA_MODE``):
    - ``mysql`` (dev): lee de ``finanzas_olap`` vía MySQL (usuario ``dashboards``,
      solo SELECT). Credenciales vía MYSQL_HOST / MYSQL_DASHBOARDS_USER /
      MYSQL_DASHBOARDS_PASSWORD.
    - ``sqlite`` (Cloud Run): lee de un snapshot SQLite estático embebido en la
      imagen (``STATIC_DB``), sin red ni credenciales.

Protección de la API (``API_TOKEN``):
    - Si la variable está definida, los endpoints ``/api/v1/*`` exigen el token
      como cabecera ``Authorization: Bearer <token>`` o query ``?token=<token>``.
      El front la recibe inyectada en el HTML servido (nunca en la imagen).
"""

from __future__ import annotations

import datetime as dt
import hmac
import html
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

try:  # imagen plana del contenedor: uvicorn main:app
    from modelos import FEATURE_COLUMNS, ModeloNoDisponible, modelos
    from storage import StorageError, crear_store
except ImportError:  # dev: paquete app/
    from .modelos import FEATURE_COLUMNS, ModeloNoDisponible, modelos
    from .storage import StorageError, crear_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("forecast-api")


# ----------------------------------------------------------------------
# Configuración
# ----------------------------------------------------------------------
def _cargar_env_local() -> None:
    """Dev: lee un .env del árbol del repo si existe (no sobrescribe exported)."""
    candidatos = [Path.cwd(), *Path(__file__).resolve().parents]
    for p in candidatos:
        ruta = p / ".env"
        if ruta.is_file():
            for linea in ruta.read_text(encoding="utf-8").splitlines():
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, _, v = linea.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


_cargar_env_local()

API_TOKEN = os.environ.get("API_TOKEN", "")

store = crear_store()


def _resolver_static() -> Path | None:
    env = os.environ.get("STATIC_DIR")
    if env:
        return Path(env) if Path(env).is_dir() else None
    for cand in (Path("/app/static"), Path(__file__).resolve().parent.parent / "static"):
        if cand.is_dir():
            return cand
    return None


# ----------------------------------------------------------------------
# Helpers de valores
# ----------------------------------------------------------------------
def _num(valor: object) -> float | None:
    if valor is None:
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _fecha_iso(valor: object) -> str:
    if isinstance(valor, (dt.date, dt.datetime)):
        return valor.isoformat()
    return str(valor)


# ----------------------------------------------------------------------
# App + CORS + estáticos
# ----------------------------------------------------------------------
app = FastAPI(title="Forecast API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    # Solo la UI servida por esta misma API (same-origin). Sin credenciales,
    # sin wildcard: no habilitamos CORS para otros orígenes.
    allow_origins=[
        "http://127.0.0.1:8090",
        "http://localhost:8090",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _seguridad_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.middleware("http")
async def _proteger_api_token(request, call_next):
    """Los endpoints /api/v1 exigen API_TOKEN solo si está configurado.

    Dev (compose, sin token) queda abierto; Cloud Run siempre inyecta el token
    vía Secret Manager, así que en producción la protección está activa.
    """
    if request.url.path.startswith("/api/") and API_TOKEN:
        cabecera = request.headers.get("Authorization", "")
        dado = cabecera[7:] if cabecera.startswith("Bearer ") else request.query_params.get("token", "")
        if not dado or not hmac.compare_digest(dado, API_TOKEN):
            return JSONResponse({"detalle": "no autorizado"}, status_code=401)
    return await call_next(request)


# ----------------------------------------------------------------------
# GET / (static) — se monta AL FINAL para no sombrear /api/v1/*
# ----------------------------------------------------------------------
STATIC_DIR = _resolver_static()


def _montar_static() -> None:
    if STATIC_DIR is None:
        return

    @app.get("/")
    def raiz() -> HTMLResponse:
        try:
            html_base = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
        except OSError:
            raise HTTPException(404, "frontend estático no disponible")
        html_base = html_base.replace("__API_TOKEN_VAL__", html.escape(API_TOKEN))
        return HTMLResponse(html_base)

    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


# ----------------------------------------------------------------------
# GET /api/v1/health
# ----------------------------------------------------------------------
@app.get("/api/v1/health")
def health() -> dict:
    info = modelos.info()
    return {"status": "ok", "modelo": info["id"] if info else None}


# ----------------------------------------------------------------------
# GET /api/v1/tickers
# ----------------------------------------------------------------------
@app.get("/api/v1/tickers")
def listar_tickers(
    q: str | None = Query(None),
    lista: str | None = Query(None),
    sector: str | None = Query(None),
) -> list[dict]:
    try:
        return store.tickers(q=q, lista=lista, sector=sector)
    except StorageError as exc:
        logger.error("tickers: %s", exc)
        raise HTTPException(503, "no se pudo leer el catálogo de tickers") from exc


# ----------------------------------------------------------------------
# GET /api/v1/ticker/{sim}/history
# ----------------------------------------------------------------------
@app.get("/api/v1/ticker/{sim}/history")
def historico(
    sim: str,
    desde: str | None = Query(None),
    hasta: str | None = Query(None),
) -> list[dict]:
    sim = sim.strip().upper()
    try:
        filas = store.history(sim, desde=desde, hasta=hasta)
    except StorageError as exc:
        logger.error("history %s: %s", sim, exc)
        raise HTTPException(503, "no se pudo consultar la historia") from exc
    if filas is None:
        raise HTTPException(404, f"símbolo no encontrado: {sim}")
    return filas


# ----------------------------------------------------------------------
# GET /api/v1/ticker/{sim}/forecast
# ----------------------------------------------------------------------
HORIZONTES = 10
H_CLASIFICADOR = 21


def _dias_hábiles(desde: dt.date, n: int) -> list[dt.date]:
    dias: list[dt.date] = []
    d = desde
    while len(dias) < n:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:  # skip sáb/dom
            dias.append(d)
    return dias


def _prediccion_proba(clf: object, vector: list[float]) -> float:
    """P(clase positiva) sobre clases {0, 1}, tolerante a una sola clase.

    El clasificador predice "movimiento fuerte" (|retorno 21d| > umbral).
    """
    proba = clf.predict_proba([vector])[0]
    clases = getattr(clf, "classes_", [0, 1])
    if len(clases) == 1:
        return float(proba[0]) if int(clases[0]) == 1 else 1.0 - float(proba[0])
    return float(proba[list(clases).index(1)])


@app.get("/api/v1/ticker/{sim}/forecast")
def forecast(sim: str) -> dict:
    sim = sim.strip().upper()

    try:
        mod = modelos.obtener()
    except ModeloNoDisponible:
        raise HTTPException(503, "modelo no entrenado aún")

    try:
        fila = store.latest_features(sim)
    except StorageError as exc:
        logger.error("forecast %s: %s", sim, exc)
        raise HTTPException(503, "no se pudo leer las features") from exc

    if fila is None:
        raise HTTPException(404, f"símbolo no encontrado: {sim}")

    faltan = [c for c in FEATURE_COLUMNS if c != "h" and c not in fila]
    if faltan:
        raise HTTPException(422, f"features incompletas para {sim}: {', '.join(faltan)}")

    base = {c: _num(fila[c]) for c in FEATURE_COLUMNS if c != "h"}
    sin_valor = [c for c, v in base.items() if v is None]
    if sin_valor:
        raise HTTPException(422, f"features sin valor para {sim}: {', '.join(sin_valor)}")

    precio_actual = round(_num(fila["close"]) or 0.0, 2)
    fecha_asof = fila["fecha"]
    if isinstance(fecha_asof, str):
        try:
            fecha_asof = dt.date.fromisoformat(fecha_asof)
        except ValueError:
            raise HTTPException(422, f"fecha de features inválida para {sim}")

    fechas = _dias_hábiles(fecha_asof, HORIZONTES)
    serie: list[dict] = []
    for h in range(1, HORIZONTES + 1):
        vector = [float(base[c] if c != "h" else h) for c in FEATURE_COLUMNS]
        rets = {
            q: float(reg.predict([vector])[0])
            for q, reg in (("q10", mod["q10"]), ("q50", mod["q50"]), ("q90", mod["q90"]))
        }
        serie.append(
            {
                "h": h,
                "fecha": fechas[h - 1].isoformat(),
                "q10": round(precio_actual * (1 + rets["q10"]), 4),
                "q50": round(precio_actual * (1 + rets["q50"]), 4),
                "q90": round(precio_actual * (1 + rets["q90"]), 4),
            }
        )

    vector_21 = [float(base[c]) for c in FEATURE_COLUMNS if c != "h"]
    prob_mov = round(max(0.0, min(1.0, _prediccion_proba(mod["clf"], vector_21))), 4)

    umbral = float(mod.get("umbral_movimiento", 0.15) or 0.15)

    return {
        "simbolo": sim,
        "fecha_asof": _fecha_iso(fecha_asof),
        "precio_actual": precio_actual,
        "prob_mov_fuerte": prob_mov,
        "prob_calma": round(1.0 - prob_mov, 4),
        "umbral_movimiento": umbral,
        "forecast": serie,
        "modelo": mod["id"],
    }


_montar_static()