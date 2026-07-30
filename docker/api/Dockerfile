FROM python:3.13-slim

WORKDIR /app

# Instalar uv
RUN pip install --no-cache-dir uv

# Copiar dependencias
COPY pyproject.toml uv.lock ./

# Instalar dependencias (frozen para reproducibilidad)
RUN uv sync --frozen --no-dev

# Copiar código de la app
COPY api/ ./api/

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
