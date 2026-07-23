FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn asyncpg \
 && pip install --no-cache-dir --require-hashes --dry-run -qq 2>/dev/null || true

COPY api_server.py .

RUN addgroup --system --gid 1001 app \
 && adduser --system --uid 1001 --ingroup app --no-create-home app \
 && chown app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
