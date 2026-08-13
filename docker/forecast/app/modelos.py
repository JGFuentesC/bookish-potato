"""Carga lazy (singleton) de los modelos XGBoost + lectura de models/current.json.

El vector de features es FIJO y compartido por regresores y clasificador.

Contrato de horizontes:
    - Regresores cuantílicos (q10/q50/q90): feature ``h`` en 1..10 → retorno
      de cierre a h días: target = close(t+h)/close(t) - 1.
    - Clasificador de volatilidad: predice P(|close(t+21)/close(t) - 1| > umbral)
      = probabilidad de "movimiento fuerte" a 1 mes, sobre el mismo vector sin
      ``h``. El umbral se lee de models/current.json (``umbral_movimiento``).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

import joblib

logger = logging.getLogger(__name__)

#: Orden de columnas de features NUMÉRICAS del modelo (16 fijas + el horizonte ``h``).
FEATURE_COLUMNS: list[str] = [
    "ret_1d",
    "ret_5d",
    "ret_21d",
    "ret_63d",
    "ma_5",
    "ma_20",
    "ma_50",
    "ma_ratio_20_50",
    "vol_20",
    "rng_mean_20",
    "volumen_log",
    "volume_ratio_20",
    "mes_num",
    "dia_semana",
    "mkt_ret_1d",
    "mkt_vol_20",
    "h",
]

LOCALES: dict[str, str] = {
    "forecast_q10": "forecast_q10.joblib",
    "forecast_q50": "forecast_q50.joblib",
    "forecast_q90": "forecast_q90.joblib",
    "updown_clf": "updown_clf.joblib",
    "updown_iso": "updown_iso.joblib",
}


class ModeloNoDisponible(Exception):
    """Sin modelo activo (o incompleto). La API lo traduce a HTTP 503."""


def _resolver_directorio() -> Path:
    """Ruta de models/: MODELS_DIR env > /app/models (contenedor) > ./models (dev)."""
    env = os.environ.get("MODELS_DIR")
    if env:
        return Path(env)
    for cand in (Path("/app/models"), Path.cwd() / "models"):
        if cand.is_dir():
            return cand
    return Path("/app/models")


class Modelos:
    """Singleton perezoso y thread-safe.

    - ``current.json`` se relee en cada petición (fuente de verdad de la versión
      activa). Si cambia el id del modelo, se recargan los pesos joblib.
    - Los .joblib (pesados) solo se cargan una vez y se cachean.
    """

    def __init__(self, directorio: Path | None = None) -> None:
        self._directorio = directorio or _resolver_directorio()
        self._lock = threading.Lock()
        self._cache: dict | None = None

    # ------------------------------------------------------------------
    # current.json
    # ------------------------------------------------------------------
    def _leer_current(self) -> dict | None:
        ruta = self._directorio / "current.json"
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.debug("current.json no disponible en %s", ruta)
            return None

    def info(self) -> dict | None:
        """Metadatos ligeros del modelo activo, sin cargar pesos."""
        cur = self._leer_current()
        if not cur or not cur.get("modelo"):
            return None
        return {
            "id": cur["modelo"],
            "entrenado_el": cur.get("entrenado_el"),
            "cache_activa": bool(self._cache),
        }

    # ------------------------------------------------------------------
    # resolución de rutas
    # ------------------------------------------------------------------
    def _resolver_ruta(self, clave: str, cur: dict) -> Path:
        rutas = cur.get("rutas") or {}
        valor = rutas.get(clave) or LOCALES[clave]
        p = Path(valor)
        if not p.is_absolute():
            p = self._directorio / p
        return p

    @staticmethod
    def _cargar(ruta: Path) -> object | None:
        try:
            return joblib.load(ruta)
        except Exception:  # noqa: BLE001 - cualquier fallo de deserialización
            logger.exception("no se pudo cargar el modelo %s", ruta)
            return None

    # ------------------------------------------------------------------
    # carga + cache
    # ------------------------------------------------------------------
    def obtener(self) -> dict:
        """Devuelve el conjunto de modelos activo (regresores + clasificador).

        Levanta ``ModeloNoDisponible`` si no existe current.json o falta
        alguno de los artefactos obligatorios.
        """
        with self._lock:
            cur = self._leer_current()
            if not cur or not cur.get("modelo"):
                if self._cache is not None:
                    self._cache = None
                raise ModeloNoDisponible("modelo no entrenado aún")

            vid = str(cur["modelo"])
            if self._cache and self._cache.get("id") == vid:
                return self._cache

            # Regresores cuantílicos (obligatorios)
            reg = {}
            for clave, q in (("forecast_q10", "q10"), ("forecast_q50", "q50"), ("forecast_q90", "q90")):
                cargado = self._cargar(self._resolver_ruta(clave, cur))
                if cargado is None:
                    raise ModeloNoDisponible("modelo no entrenado aún")
                reg[q] = cargado

            # Clasificador: preferir el calibrado isotónico, fallback al bosque
            iso = self._cargar(self._resolver_ruta("updown_iso", cur))
            clf = iso
            usa_iso = iso is not None
            if clf is None:
                clf = self._cargar(self._resolver_ruta("updown_clf", cur))
            if clf is None:
                raise ModeloNoDisponible("modelo no entrenado aún")

            self._cache = {
                "id": vid,
                "entrenado_el": cur.get("entrenado_el"),
                "umbral_movimiento": float(cur.get("umbral_movimiento", 0.15) or 0.15),
                "q10": reg["q10"],
                "q50": reg["q50"],
                "q90": reg["q90"],
                "clf": clf,
                "usa_iso": usa_iso,
            }
            logger.info("modelos activos: %s (clasificador calibrado=%s)", vid, usa_iso)
            return self._cache

    def recargar(self) -> dict:
        """Fuerza recarga (útil para retrain sin reiniciar el proceso)."""
        with self._lock:
            self._cache = None
        return self.obtener()


modelos = Modelos()