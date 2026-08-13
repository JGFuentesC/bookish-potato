FROM python:3.12-slim

WORKDIR /app

# Primero copiamos requirements para aprovechar la caché de layers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App plana: main.py + modelos.py en la raíz de /app (uvicorn main:app)
COPY app/ /app/

# Front estático (vanilla JS) servido por FastAPI en la raíz
COPY static/ /app/static/

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]