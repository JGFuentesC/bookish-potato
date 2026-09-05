from fastapi import FastAPI

from genbi_ai.api.nl2sql import router as nl2sql_router
from genbi_ai.api.query import router as query_router

app = FastAPI(title="GenBI AI sidecar", version="0.1.0")
app.include_router(query_router)
app.include_router(nl2sql_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}