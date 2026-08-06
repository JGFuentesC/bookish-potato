import os
from pathlib import Path


def cargar_env() -> None:
    """Carga .env (raíz del repo) sin sobrescribir variables ya exportadas."""
    ruta = Path(__file__).resolve().parent.parent / ".env"
    if ruta.exists():
        for linea in ruta.read_text().splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, _, valor = linea.partition("=")
                os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


def cfg_db(database: str) -> dict:
    """Configuración de conexión MySQL para el usuario ETL."""
    cargar_env()
    return {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": os.environ.get("MYSQL_ETL_USER", "etl"),
        "password": os.environ.get("MYSQL_ETL_PASSWORD", "etl_dev_password"),
        "database": database,
        "charset": "utf8mb4",
        "local_infile": True,
        "autocommit": True,
    }
