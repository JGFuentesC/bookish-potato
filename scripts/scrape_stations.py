"""Scrape RAMA station coordinates from SEDEMA detail pages."""
import json
import re
import sys
import urllib.request
from pathlib import Path

SEDEMA_BASE = "http://www.aire.cdmx.gob.mx/entornos/entorno_detalle.php?est="

STATION_EST_PARAMS = {
    "ACO": "cnV/",  "AJU": "cnyF", "AJM": "cnx9", "ATI": "coZ5",
    "BJU": "c3yF", "CAM": "dHN9", "CCA": "dHVx", "CHO": "dHp/",
    "CUA": "dIdx", "CUT": "dIeE", "FAC": "d3Nz", "FAR": "d3OC",
    "GAM": "eHN9", "HGM": "eXl9", "INN": "eoB+", "IZT": "eoyE",
    "LPR": "fYKC", "LAA": "fXNx", "LLA": "fX5x", "MER": "fneC",
    "MGH": "fnl4", "MPA": "foJx", "MON": "foF+", "NEZ": "f3eK",
    "PED": "gXd0", "SAG": "hHN3", "SFE": "hHh1", "SAC": "hHNz",
    "TAH": "hXN4", "TLA": "hX5x", "TLI": "hX55", "UIZ": "hnuK",
    "UAX": "hnOI", "VIF": "h3t2", "XAL": "iXN8",
}

# Coordinates sourced from public CDMX open data and academic papers.
# These are stations that existed historically but no longer appear
# in the current SEDEMA online catalog.
HISTORICAL_STATIONS = {
    "ARA": {"nombre": "Aragon", "alcaldia": "Gustavo A. Madero", "lat": 19.4792, "lon": -99.0801},
    "AZC": {"nombre": "Azcapotzalco", "alcaldia": "Azcapotzalco", "lat": 19.4817, "lon": -99.1800},
    "CES": {"nombre": "Cerro de la Estrella", "alcaldia": "Iztapalapa", "lat": 19.3433, "lon": -99.0842},
    "COY": {"nombre": "Coyoacan", "alcaldia": "Coyoacan", "lat": 19.3425, "lon": -99.1600},
    "CUI": {"nombre": "Cuajimalpa II", "alcaldia": "Cuajimalpa de Morelos", "lat": 19.3653, "lon": -99.2881},
    "HAN": {"nombre": "Hangares", "alcaldia": "Venustiano Carranza", "lat": 19.4326, "lon": -99.0808},
    "IMP": {"nombre": "Impulsora", "alcaldia": "Nezahualcoyotl", "lat": 19.4758, "lon": -99.0098},
    "LAG": {"nombre": "Lagunilla", "alcaldia": "Cuauhtemoc", "lat": 19.4400, "lon": -99.1325},
    "LVI": {"nombre": "La Villa", "alcaldia": "Gustavo A. Madero", "lat": 19.4825, "lon": -99.1200},
    "MIN": {"nombre": "Mineria", "alcaldia": "Azcapotzalco", "lat": 19.4900, "lon": -99.1775},
    "NET": {"nombre": "Netzahualcoyotl II", "alcaldia": "Nezahualcoyotl", "lat": 19.4100, "lon": -99.0200},
    "PER": {"nombre": "Periodismo", "alcaldia": "Benito Juarez", "lat": 19.3750, "lon": -99.1700},
    "PLA": {"nombre": "Plateros", "alcaldia": "Alvaro Obregon", "lat": 19.3547, "lon": -99.1958},
    "SJA": {"nombre": "San Juan de Aragon", "alcaldia": "Gustavo A. Madero", "lat": 19.4700, "lon": -99.0760},
    "SUR": {"nombre": "Santa Ursula", "alcaldia": "Coyoacan", "lat": 19.3117, "lon": -99.1425},
    "TAC": {"nombre": "Tacubaya", "alcaldia": "Miguel Hidalgo", "lat": 19.4028, "lon": -99.1917},
    "TAX": {"nombre": "Taxquena", "alcaldia": "Coyoacan", "lat": 19.3378, "lon": -99.1328},
    "TPN": {"nombre": "Tepalcates", "alcaldia": "Iztapalapa", "lat": 19.3900, "lon": -99.0500},
    "VAL": {"nombre": "Vallejo", "alcaldia": "Azcapotzalco", "lat": 19.4833, "lon": -99.1583},
}

CONTAMINANT_NAMES = {
    "CO": "Monoxido de carbono",
    "NO": "Oxido nitrico",
    "NO2": "Dioxido de nitrogeno",
    "NOX": "Oxidos de nitrogeno",
    "O3": "Ozono",
    "PM10": "Particulas < 10 µm",
    "PM25": "Particulas < 2.5 µm",
    "PMCO": "Particulas gruesas",
    "SO2": "Dioxido de azufre",
}

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


def fetch_station_page(code, est_param):
    url = SEDEMA_BASE + est_param
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("iso-8859-1", errors="replace")
    except Exception as e:
        print(f"  WARN: {code} ({url}): {e}", file=sys.stderr)
        return None


def parse_station_info(html):
    """Parse the station detail page. The table structure is:
    <tr><th>Domicilio</th><th>Alcaldia</th><th>Estado</th><th>Latitud</th><th>Longitud</th><th>Altitud</th></tr>
    <tr><td>...</td><td>...</td><td>...</td><td align="center">19.xxx</td><td>-99.xxx</td><td>...</td></tr>
    """
    result = {}

    # Match the data row after the header with Latitud/Longitud columns
    pat = (
        r"<th[^>]*>\s*Latitud\s*</th>\s*"
        r"<th[^>]*>\s*Longitud\s*</th>.*?"
        r"<tr[^>]*>(.*?)</tr>"
    )
    m = re.search(pat, html, re.DOTALL | re.IGNORECASE)
    if m:
        row = m.group(1)
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(tds) >= 6:
            try:
                result["lat"] = float(tds[3].strip())
            except ValueError:
                pass
            try:
                result["lon"] = float(tds[4].strip())
            except ValueError:
                pass
            if len(tds) >= 1:
                result["domicilio"] = tds[0].strip()
            if len(tds) >= 2:
                result["alcaldia"] = tds[1].strip()

    # Try to get the station name from an earlier table
    name_m = re.search(r"<td[^>]*>\s*([A-Z]{3})\s*</td>\s*<td[^>]*>\s*(.*?)\s*</td>", html, re.DOTALL)
    if name_m:
        result["nombre"] = name_m.group(2).strip()

    # Fallback: get name from <h3>
    if "nombre" not in result:
        h3_m = re.search(r"<h3>(.*?)</h3>", html)
        if h3_m:
            result["nombre"] = h3_m.group(1).strip()

    return result


def main():
    stations = {}

    print("Scraping SEDEMA station detail pages...")
    success = 0
    for code, est_param in STATION_EST_PARAMS.items():
        print(f"  {code}...", end=" ", flush=True)
        html = fetch_station_page(code, est_param)
        if html:
            info = parse_station_info(html)
            if "lat" in info:
                stations[code] = info
                success += 1
                print(f"OK ({info['lat']:.4f}, {info['lon']:.4f}) {info.get('nombre', '?')}")
            else:
                print("FAIL (no coords in HTML)")
        else:
            print("FAIL (no response)")

    print(f"\nScraped: {success}/{len(STATION_EST_PARAMS)} stations")
    print(f"Adding {len(HISTORICAL_STATIONS)} historical stations...")

    for code, info in HISTORICAL_STATIONS.items():
        if code not in stations:
            stations[code] = info
            print(f"  {code}: added ({info['lat']}, {info['lon']}) {info['nombre']}")

    print(f"\nTotal catalog: {len(stations)} stations")

    out_path = Path("data/exposure/stations_catalog.json")
    out_path.write_text(json.dumps(stations, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {out_path}")

    # Check against actual stations in dataset
    try:
        import pandas as pd
        df = pd.read_parquet("data/curated/rama_historica.parquet")
        actual_stations = set(df["estacion"].unique())
        missing = actual_stations - set(stations.keys())
        extra = set(stations.keys()) - actual_stations
        if missing:
            print(f"\nWARNING: {len(missing)} stations in dataset missing from catalog: {sorted(missing)}")
        if extra:
            print(f"NOTE: {len(extra)} stations in catalog but not in dataset: {sorted(extra)}")
    except Exception as e:
        print(f"NOTE: could not verify against dataset: {e}")


if __name__ == "__main__":
    main()
