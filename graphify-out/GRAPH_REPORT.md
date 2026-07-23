# Graph Report - bookish-potato  (2026-07-22)

## Corpus Check
- 20 files · ~16,646 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 160 nodes · 215 edges · 13 communities (9 shown, 4 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `56532e4c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Great Expectations Suite
- Plotly Control Charts
- Audit HTML Generator
- Pydantic Data Models
- Hypothesis Testing
- Curation Validators
- Curation Pipeline
- Statistical Analysis
- XLS Processing
- Pipeline Config
- File I/O & Extraction
- Bash Downloader
- Package Root

## God Nodes (most connected - your core abstractions)
1. `ResultadoContaminante` - 11 edges
2. `Arquitectura Medallon SQL — RAMA (PostgreSQL)` - 11 edges
3. `RAMA — Datos historicos de calidad del aire (CDMX)` - 9 edges
4. `analizar_contaminante()` - 8 edges
5. `generar_html()` - 8 edges
6. `ejecutar_validacion()` - 8 edges
7. `ConfigPipeline` - 7 edges
8. `procesar_archivo()` - 7 edges
9. `ejecutar()` - 7 edges
10. `main()` - 7 edges

## Surprising Connections (you probably didn't know these)
- `ConfigPipeline` --inherits--> `BaseModel`  [EXTRACTED]
  curate.py →   _Bridges community 3 → community 5_

## Import Cycles
- None detected.

## Communities (13 total, 4 thin omitted)

### Community 0 - "Great Expectations Suite"
Cohesion: 0.18
Nodes (16): Checkpoint, EphemeralDataContext, ExpectationSuite, cargar_dataset(), crear_contexto(), crear_suite(), ejecutar_validacion(), main() (+8 more)

### Community 1 - "Plotly Control Charts"
Cohesion: 0.11
Nodes (30): analizar_contaminante(), anderson_darling_test(), AuditoriaReporte, generar_html(), grafico_bell_curve(), grafico_boxplot_mensual(), grafico_serie_temporal(), main() (+22 more)

### Community 2 - "Audit HTML Generator"
Cohesion: 0.10
Nodes (20): 1. Descargar datos, 2. Curar y consolidar, 3. Auditoria estadistica, 4. Validacion con Great Expectations, 5. Generar tabla agregada mensual, 6. Dashboard interactivo, 7. Catalogo de estaciones, API REST (+12 more)

### Community 3 - "Pydantic Data Models"
Cohesion: 0.33
Nodes (5): Any, FilaRAMA, BaseModel, Una fila del dataset curado. Representa una medicion puntual., date

### Community 4 - "Hypothesis Testing"
Cohesion: 0.11
Nodes (18): 10. Comparativa: SQL vs Python, 1. Diagrama de arquitectura, 2. Docker Compose, 3. Capa Bronze — `bronze.rama_horaria`, 4. Capa Silver — `silver.rama_horaria_validada`, 5. Capa Gold — `gold.rama_mensual_bi`, 6. Indices, 7. API (FastAPI + asyncpg) (+10 more)

### Community 5 - "Curation Validators"
Cohesion: 0.12
Nodes (19): ConfigPipeline, corregir_hora(), ejecutar(), extraer_contaminante(), generar_metadata(), MetadataRAMA, procesar_archivo(), DataFrame (+11 more)

### Community 6 - "Curation Pipeline"
Cohesion: 0.33
Nodes (11): export_bronze_csv(), load_bronze(), main(), psql_copy(), psql_file(), Path, Bootstrap: exporta datos horarios del Parquet a PostgreSQL y ejecuta las transfo, Ejecuta SQL via psql en el contenedor. (+3 more)

### Community 7 - "Statistical Analysis"
Cohesion: 0.33
Nodes (4): build_station_frame(), main(), DataFrame, Generate rama_mensual.parquet — BI-ready monthly exposure table for Looker Studi

### Community 9 - "Pipeline Config"
Cohesion: 0.47
Nodes (5): fetch_station_page(), main(), parse_station_info(), Scrape RAMA station coordinates from SEDEMA detail pages., Parse the station detail page. The table structure is:     <tr><th>Domicilio</th

## Knowledge Gaps
- **31 isolated node(s):** `download_rama.sh script`, `rama-curation`, `Datos`, `Estructura`, `1. Descargar datos` (+26 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What connects `download_rama.sh script`, `rama-curation`, `Datos` to the rest of the system?**
  _31 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Plotly Control Charts` be split into smaller, more focused modules?**
  _Cohesion score 0.10873440285204991 - nodes in this community are weakly interconnected._
- **Should `Audit HTML Generator` be split into smaller, more focused modules?**
  _Cohesion score 0.09523809523809523 - nodes in this community are weakly interconnected._
- **Should `Hypothesis Testing` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._
- **Should `Curation Validators` be split into smaller, more focused modules?**
  _Cohesion score 0.12333333333333334 - nodes in this community are weakly interconnected._