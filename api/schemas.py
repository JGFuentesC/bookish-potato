"""
Modelos Pydantic para respuestas de la API OLAP.
"""

from typing import List, Optional
from pydantic import BaseModel


# === Dimensiones ===

class ItemContaminante(BaseModel):
    contaminante_id: int
    codigo: str
    nombre: str
    unidad: str
    categoria_id: int


class ItemCategoria(BaseModel):
    categoria_id: int
    nombre_categoria: str


class ItemEstacion(BaseModel):
    estacion_id: int
    codigo: str
    nombre_estacion: str
    alcaldia_id: int
    latitud: float
    longitud: float
    activo: bool


class ItemAlcaldia(BaseModel):
    alcaldia_id: int
    nombre_alcaldia: str
    entidad: str


class DimensionesResponse(BaseModel):
    tipo: str
    items: List[dict]


# === KPIs ===

class Periodo(BaseModel):
    fecha_inicio: str
    fecha_fin: str


class KPIsResponse(BaseModel):
    periodo: Periodo
    promedio_indice_normalizado: float
    pct_completitud: float
    estaciones_activas: int
    contaminantes_monitoreados: int
    total_mediciones: int


# === Series de tiempo ===

class PuntoSerieTiempo(BaseModel):
    fecha: str
    valor_promedio: Optional[float] = None
    valor_min: Optional[float] = None
    valor_max: Optional[float] = None
    indice_normalizado: Optional[float] = None
    mediciones_validas: int
    pct_completitud: float


class SeriesTiempoResponse(BaseModel):
    granularidad: str
    contaminante: str
    puntos: List[PuntoSerieTiempo]


# === Mapa ===

class EstacionMapa(BaseModel):
    estacion_id: int
    codigo: str
    nombre: str
    alcaldia: str
    latitud: float
    longitud: float
    valor: Optional[float]
    indice_normalizado: Optional[float]


class MapaEstacionesResponse(BaseModel):
    contaminante: str
    fecha_referencia: str
    estaciones: List[EstacionMapa]


# === Rankings ===

class ItemRankingEstacion(BaseModel):
    posicion: int
    codigo: str
    nombre: str
    alcaldia: str
    valor_promedio: Optional[float]
    indice_normalizado: float


class RankingEstacionesResponse(BaseModel):
    contaminante: str
    periodo: Periodo
    ranking: List[ItemRankingEstacion]


class ItemRankingContaminante(BaseModel):
    posicion: int
    codigo: str
    nombre: str
    categoria: str
    indice_normalizado_promedio: float


class RankingContaminantesResponse(BaseModel):
    periodo: Periodo
    ranking: List[ItemRankingContaminante]


# === Completitud ===

class ItemCompletitud(BaseModel):
    clave: str
    etiqueta: str
    mediciones_totales: int
    mediciones_validas: int
    pct_completitud: float


class CompletitudResponse(BaseModel):
    agrupado_por: str
    items: List[ItemCompletitud]
