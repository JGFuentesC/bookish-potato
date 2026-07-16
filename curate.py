"""
Curacion de datos historicos RAMA (Red Automatica de Monitoreo Atmosferico).

Lee archivos .xls de data/raw/files/, los transforma a formato tidy (long),
reemplaza el sentinel -99 por null, corrige HORA=24, y escribe un solo
archivo Parquet en data/curated/rama_historica.parquet.
"""

import re
from datetime import date
from pathlib import Path
from typing import Annotated, Any

import polars as pl
from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

# ---------------------------------------------------------------------------
# configuracion
# ---------------------------------------------------------------------------

INPUT_DIR = Path("data/raw/files")
OUTPUT_DIR = Path("data/curated")
OUTPUT_FILE = OUTPUT_DIR / "rama_historica.parquet"

MISSING_SENTINEL = -99
CHUNK_SIZE = 50  # procesar en lotes para no saturar memoria

CONTAMINANTES: set[str] = {"CO", "NO", "NO2", "NOX", "O3", "PM10", "PM25", "PMCO", "SO2"}

# ---------------------------------------------------------------------------
# modelos pydantic
# ---------------------------------------------------------------------------


def _estacion_valida(v: str) -> str:
    if not re.fullmatch(r"[A-Z]{3}", v):
        raise ValueError(f"Codigo de estacion invalido: {v!r}")
    return v


def _contaminante_valido(v: str) -> str:
    if v not in CONTAMINANTES:
        raise ValueError(f"Contaminante desconocido: {v!r}")
    return v


class FilaRAMA(BaseModel):
    """Una fila del dataset curado. Representa una medicion puntual."""

    FECHA: date
    HORA: int = Field(ge=0, le=23)
    estacion: Annotated[str, AfterValidator(_estacion_valida)]
    contaminante: Annotated[str, AfterValidator(_contaminante_valido)]
    valor: float | None

    @field_validator("HORA", mode="before")
    @classmethod
    def _corregir_hora_24(cls, v: Any) -> int:
        if isinstance(v, (int, float)) and v == 24:
            return 0
        return int(v)

    @field_validator("FECHA", mode="before")
    @classmethod
    def _parse_fecha(cls, v: Any) -> date:
        if isinstance(v, date):
            return v
        if hasattr(v, "date"):
            return v.date()
        raise ValueError(f"No se pudo convertir a date: {v!r}")


class MetadataRAMA(BaseModel):
    """Metadata del dataset curado."""

    total_filas: int
    filas_validas: int
    estaciones: list[str]
    contaminantes: list[str]
    fecha_min: date
    fecha_max: date
    archivos_procesados: int


class ConfigPipeline(BaseModel):
    """Configuracion del pipeline de curacion."""

    input_dir: Path = Field(default=INPUT_DIR)
    output_dir: Path = Field(default=OUTPUT_DIR)
    missing_sentinel: int = Field(default=MISSING_SENTINEL)
    chunk_size: int = Field(default=CHUNK_SIZE)

    @field_validator("input_dir")
    @classmethod
    def _existe_input(cls, v: Path) -> Path:
        if not v.exists():
            raise ValueError(f"Directorio de entrada no existe: {v}")
        return v

    @model_validator(mode="after")
    def _crear_output(self) -> "ConfigPipeline":
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self

    @model_validator(mode="after")
    def _chunk_size_positivo(self) -> "ConfigPipeline":
        if self.chunk_size < 1:
            raise ValueError("chunk_size debe ser >= 1")
        return self


# ---------------------------------------------------------------------------
# funciones del pipeline
# ---------------------------------------------------------------------------


def extraer_contaminante(filename: str) -> str:
    """Extrae el codigo de contaminante del nombre de archivo (ej: 1986CO.xls -> CO)."""
    stem = Path(filename).stem
    match = re.search(r"\d{4}([A-Z0-9]+)$", stem)
    if not match:
        raise ValueError(f"No se pudo extraer contaminante de: {filename!r}")
    return match.group(1)


def corregir_hora(df: pl.DataFrame) -> pl.DataFrame:
    """
    HORA 24 se usa como medianoche del dia siguiente.
    Convertimos HORA=24 -> hora=0 y sumamos un dia a la fecha.
    """
    mask = df["HORA"] == 24
    if mask.any():
        df = df.with_columns(
            pl.when(mask)
            .then(df["FECHA"].cast(pl.Date) + pl.duration(days=1))
            .otherwise(df["FECHA"])
            .alias("FECHA"),
            pl.when(mask).then(0).otherwise(df["HORA"]).alias("HORA"),
        )
    return df


def procesar_archivo(path: Path) -> pl.DataFrame:
    """Lee un .xls, lo transforma a formato long (tidy) y reemplaza el sentinel."""
    contaminante = extraer_contaminante(path.name)

    df = pl.read_excel(
        path,
        engine="calamine",
        schema_overrides={"FECHA": pl.Date, "HORA": pl.Int64},
    )

    # Dropear columnas que no son FECHA, HORA ni estacion
    columnas_extra = [c for c in df.columns if c not in ("FECHA", "HORA")]

    # Melt: wide -> long
    df = df.unpivot(
        index=["FECHA", "HORA"],
        on=columnas_extra,
        variable_name="estacion",
        value_name="valor",
    )

    df = df.with_columns(pl.lit(contaminante).alias("contaminante"))

    # Reemplazar sentinel por null
    df = df.with_columns(
        pl.when(pl.col("valor") == MISSING_SENTINEL)
        .then(None)
        .otherwise(pl.col("valor"))
        .alias("valor")
    )

    # Corregir HORA=24
    df = corregir_hora(df)

    # Garantizar tipos finales
    df = df.select(
        pl.col("FECHA").cast(pl.Date),
        pl.col("HORA").cast(pl.Int8),
        pl.col("estacion").cast(pl.Utf8),
        pl.col("contaminante").cast(pl.Utf8),
        pl.col("valor").cast(pl.Float32),
    )

    return df


def validar_dataframe(df: pl.DataFrame, *, strict: bool = True) -> None:
    """Valida que el DataFrame cumpla con el esquema esperado usando pydantic."""
    columnas_requeridas = {"FECHA", "HORA", "estacion", "contaminante", "valor"}
    faltantes = columnas_requeridas - set(df.columns)
    if faltantes:
        raise ValueError(f"Faltan columnas: {faltantes}")

    if strict:
        sobrantes = set(df.columns) - columnas_requeridas
        if sobrantes:
            raise ValueError(f"Columnas inesperadas: {sobrantes}")

    muestra = df.head(10)
    errores: list[str] = []
    for row in muestra.iter_rows(named=True):
        try:
            FilaRAMA.model_validate(row)
        except ValidationError as e:
            errores.append(str(e))

    if errores:
        raise ValueError(f"Errores de validacion en muestra ({len(errores)}):\n" + "\n".join(errores[:5]))


def generar_metadata(df: pl.DataFrame, *, archivos: int) -> MetadataRAMA:
    """Genera metadata del dataset curado."""
    return MetadataRAMA(
        total_filas=df.height,
        filas_validas=df["valor"].is_not_null().sum(),
        estaciones=sorted(df["estacion"].unique().to_list()),
        contaminantes=sorted(df["contaminante"].unique().to_list()),
        fecha_min=df["FECHA"].min(),  # type: ignore[arg-type]
        fecha_max=df["FECHA"].max(),  # type: ignore[arg-type]
        archivos_procesados=archivos,
    )


# ---------------------------------------------------------------------------
# pipeline principal
# ---------------------------------------------------------------------------


def ejecutar(config: ConfigPipeline | None = None) -> MetadataRAMA:
    """Ejecuta el pipeline de curacion completo. Retorna metadata del resultado."""
    if config is None:
        config = ConfigPipeline()

    archivos = sorted(config.input_dir.glob("*.xls"))
    if not archivos:
        raise FileNotFoundError(f"No se encontraron archivos .xls en {config.input_dir}")

    print(f"Procesando {len(archivos)} archivos en lotes de {config.chunk_size}...")

    chunks: list[pl.DataFrame] = []
    errores: list[str] = []

    for i in range(0, len(archivos), config.chunk_size):
        lote = archivos[i : i + config.chunk_size]
        batch: list[pl.DataFrame] = []

        for path in lote:
            try:
                batch.append(procesar_archivo(path))
            except Exception as e:
                errores.append(f"{path.name}: {e}")

        if batch:
            chunks.append(pl.concat(batch, how="diagonal_relaxed"))
            print(f"  [{min(i + config.chunk_size, len(archivos)):3d}/{len(archivos)}] "
                  f"lote procesado ({len(batch)} archivos)")

    if errores:
        print(f"\nAdvertencia: {len(errores)} archivos con error:")
        for err in errores:
            print(f"  - {err}")

    if not chunks:
        raise RuntimeError("No se pudo procesar ningun archivo")

    df = pl.concat(chunks, how="diagonal_relaxed")
    print(f"\nFilas totales: {df.height:,}")

    print("Validando esquema...")
    validar_dataframe(df)

    print(f"Escribiendo {OUTPUT_FILE}...")
    df.write_parquet(OUTPUT_FILE, compression="zstd", statistics=True)

    metadata = generar_metadata(df, archivos=len(archivos) - len(errores))
    print(f"\nDataset curado guardado en {OUTPUT_FILE.resolve()}")
    print(f"  Filas:        {metadata.total_filas:,}")
    print(f"  Validas:      {metadata.filas_validas:,} "
          f"({metadata.filas_validas / metadata.total_filas * 100:.1f}%)")
    print(f"  Estaciones:   {len(metadata.estaciones)}")
    print(f"  Contaminantes: {metadata.contaminantes}")
    print(f"  Rango:        {metadata.fecha_min} -> {metadata.fecha_max}")
    print(f"  Tamano:       {OUTPUT_FILE.stat().st_size / 1_048_576:.1f} MB")

    return metadata


if __name__ == "__main__":
    ejecutar()
