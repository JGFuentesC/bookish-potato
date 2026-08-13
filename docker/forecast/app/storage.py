"""Capa de acceso a datos de la forecast-api.

Modos (env ``DATA_MODE``):

- ``mysql`` (default, dev): lee en vivo de MySQL (``finanzas_olap``) con el
  usuario ``dashboards`` (solo SELECT). Es el comportamiento histórico.
- ``sqlite`` (Cloud Run, estático): lee de un snapshot SQLite embebido en la
  imagen (``STATIC_DB``). Cero red, cero credenciales, solo lectura.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:  # MySQL solo es necesario en modo dev (DATA_MODE=mysql)
    import pymysql

    _PIVOTABLE = True
except ImportError:  # pragma: no cover - imagen Cloud Run estática
    pymysql = None  # type: ignore[assignment]
    _PIVOTABLE = False

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Error genérico de acceso a datos (la API lo traduce a HTTP 503)."""


class Store:
    """Contrato de lectura usado por los endpoints."""

    def tickers(
        self,
        q: str | None = None,
        lista: str | None = None,
        sector: str | None = None,
    ) -> list[dict]:
        raise NotImplementedError

    def history(
        self,
        sim: str,
        desde: str | None = None,
        hasta: str | None = None,
    ) -> list[dict] | None:
        """Historia OHLCV; ``None`` si el símbolo no existe."""
        raise NotImplementedError

    def latest_features(self, sim: str) -> dict | None:
        raise NotImplementedError


# ----------------------------------------------------------------------
# Modo MySQL (dev / compose) — SQL histórico sin cambios
# ----------------------------------------------------------------------
class MySQLStore(Store):
    def __init__(self) -> None:
        if pymysql is None:
            raise RuntimeError("pymysql no instalado; DATA_MODE=mysql requiere la dependencia")
        self._host = os.environ.get("MYSQL_HOST", "127.0.0.1")
        self._port = int(os.environ.get("MYSQL_PORT", "3306"))
        self._user = os.environ.get("MYSQL_DASHBOARDS_USER", "dashboards")
        self._password = os.environ.get("MYSQL_DASHBOARDS_PASSWORD", "")
        self._database = os.environ.get("MYSQL_DATABASE", "") or None

    @contextmanager
    def _conectar(self) -> Iterator[Any]:
        conn = pymysql.connect(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            database=self._database,
            charset="utf8mb4",
            autocommit=True,
            cursorclass=pymysql.cursors.DictCursor,
        )
        try:
            yield conn
        finally:
            conn.close()

    def tickers(self, q=None, lista=None, sector=None) -> list[dict]:
        limit = 50 if q else 200
        where: list[str] = []
        params: list[object] = []

        if q:
            patron = f"%{q.strip()}%"
            where.append("(e.simbolo LIKE %s OR e.nombre LIKE %s)")
            params += [patron, patron]
        if lista:
            where.append("l.codigo = %s")
            params.append(lista.strip())
        if sector:
            where.append("s.sector_nombre = %s")
            params.append(sector.strip())

        sql = """
            SELECT e.simbolo, e.nombre, s.sector_nombre AS sector,
                   GROUP_CONCAT(l.codigo SEPARATOR ',') AS listas
            FROM `finanzas_olap`.`dim_empresa` e
            JOIN `finanzas_olap`.`dim_subsector` ss ON ss.subsector_id = e.subsector_id
            JOIN `finanzas_olap`.`dim_sector`     s  ON s.sector_id = ss.sector_id
            LEFT JOIN `finanzas_olap`.`hecho_membresia` hm ON hm.empresa_id = e.empresa_id
            LEFT JOIN `finanzas_olap`.`dim_lista`     l  ON l.lista_id = hm.lista_id
        """
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += (
            " GROUP BY e.empresa_id, e.simbolo, e.nombre, s.sector_nombre"
            " ORDER BY e.simbolo"
            f" LIMIT {limit}"
        )

        try:
            with self._conectar() as conn, conn.cursor() as cur:
                cur.execute(sql, params)
                filas = cur.fetchall()
        except pymysql.MySQLError as exc:
            logger.error("tickers mysql: %s", exc)
            raise StorageError("no se pudo leer el catálogo de tickers") from exc

        return [
            {
                "simbolo": f["simbolo"],
                "nombre": f["nombre"],
                "sector": f["sector"],
                "listas": [x for x in (f["listas"] or "").split(",") if x],
            }
            for f in filas
        ]

    def history(self, sim, desde=None, hasta=None) -> list[dict] | None:
        try:
            with self._conectar() as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT empresa_id FROM `finanzas_olap`.`dim_empresa` WHERE simbolo = %s",
                    (sim,),
                )
                if cur.fetchone() is None:
                    return None

                cur.execute(
                    """SELECT df.fecha, f.open, f.high, f.low, f.close, f.volumen
                       FROM `finanzas_olap`.`fact_precio_diario` f
                       JOIN `finanzas_olap`.`dim_empresa` e ON e.empresa_id = f.empresa_id
                       JOIN `finanzas_olap`.`dim_fecha` df ON df.fecha_id = f.fecha_id
                       WHERE e.simbolo = %s
                         AND (%s IS NULL OR df.fecha >= %s)
                         AND (%s IS NULL OR df.fecha <= %s)
                       ORDER BY df.fecha ASC""",
                    (sim, desde or None, desde or None, hasta or None, hasta or None),
                )
                filas = cur.fetchall()
        except pymysql.MySQLError as exc:
            logger.error("history %s mysql: %s", sim, exc)
            raise StorageError("no se pudo consultar la historia") from exc

        return [
            {
                "fecha": d["fecha"].isoformat() if hasattr(d["fecha"], "isoformat") else str(d["fecha"]),
                "open": float(d["open"]) if d["open"] is not None else None,
                "high": float(d["high"]) if d["high"] is not None else None,
                "low": float(d["low"]) if d["low"] is not None else None,
                "close": float(d["close"]) if d["close"] is not None else None,
                "volumen": int(d["volumen"]) if d["volumen"] is not None else None,
            }
            for d in filas
        ]

    def latest_features(self, sim: str) -> dict | None:
        try:
            with self._conectar() as conn, conn.cursor() as cur:
                cur.execute(
                    """SELECT fecha, close,
                              ret_1d, ret_5d, ret_21d, ret_63d,
                              ma_5, ma_20, ma_50, ma_ratio_20_50,
                              vol_20, rng_mean_20, volumen_log, volume_ratio_20,
                              mes_num, dia_semana, mkt_ret_1d, mkt_vol_20
                       FROM `finanzas_olap`.`feat_diaria`
                       WHERE simbolo = %s
                       ORDER BY fecha DESC
                       LIMIT 1""",
                    (sim,),
                )
                fila = cur.fetchone()
        except pymysql.MySQLError as exc:
            logger.error("forecast %s mysql: %s", sim, exc)
            raise StorageError("no se pudo leer las features") from exc

        if fila is None:
            return None
        fila = dict(fila)
        fecha = fila.get("fecha")
        if fecha is not None and hasattr(fecha, "isoformat"):
            fila["fecha"] = fecha.isoformat()
        return fila


# ----------------------------------------------------------------------
# Modo SQLite estático (Cloud Run) — snapshot embebido de solo lectura
# ----------------------------------------------------------------------
class SqliteStore(Store):
    def __init__(self, ruta: Path | None = None) -> None:
        self._ruta = ruta or Path(os.environ.get("STATIC_DB", "/app/data/static.db"))

    @contextmanager
    def _conectar(self) -> Iterator[sqlite3.Connection]:
        uri = f"file:{self._ruta}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        try:
            yield conn
        finally:
            conn.close()

    def tickers(self, q=None, lista=None, sector=None) -> list[dict]:
        limit = 50 if q else 200
        patron = f"%{q.strip()}%" if q else None

        sql = """
            SELECT e.simbolo, e.nombre, s.sector_nombre AS sector,
                   (SELECT group_concat(l.codigo, ',')
                      FROM hecho_membresia hm JOIN dim_lista l ON l.lista_id = hm.lista_id
                     WHERE hm.empresa_id = e.empresa_id) AS listas
            FROM dim_empresa e
            JOIN dim_subsector ss ON ss.subsector_id = e.subsector_id
            JOIN dim_sector s     ON s.sector_id     = ss.sector_id
            WHERE (? IS NULL OR e.simbolo LIKE ? OR e.nombre LIKE ?)
              AND (? IS NULL OR s.sector_nombre = ?)
              AND (? IS NULL OR EXISTS (
                    SELECT 1 FROM hecho_membresia hm2
                    JOIN dim_lista l2 ON l2.lista_id = hm2.lista_id
                    WHERE hm2.empresa_id = e.empresa_id AND l2.codigo = ?))
            ORDER BY e.simbolo
            LIMIT ?
        """
        params: list[object] = [
            patron, patron, patron,
            sector or None, sector or None,
            lista or None, lista or None,
            limit,
        ]
        try:
            with self._conectar() as conn:
                cur = conn.execute(sql, params)
                filas = cur.fetchall()
        except sqlite3.Error as exc:
            logger.error("tickers sqlite: %s", exc)
            raise StorageError("no se pudo leer el catálogo de tickers") from exc

        return [
            {
                "simbolo": f["simbolo"],
                "nombre": f["nombre"],
                "sector": f["sector"],
                "listas": [x for x in (f["listas"] or "").split(",") if x],
            }
            for f in filas
        ]

    def history(self, sim, desde=None, hasta=None) -> list[dict] | None:
        try:
            with self._conectar() as conn:
                cur = conn.execute(
                    "SELECT 1 FROM dim_empresa WHERE simbolo = ? LIMIT 1",
                    (sim,),
                )
                if cur.fetchone() is None:
                    return None
                cur = conn.execute(
                    """SELECT fecha, open, high, low, close, volumen
                       FROM fact_precio_diario
                       WHERE empresa_id = (SELECT empresa_id FROM dim_empresa WHERE simbolo = ?)
                         AND (? IS NULL OR fecha >= ?)
                         AND (? IS NULL OR fecha <= ?)
                       ORDER BY fecha ASC""",
                    (sim, desde or None, desde or None, hasta or None, hasta or None),
                )
                filas = cur.fetchall()
        except sqlite3.Error as exc:
            logger.error("history %s sqlite: %s", sim, exc)
            raise StorageError("no se pudo consultar la historia") from exc

        return [
            {
                "fecha": f["fecha"],
                "open": float(f["open"]) if f["open"] is not None else None,
                "high": float(f["high"]) if f["high"] is not None else None,
                "low": float(f["low"]) if f["low"] is not None else None,
                "close": float(f["close"]) if f["close"] is not None else None,
                "volumen": int(f["volumen"]) if f["volumen"] is not None else None,
            }
            for f in filas
        ]

    def latest_features(self, sim: str) -> dict | None:
        try:
            with self._conectar() as conn:
                cur = conn.execute(
                    """SELECT simbolo, fecha, close,
                              ret_1d, ret_5d, ret_21d, ret_63d,
                              ma_5, ma_20, ma_50, ma_ratio_20_50,
                              vol_20, rng_mean_20, volumen_log, volume_ratio_20,
                              mes_num, dia_semana, mkt_ret_1d, mkt_vol_20
                       FROM feat_diaria
                       WHERE simbolo = ?
                       LIMIT 1""",
                    (sim,),
                )
                fila = cur.fetchone()
        except sqlite3.Error as exc:
            logger.error("forecast %s sqlite: %s", sim, exc)
            raise StorageError("no se pudo leer las features") from exc
        return dict(fila) if fila is not None else None


def crear_store() -> Store:
    mode = os.environ.get("DATA_MODE", "mysql").strip().lower()
    if mode == "sqlite":
        logger.info("DATA_MODE=sqlite → snapshot estático %s", os.environ.get("STATIC_DB", "/app/data/static.db"))
        return SqliteStore()
    if mode == "mysql":
        return MySQLStore()
    raise RuntimeError(f"DATA_MODE desconocido: {mode!r} (esperado 'mysql' o 'sqlite')")