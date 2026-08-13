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


_CREDENCIAL_FALTANTE = (
    "Falta la credencial %s en el entorno: exportarla o crearla en el .env del repo. "
    "No se usan contraseñas por defecto (seguridad)."
)


def cfg_db(database: str) -> dict:
    """Configuración de conexión MySQL para el usuario ETL."""
    cargar_env()

    def _obligar(nombre: str) -> str:
        valor = os.environ.get(nombre)
        if not valor:
            raise RuntimeError(_CREDENCIAL_FALTANTE % nombre)
        return valor

    return {
        "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.environ.get("MYSQL_PORT", "3306")),
        "user": _obligar("MYSQL_ETL_USER"),
        "password": _obligar("MYSQL_ETL_PASSWORD"),
        "database": database,
        "charset": "utf8mb4",
        "local_infile": True,
        "autocommit": True,
    }
