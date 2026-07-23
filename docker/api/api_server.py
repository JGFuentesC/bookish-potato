"""API server — puente entre el dashboard HTML y PostgreSQL.

Endpoints:
  GET /api/data?cont=NOX&from=2015&to=2025[&stations=TLA,MER,UIZ]
    Devuelve JSON con el mismo esquema que el CSV (24 columnas dim_*/mt_*).
    Si no se especifica stations, devuelve todas.

  GET /health
    {"status": "ok"}
"""
import os

from asyncpg import create_pool
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rama:rama@localhost:5433/rama")

app = FastAPI(title="RAMA API", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

pool = None


@app.on_event("startup")
async def startup():
    global pool
    pool = await create_pool(DATABASE_URL, min_size=2, max_size=8)


@app.on_event("shutdown")
async def shutdown():
    if pool:
        await pool.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/data")
async def get_data(
    cont: str = Query(..., description="Codigo de contaminante (ej: NOX)"),
    fr: int = Query(..., alias="from", description="Anio inicio"),
    to: int = Query(..., alias="to", description="Anio fin"),
    stations: str | None = Query(None, description="Lista separada por comas (ej: TLA,MER)"),
):
    query = """
        SELECT
            dim_fecha, dim_anio, dim_mes, dim_nombre_mes, dim_trimestre,
            dim_estacion_anio, dim_estacion, dim_nombre_estacion, dim_alcaldia,
            dim_lat_lon, dim_contaminante, dim_nombre_contaminante,
            mt_valor_mean, mt_valor_max, mt_valor_min, mt_valor_std,
            mt_valor_p50, mt_valor_p95, mt_valor_p98,
            mt_horas_validas, mt_horas_esperadas,
            mt_dias_con_dato, mt_dias_esperados, mt_pct_datos
        FROM gold.rama_mensual_bi
        WHERE dim_contaminante = $1
          AND dim_anio >= $2
          AND dim_anio <= $3
    """
    params = [cont, fr, to]
    idx = 4

    if stations:
        st_list = [s.strip() for s in stations.split(",") if s.strip()]
        if st_list:
            placeholders = ", ".join(f"${i}" for i in range(idx, idx + len(st_list)))
            query += f" AND dim_estacion IN ({placeholders})"
            params.extend(st_list)

    query += " ORDER BY dim_fecha, dim_estacion"

    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)

    return {
        "stations": [dict(r) for r in rows],
        "count": len(rows),
        "params": {"cont": cont, "from": fr, "to": to},
    }
