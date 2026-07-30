"""
Configuración de base de datos: ConnectionPool de psycopg.

Lee DATABASE_URL del entorno, mantiene pool de conexiones (min=2, max=8)
para consultas OLAP desde la API.
"""

import os
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://rama:rama@localhost:5433/rama"
)

pool: ConnectionPool = None


def init_pool():
    """Inicializar el pool de conexiones (lifespan de FastAPI)."""
    global pool
    if pool is None:
        pool = ConnectionPool(
            DATABASE_URL,
            min_size=2,
            max_size=8,
            timeout=10,
        )


def close_pool():
    """Cerrar el pool (lifespan de FastAPI)."""
    global pool
    if pool is not None:
        pool.close()


def get_connection():
    """Obtener una conexión del pool."""
    if pool is None:
        raise RuntimeError("Pool no inicializado")
    return pool.getconn()


def return_connection(conn):
    """Devolver conexión al pool."""
    if pool is not None:
        pool.putconn(conn)
