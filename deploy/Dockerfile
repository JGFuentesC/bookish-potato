FROM python:3.12-slim

# Parcheo de CVEs del sistema base (Debian) antes de instalar nada.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Dependencias de runtime SOLO (sin pymysql/polars: en modo sqlite no se usan).
COPY deploy/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Mismo código fuente de la API del forecast-api local (sin duplicación).
COPY docker/forecast/app/ /app/
COPY docker/forecast/static/ /app/static/

# Modelos ML + snapshot SQLite estático embebidos en la imagen.
COPY models/ /app/models/
COPY deploy/data/static.db /app/data/static.db

# Principio de mínimo privilegio a nivel de proceso.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]