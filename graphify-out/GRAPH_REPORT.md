# Graph Report - .  (2026-07-15)

## Corpus Check
- Corpus is ~5,180 words - fits in a single context window. You may not need a graph.

## Summary
- 86 nodes · 134 edges · 13 communities (10 shown, 3 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

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
2. `analizar_contaminante()` - 8 edges
3. `generar_html()` - 8 edges
4. `ejecutar_validacion()` - 8 edges
5. `ConfigPipeline` - 7 edges
6. `procesar_archivo()` - 7 edges
7. `ejecutar()` - 7 edges
8. `grafico_serie_temporal()` - 6 edges
9. `PruebaHipotesis` - 5 edges
10. `shapiro_test()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `shapiro_test()` --references--> `PruebaHipotesis`  [EXTRACTED]
  audit.py → audit.py  _Bridges community 4 → community 7_
- `AuditoriaReporte` --inherits--> `BaseModel`  [EXTRACTED]
  audit.py →   _Bridges community 4 → community 2_
- `ResultadoContaminante` --inherits--> `BaseModel`  [EXTRACTED]
  audit.py →   _Bridges community 4 → community 1_
- `analizar_contaminante()` --references--> `ResultadoContaminante`  [EXTRACTED]
  audit.py → audit.py  _Bridges community 1 → community 7_
- `grafico_boxplot_mensual()` --references--> `ResultadoContaminante`  [EXTRACTED]
  audit.py → audit.py  _Bridges community 1 → community 2_

## Import Cycles
- None detected.

## Communities (13 total, 3 thin omitted)

### Community 0 - "Great Expectations Suite"
Cohesion: 0.18
Nodes (16): Checkpoint, EphemeralDataContext, ExpectationSuite, cargar_dataset(), crear_contexto(), crear_suite(), ejecutar_validacion(), main() (+8 more)

### Community 1 - "Plotly Control Charts"
Cohesion: 0.21
Nodes (9): grafico_bell_curve(), grafico_serie_temporal(), Agrega las bandas de control 2-sigma y 3-sigma a la figura., Serie de tiempo con bandas de control, media y tendencia., Histograma con curva normal teorica y bandas sigma (bell curve)., Coeficiente de variacion., ResultadoContaminante, _trazas_control() (+1 more)

### Community 2 - "Audit HTML Generator"
Cohesion: 0.31
Nodes (9): AuditoriaReporte, generar_html(), grafico_boxplot_mensual(), main(), Auditoria de calidad de datos RAMA.  Genera cartas de control (estilo bell curve, Boxplots mensuales para detectar estacionalidad., HTML con tarjetas de metricas y pruebas de hipotesis., Construye la SPA HTML completa con navegacion por pestanas. (+1 more)

### Community 3 - "Pydantic Data Models"
Cohesion: 0.33
Nodes (5): Any, FilaRAMA, BaseModel, Una fila del dataset curado. Representa una medicion puntual., date

### Community 4 - "Hypothesis Testing"
Cohesion: 0.33
Nodes (7): anderson_darling_test(), mann_kendall_test(), PruebaHipotesis, BaseModel, Mann-Kendall: tendencia monotona., Anderson-Darling: normalidad., ndarray

### Community 5 - "Curation Validators"
Cohesion: 0.33
Nodes (3): Curacion de datos historicos RAMA (Red Automatica de Monitoreo Atmosferico).  Le, Valida que el DataFrame cumpla con el esquema esperado usando pydantic., validar_dataframe()

### Community 6 - "Curation Pipeline"
Cohesion: 0.40
Nodes (6): ejecutar(), generar_metadata(), MetadataRAMA, Genera metadata del dataset curado., Ejecuta el pipeline de curacion completo. Retorna metadata del resultado., Metadata del dataset curado.

### Community 7 - "Statistical Analysis"
Cohesion: 0.40
Nodes (5): analizar_contaminante(), DataFrame, Shapiro-Wilk: normalidad. Usa muestra aleatoria si n > 5000., Ejecuta el analisis completo para un contaminante., shapiro_test()

### Community 8 - "XLS Processing"
Cohesion: 0.50
Nodes (5): corregir_hora(), procesar_archivo(), DataFrame, HORA 24 se usa como medianoche del dia siguiente.     Convertimos HORA=24 -> hor, Lee un .xls, lo transforma a formato long (tidy) y reemplaza el sentinel.

### Community 10 - "File I/O & Extraction"
Cohesion: 0.50
Nodes (3): extraer_contaminante(), Extrae el codigo de contaminante del nombre de archivo (ej: 1986CO.xls -> CO)., Path

## Knowledge Gaps
- **2 isolated node(s):** `download_rama.sh script`, `rama-curation`
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `ResultadoContaminante` connect `Plotly Control Charts` to `Audit HTML Generator`, `Hypothesis Testing`, `Statistical Analysis`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Why does `FilaRAMA` connect `Pydantic Data Models` to `Curation Validators`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `ConfigPipeline` connect `Pipeline Config` to `File I/O & Extraction`, `Pydantic Data Models`, `Curation Validators`, `Curation Pipeline`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **What connects `download_rama.sh script`, `rama-curation` to the rest of the system?**
  _2 weakly-connected nodes found - possible documentation gaps or missing edges._