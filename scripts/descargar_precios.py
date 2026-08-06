import asyncio
import random
import sys
from pathlib import Path

import httpx
import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PRICES_DIR = DATA_DIR / "prices"
PRICES_DIR.mkdir(parents=True, exist_ok=True)

TICKERS = DATA_DIR / "tickers_all.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
}
INTERVAL = "1d"
RANGO = "5y"
CONCURRENCIA = 25
REINTENTOS = 6
COLUMNAS = ["date", "open", "high", "low", "close", "adjclose", "volume"]
LOG = DATA_DIR / "descarga.log"
FALLOS = DATA_DIR / "fallos.csv"


def log(msg: str) -> None:
    with LOG.open("a") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def cargar_tickers() -> list[str]:
    return pd.read_csv(TICKERS, dtype=str, keep_default_na=False)["symbol"].tolist()


def ya_descargado(sym: str) -> bool:
    ruta = PRICES_DIR / f"{sym}.csv"
    if not ruta.exists():
        return False
    try:
        df = pd.read_csv(ruta)
    except Exception:
        return False
    return len(df) > 0


async def descargar_uno(cliente: httpx.AsyncClient, sem: asyncio.Semaphore, sym: str) -> bool:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
    params = {"range": RANGO, "interval": INTERVAL}
    async with sem:
        for intento in range(REINTENTOS):
            try:
                r = await cliente.get(url, params=params, headers=HEADERS, timeout=30)
                if r.status_code == 429:
                    espera = 2 ** intento + random.uniform(0, 1)
                    await asyncio.sleep(espera)
                    continue
                r.raise_for_status()
                payload = r.json()
                res = payload.get("chart", {}).get("result")
                if not res:
                    return False
                res = res[0]
                timestamps = res.get("timestamp") or []
                indicadores = res.get("indicators", {}).get("quote", [{}])
                if not timestamps or not indicadores:
                    return False
                quote = indicadores[0]
                adj = res.get("indicators", {}).get("adjclose", [{}])
                adj = (adj[0].get("adjclose") if adj else None) or quote.get("close")
                df = pd.DataFrame(
                    {
                        "date": pd.to_datetime(timestamps, unit="s").date,
                        "open": quote.get("open"),
                        "high": quote.get("high"),
                        "low": quote.get("low"),
                        "close": quote.get("close"),
                        "adjclose": adj,
                        "volume": quote.get("volume"),
                    }
                ).dropna(subset=["close"])
                if df.empty:
                    return False
                df.to_csv(PRICES_DIR / f"{sym}.csv", index=False)
                return True
            except (httpx.HTTPError, ValueError) as e:
                espera = 2 ** intento + random.uniform(0, 1)
                await asyncio.sleep(espera)
        return False


async def extraer(solo: str | None = None, limite: int | None = None) -> None:
    tickers = [solo] if solo else cargar_tickers()
    if limite:
        tickers = tickers[:limite]
    pendientes = [t for t in tickers if not ya_descargado(t)]
    log(f"pendientes: {len(pendientes)} de {len(tickers)}")

    fallos: list[str] = []
    ok = 0
    sem = asyncio.Semaphore(CONCURRENCIA)
    async with httpx.AsyncClient(http2=False) as cliente:
        for i in range(0, len(pendientes), CONCURRENCIA * 2):
            lote = pendientes[i : i + CONCURRENCIA * 2]
            resultados = await asyncio.gather(
                *(descargar_uno(cliente, sem, s) for s in lote)
            )
            for s, exito in zip(lote, resultados):
                if exito:
                    ok += 1
                else:
                    fallos.append(s)
            log(f"progreso {min(i + len(lote), len(pendientes))}/{len(pendientes)} (ok {ok})")

    pd.DataFrame({"symbol": fallos}).to_csv(FALLOS, index=False)
    log(f"final: ok={ok} fallos={len(fallos)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    solo = None
    limite = None
    if args and args[0] == "--sym":
        solo = args[1]
    if args and args[0] == "--limit":
        limite = int(args[1])
    asyncio.run(extraer(solo, limite))
