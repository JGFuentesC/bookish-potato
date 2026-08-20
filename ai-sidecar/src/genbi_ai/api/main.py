from fastapi import FastAPI

app = FastAPI(title="GenBI AI sidecar", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}