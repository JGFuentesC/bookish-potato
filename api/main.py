"""
API FastAPI para exponer el cubo OLAP.

Endpoints:
  GET /health — healthcheck
  GET /api/dimensiones/{tipo} — contaminantes, categorias, estaciones, alcaldias
  GET /api/kpis — KPIs agregados
  GET /api/series-tiempo — series temporales (hora/dia/mes)
  GET /api/mapa-estaciones — últimas lecturas por estación
  GET /api/ranking/estaciones — top/bottom estaciones
  GET /api/ranking/contaminantes — top contaminantes
  GET /api/completitud — % de completitud agrupado

Sirve también el dashboard estático en /.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from api import db, consultas, schemas


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializar/cerrar pool de conexiones en lifespan de FastAPI."""
    db.init_pool()
    yield
    db.close_pool()


app = FastAPI(
    title="RAMA OLAP API",
    description="Cubo OLAP para análisis de calidad del aire (CDMX/ZMVM)",
    version="0.1.0",
    lifespan=lifespan,
)


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
def health():
    """Healthcheck para Docker."""
    return {"status": "ok"}


# ============================================================================
# Dimensiones
# ============================================================================

@app.get("/api/dimensiones/{tipo}")
def get_dimensiones(tipo: str) -> schemas.DimensionesResponse:
    """
    Obtener dimensiones para poblar filtros del dashboard.

    tipo: contaminantes | categorias | estaciones | alcaldias
    """
    if tipo not in ["contaminantes", "categorias", "estaciones", "alcaldias"]:
        raise HTTPException(status_code=400, detail="tipo inválido")

    items = consultas.obtener_dimensiones(tipo)
    return schemas.DimensionesResponse(tipo=tipo, items=items)


@app.get("/api/rango-fechas", response_model=schemas.RangoFechasResponse)
def get_rango_fechas():
    """
    Rango de fechas con datos. El dashboard lo usa al arrancar para fijar
    fechas explícitas en todos los filtros (los datos terminan en 2025, no hoy).
    """
    try:
        fecha_min, fecha_max = consultas.obtener_rango_fechas_disponibles()
        return schemas.RangoFechasResponse(fecha_min=fecha_min, fecha_max=fecha_max)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# KPIs
# ============================================================================

@app.get("/api/kpis", response_model=schemas.KPIsResponse)
def get_kpis(
    contaminante: str = Query(None),
    alcaldia_id: int = Query(None),
    fecha_inicio: str = Query(None),
    fecha_fin: str = Query(None),
):
    """
    KPIs agregados: promedio índice, % completitud, estaciones, contaminantes, total mediciones.

    Si no se pasan fechas, usa últimos 12 meses.
    """
    try:
        return consultas.obtener_kpis(
            contaminante=contaminante,
            alcaldia_id=alcaldia_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Series de Tiempo
# ============================================================================

@app.get("/api/series-tiempo", response_model=schemas.SeriesTiempoResponse)
def get_series_tiempo(
    contaminante: str = Query(..., description="Código del contaminante (ej. PM25)"),
    granularidad: str = Query("dia", description="hora | dia | mes"),
    estacion: str = Query(None, description="Código de estación (ej. MER)"),
    alcaldia_id: int = Query(None),
    fecha_inicio: str = Query(None),
    fecha_fin: str = Query(None),
):
    """
    Serie temporal de un contaminante con granularidad hora/dia/mes.

    Guardrail: granularidad='hora' requiere estacion y limita a 90 días.
    """
    try:
        if granularidad == "hora" and not estacion:
            raise HTTPException(
                status_code=400,
                detail="granularidad='hora' requiere parámetro 'estacion'",
            )

        puntos = consultas.obtener_series_tiempo(
            contaminante=contaminante,
            granularidad=granularidad,
            estacion=estacion,
            alcaldia_id=alcaldia_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        )

        return schemas.SeriesTiempoResponse(
            granularidad=granularidad,
            contaminante=contaminante,
            puntos=puntos,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Mapa
# ============================================================================

@app.get("/api/mapa-estaciones", response_model=schemas.MapaEstacionesResponse)
def get_mapa_estaciones(
    contaminante: str = Query(..., description="Código del contaminante"),
    fecha: str = Query(None, description="Fecha (ISO-8601, default = última disponible)"),
):
    """Última lectura por estación de un contaminante para el mapa Leaflet."""
    try:
        fecha_ref, estaciones = consultas.obtener_mapa_estaciones(
            contaminante=contaminante,
            fecha=fecha,
        )

        return schemas.MapaEstacionesResponse(
            contaminante=contaminante,
            fecha_referencia=fecha_ref,
            estaciones=[schemas.EstacionMapa(**e) for e in estaciones],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Rankings
# ============================================================================

@app.get("/api/ranking/estaciones", response_model=schemas.RankingEstacionesResponse)
def get_ranking_estaciones(
    contaminante: str = Query(...),
    fecha_inicio: str = Query(None),
    fecha_fin: str = Query(None),
    orden: str = Query("desc", description="asc | desc"),
    limit: int = Query(10, ge=1, le=54),
):
    """Ranking de estaciones por índice normalizado."""
    try:
        f_inicio, f_fin, ranking = consultas.obtener_ranking_estaciones(
            contaminante=contaminante,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            orden=orden,
            limit=limit,
        )

        return schemas.RankingEstacionesResponse(
            contaminante=contaminante,
            periodo=schemas.Periodo(
                fecha_inicio=f_inicio,
                fecha_fin=f_fin,
            ),
            ranking=[schemas.ItemRankingEstacion(**r) for r in ranking],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ranking/contaminantes", response_model=schemas.RankingContaminantesResponse)
def get_ranking_contaminantes(
    estacion: str = Query(None),
    alcaldia_id: int = Query(None),
    fecha_inicio: str = Query(None),
    fecha_fin: str = Query(None),
    limit: int = Query(9, ge=1, le=9),
):
    """Ranking de contaminantes por índice normalizado."""
    try:
        f_inicio, f_fin, ranking = consultas.obtener_ranking_contaminantes(
            estacion=estacion,
            alcaldia_id=alcaldia_id,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            limit=limit,
        )

        return schemas.RankingContaminantesResponse(
            periodo=schemas.Periodo(
                fecha_inicio=f_inicio,
                fecha_fin=f_fin,
            ),
            ranking=[schemas.ItemRankingContaminante(**r) for r in ranking],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Completitud
# ============================================================================

@app.get("/api/completitud", response_model=schemas.CompletitudResponse)
def get_completitud(
    agrupar_por: str = Query("contaminante", description="contaminante | estacion | anio"),
    contaminante: str = Query(None),
    estacion: str = Query(None),
    alcaldia_id: int = Query(None),
):
    """% de completitud agrupado por contaminante/estacion/año."""
    try:
        if agrupar_por not in ["contaminante", "estacion", "anio"]:
            raise HTTPException(status_code=400, detail="agrupar_por inválido")

        items = consultas.obtener_completitud(
            agrupar_por=agrupar_por,
            contaminante=contaminante,
            estacion=estacion,
            alcaldia_id=alcaldia_id,
        )

        return schemas.CompletitudResponse(
            agrupado_por=agrupar_por,
            items=[schemas.ItemCompletitud(**i) for i in items],
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Dashboard Estático
# ============================================================================

# Mount static files (HTML, JS, CSS) — after all /api routes so they don't conflict
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
