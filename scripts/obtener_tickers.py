from io import StringIO
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

WIKI_SP500 = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
NASDAQ_LISTED = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"


def yahoo_symbol(symbol: str) -> str:
    return symbol.replace(".", "-")


def descargar(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def sp500() -> pd.DataFrame:
    html = descargar(WIKI_SP500)
    tablas = pd.read_html(StringIO(html), attrs={"id": "constituents"})
    df = tablas[0]
    df = df[["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]].copy()
    df.columns = ["symbol", "name", "sector", "subsector"]
    df["symbol"] = df["symbol"].str.strip().map(yahoo_symbol)
    return df


def nasdaq() -> pd.DataFrame:
    texto = descargar(NASDAQ_LISTED)
    df = pd.read_csv(pd.io.common.StringIO(texto), sep="|", dtype=str, na_filter=False)
    df = df[df["Test Issue"] != "Y"].copy()
    df = df[["Symbol", "Security Name"]].copy()
    df.columns = ["symbol", "name"]
    df = df[df["name"].astype(str).str.strip() != ""]
    df["symbol"] = df["symbol"].str.strip().map(yahoo_symbol)
    df = df[df["symbol"] != ""].drop_duplicates("symbol")
    return df


def amex() -> pd.DataFrame:
    texto = descargar(OTHER_LISTED)
    df = pd.read_csv(pd.io.common.StringIO(texto), sep="|", dtype=str, na_filter=False)
    df = df[df["Test Issue"] != "Y"]
    df = df[df["Exchange"] == "A"]
    df = df[["ACT Symbol", "Security Name"]].copy()
    df.columns = ["symbol", "name"]
    df = df[df["name"].astype(str).str.strip() != ""]
    df["symbol"] = df["symbol"].str.strip().map(yahoo_symbol)
    df = df[df["symbol"] != ""].drop_duplicates("symbol")
    return df


def guardar(nombre: str, df: pd.DataFrame) -> None:
    ruta = DATA_DIR / nombre
    df.to_csv(ruta, index=False)
    print(f"{nombre}: {len(df)} tickers -> {ruta}")


if __name__ == "__main__":
    guardar("sp500.csv", sp500())
    guardar("nasdaq.csv", nasdaq())
    guardar("amex.csv", amex())
