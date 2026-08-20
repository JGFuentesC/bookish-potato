# PRD — Plataforma GenBI de Fútbol ("Talk to your data")

| Campo | Valor |
|---|---|
| Versión | 1.0 |
| Fecha | 2026-08-19 |
| Estado | Aprobado para implementación |
| Tipo | POC (prueba de concepto) — 1 equipo, 1-2 sesiones de trabajo |
| Autor | Clase de Inteligencia de Negocio |
| Audiencia | Agente de IA implementador + equipo de desarrollo |
| Idioma | Documento en español; código, esquemas, tablas y columnas en inglés |

---

## 1. Resumen ejecutivo

Construir, desde cero y con modelos **estrictamente locales**, una plataforma de Generative BI sobre datos de fútbol de evento (StatsBomb Open Data / Hudl). El sistema entrega dos modos de consumo sobre el mismo modelo semántico:

1. **Tableros** — visualizaciones gobernadas sobre marts en esquema estrella.
2. **Chat con los datos** — un agente conversacional (Google ADK) que traduce lenguaje natural a consultas analíticas verificables y responde con tabla + gráfica + trazabilidad de la consulta ejecutada.

La cadena completa es: JSON crudo → **OLTP PostgreSQL 3NF (fuente de verdad)** → **bronze → silver → gold en Parquet consultado por DuckDB** → **capa semántica declarativa** → **agente ADK** → **API Go hexagonal** → **frontend React/TS**.

El diferenciador del proyecto no es el modelo de lenguaje —limitado a 8 GB de VRAM— sino la **arquitectura que compensa esa limitación**: capa semántica explícita, contratos Pydantic, validación y evaluación medible.

---

## 2. Objetivos y métricas de éxito

### 2.1 Objetivos

| ID | Objetivo |
|---|---|
| OBJ-1 | Demostrar end-to-end una arquitectura GenBI completa, sin servicios de nube ni APIs de pago |
| OBJ-2 | Ejercitar en un caso real los patrones canónicos de BI: 3NF, medallón, esquema estrella, capa semántica |
| OBJ-3 | Producir un chat sobre datos con respuestas **verificables**, no plausibles |
| OBJ-4 | Dejar una base de código que un agente de IA pueda extender sin arqueología |

### 2.2 No-objetivos (fuera de alcance explícito)

- Autenticación, autorización, multi-tenancy o gestión de usuarios.
- Ingesta en tiempo real, CDC o simulación de partido en vivo.
- Aplicación transaccional propia (notas de scouting, alertas, anotaciones).
- Modelos predictivos, xG propio, o entrenamiento/fine-tuning de modelos.
- Alta disponibilidad, backups, DR, hardening de producción.
- Aplicación móvil nativa.

### 2.3 Métricas de éxito de la POC

| ID | Métrica | Umbral de aceptación |
|---|---|---|
| MS-1 | Exactitud de ejecución (execution accuracy) sobre el golden set | ≥ 70 % |
| MS-2 | Tasa de consultas sintácticamente válidas al primer intento | ≥ 90 % |
| MS-3 | Latencia p95 de respuesta del chat (pregunta → tabla renderizada) | ≤ 15 s |
| MS-4 | Latencia p95 de carga del tablero | ≤ 2 s |
| MS-5 | Tasa de alucinación de entidades (métricas/dimensiones inexistentes) | 0 % (bloqueada por diseño) |
| MS-6 | Reproducibilidad: `make bootstrap && make demo` en máquina limpia | 1 comando, sin pasos manuales |
| MS-7 | Cobertura del subset crítico ingerido y validado | 100 % de partidos del subset |

---

## 3. Usuario y casos de uso

### 3.1 Persona

**Ana — Analista de BI genérica.** No sabe SQL avanzado ni conoce el esquema físico. Su lenguaje es de negocio ("goles esperados", "precisión de pase", "por temporada"). Necesita respuestas que pueda defender ante terceros: quiere ver la cifra **y** de dónde salió.

### 3.2 Casos de uso

| ID | Caso de uso | Pantalla |
|---|---|---|
| CU-1 | Revisar KPIs generales de una competición-temporada | Tablero |
| CU-2 | Comparar rendimiento entre equipos o jugadores | Tablero / Explorador |
| CU-3 | Construir una consulta ad-hoc eligiendo métricas, dimensiones y filtros | Explorador |
| CU-4 | Preguntar en lenguaje natural y obtener tabla + gráfica | Chat |
| CU-5 | Inspeccionar la consulta generada y el linaje de la métrica | Chat |
| CU-6 | Exportar el resultado a CSV | Explorador / Chat |

---

## 4. Alcance de datos

### 4.1 Fuente

**StatsBomb Open Data**, repositorio `https://github.com/hudl/open-data`.

Estructura relevante:

```
data/
├── competitions.json                       # catálogo de competición × temporada
├── matches/{competition_id}/{season_id}.json
├── lineups/{match_id}.json
├── events/{match_id}.json                  # ~3,000-4,000 eventos por partido
└── three-sixty/{match_id}.json             # freeze frames posicionales (subconjunto)
```

Volumen objetivo: **repositorio completo** (~3.5k partidos, ~12M eventos, incluyendo datos 360).

### 4.2 Licencia — requisito no negociable

Los datos se distribuyen bajo el **StatsBomb Open Data User Agreement** (uso no comercial, atribución obligatoria). El sistema **debe** mostrar la atribución a StatsBomb/Hudl en el pie de todas las pantallas y en `README.md`. El repositorio **no** versiona los datos: se descargan en `make data-pull`.

### 4.3 Estrategia de carga en dos vías (mitigación de riesgo)

| Vía | Contenido | Cuándo corre | Bloquea la demo |
|---|---|---|---|
| **Ruta crítica** | 1 competición-temporada determinista, fijada en `config/subset.yaml` | En el arranque del proyecto, minutos | Sí |
| **Carga completa** | Repositorio íntegro, incluyendo `three-sixty` | Job de fondo, idempotente, reanudable | No |

Toda transformación debe funcionar **idénticamente** sobre ambas vías. El subset se define por `competition_id`/`season_id`, nunca por muestreo aleatorio.

---

## 5. Arquitectura de solución

### 5.1 Vista de componentes

```
┌──────────────────────────────────────────────────────────────────────┐
│  Contenedor 1: app  (frontend + backend, un solo contenedor)         │
│  ┌────────────────────────┐        ┌──────────────────────────────┐  │
│  │ Frontend React+TS      │◄──────►│ Backend Go (hexagonal)       │  │
│  │ shadcn/ui · Tailwind   │  HTTP  │ dominio / puertos / adapters │  │
│  │ 3 pantallas            │        │ sirve el bundle estático     │  │
│  └────────────────────────┘        └──────────┬───────────────────┘  │
└───────────────────────────────────────────────┼──────────────────────┘
                                                │ HTTP interno
┌───────────────────────────────────────────────▼──────────────────────┐
│  Contenedor 2: ai-sidecar  (Python · FastAPI · Pydantic v2)          │
│  Agente Google ADK (single-agent + tools)                            │
│  Capa semántica · schema linking · validación · ejecución            │
└───────┬───────────────────────────────────┬──────────────────────────┘
        │                                   │
┌───────▼──────────┐              ┌─────────▼────────────┐   ┌─────────┐
│ Contenedor 3     │              │ Lakehouse (volumen)  │   │ platypy │
│ PostgreSQL 17    │  extracción  │ bronze/ silver/ gold │   │ Ollama  │
│ + pgvector       │─────────────►│ Parquet + DuckDB     │   │ LLM+emb │
│ OLTP 3NF         │              └──────────────────────┘   └─────────┘
└───────▲──────────┘                        ▲
        │ ingesta                           │ ELT Python (SQL en archivos)
┌───────┴───────────────────────────────────┴──────────────────────────┐
│  data-platform (Python · Pydantic · Makefile)                        │
│  JSON StatsBomb → OLTP → bronze → silver → gold                      │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 Flujo de datos (secuencial, unidireccional)

1. `make data-pull` — descarga el repositorio StatsBomb a `data/raw/`.
2. `make ingest` — valida cada JSON contra modelos **Pydantic** y lo carga normalizado en **PostgreSQL 3NF**. Idempotente por `match_id`.
3. `make bronze` — extrae las tablas OLTP a Parquet 1:1, sin transformar, con columnas de auditoría. Particionado por `competition_id/season_id`.
4. `make silver` — tipado, deduplicación, conformado, enriquecimiento derivado (zonas de cancha, distancias, secuencias de posesión).
5. `make gold` — construcción del esquema estrella (dimensiones + hechos + agregados).
6. `make serve` — levanta app, sidecar y base de datos.

**Regla de dirección**: ninguna capa lee de una capa posterior. La capa semántica lee **exclusivamente** de gold.

### 5.3 Arquitectura hexagonal (backend Go)

```
backend/internal/
├── domain/            # entidades y reglas. CERO imports de infraestructura
│   ├── model/         # Dashboard, QuerySpec, QueryResult, ChatTurn, SemanticEntity
│   └── errors/        # errores de dominio tipados
├── application/       # casos de uso; orquesta puertos
│   ├── port/
│   │   ├── inbound/   # DashboardService, ExplorerService, ChatService
│   │   └── outbound/  # AnalyticsRepository, SemanticCatalog, AgentGateway
│   └── usecase/
└── adapter/
    ├── inbound/http/  # handlers chi, DTOs, mapeo DTO↔dominio
    └── outbound/
        ├── duckdb/    # implementa AnalyticsRepository
        ├── sidecar/   # implementa AgentGateway (HTTP al sidecar)
        └── semantic/  # implementa SemanticCatalog (lee YAML)
```

**Regla de dependencia**: las flechas apuntan siempre hacia `domain`. Un test de arquitectura automatizado falla el build si `domain/` importa cualquier paquete de `adapter/`.

---

## 6. Modelo de datos

### 6.1 OLTP — PostgreSQL, 3NF, esquema `oltp`

**Catálogos** (tablas de referencia, carga previa):
`country`, `competition_stage`, `event_type`, `play_pattern`, `position`, `body_part`, `outcome`, `technique`, `pass_height`, `pass_type`, `shot_type`, `duel_type`, `goalkeeper_type`, `card_type`, `formation`.

**Entidades maestras**:

| Tabla | PK | Atributos principales |
|---|---|---|
| `competition` | `competition_id` | `competition_name`, `country_id`, `competition_gender`, `is_youth`, `is_international` |
| `season` | `season_id` | `season_name` |
| `competition_season` | (`competition_id`,`season_id`) | `match_updated`, `match_available` |
| `team` | `team_id` | `team_name`, `team_gender`, `country_id` |
| `player` | `player_id` | `player_name`, `player_nickname`, `country_id` |
| `manager` | `manager_id` | `name`, `nickname`, `date_of_birth`, `country_id` |
| `stadium` | `stadium_id` | `stadium_name`, `country_id` |
| `referee` | `referee_id` | `referee_name`, `country_id` |

**Transaccionales**:

| Tabla | PK | Notas |
|---|---|---|
| `match` | `match_id` | FKs a competición, temporada, equipos local/visitante, estadio, árbitro, etapa; `match_date`, `kick_off`, `home_score`, `away_score`, `match_week` |
| `match_manager` | (`match_id`,`team_id`,`manager_id`) | Técnico por partido y equipo |
| `match_player` | (`match_id`,`player_id`) | `team_id`, `jersey_number`, `country_id` |
| `match_player_position` | (`match_id`,`player_id`,`position_id`,`from_period`,`from_time`) | Posiciones con vigencia temporal |
| `match_player_card` | (`match_id`,`player_id`,`card_seq`) | Tarjetas con minuto y razón |
| `event` | `event_id` (UUID) | Tabla central. `match_id`, `index`, `period`, `timestamp`, `minute`, `second`, `type_id`, `possession`, `possession_team_id`, `play_pattern_id`, `team_id`, `player_id`, `position_id`, `location_x`, `location_y`, `duration`, `under_pressure`, `off_camera`, `out` |
| `event_relation` | (`event_id`,`related_event_id`) | Grafo de eventos relacionados |

**Especializaciones de evento** (una tabla por subtipo, FK 1:0..1 a `event`):
`event_pass`, `event_shot`, `event_dribble`, `event_carry`, `event_duel`, `event_goalkeeper`, `event_foul_committed`, `event_foul_won`, `event_interception`, `event_clearance`, `event_block`, `event_ball_receipt`, `event_miscontrol`, `event_substitution`, `event_bad_behaviour`, `event_50_50`, `event_half_start`, `event_player_off`.

**Posicionales**:

| Tabla | PK | Notas |
|---|---|---|
| `shot_freeze_frame` | (`event_id`,`frame_idx`) | `player_id`, `is_teammate`, `is_actor`, `is_keeper`, `x`, `y` |
| `tactics_lineup` | `event_id` | `formation_id` |
| `tactics_player` | (`event_id`,`player_id`) | `position_id`, `jersey_number` |
| `three_sixty_frame` | `event_id` | `visible_area` (JSONB — polígono) |
| `three_sixty_actor` | (`event_id`,`actor_idx`) | `is_teammate`, `is_actor`, `is_keeper`, `x`, `y` |

**Auditoría**:

| Tabla | Notas |
|---|---|
| `ingestion_run` | `run_id`, `started_at`, `finished_at`, `status`, `scope`, `files_processed`, `rows_written`, `error_summary` |
| `ingestion_file` | `run_id`, `source_path`, `file_sha256`, `entity`, `rows`, `status` — habilita reanudación e idempotencia |

**Índices obligatorios**: `event(match_id, index)`, `event(player_id)`, `event(team_id)`, `event(type_id)`, `match(competition_id, season_id)`, `match(match_date)`.

**Convenciones**: `snake_case`; timestamps `timestamptz`; coordenadas `numeric(6,2)` sobre cancha 120×80; toda FK con `ON DELETE RESTRICT`; sin borrados físicos.

### 6.2 Lakehouse — Parquet + DuckDB

Ruta física: `lakehouse/{layer}/{table}/competition_id=*/season_id=*/*.parquet`

| Capa | Contrato | Contenido |
|---|---|---|
| **bronze** | Copia fiel 1:1 de OLTP | Sin lógica de negocio. Columnas de auditoría: `_ingested_at`, `_source_table`, `_batch_id`, `_row_hash` |
| **silver** | Limpio, tipado, conformado | Deduplicación por clave natural; nulos normalizados; catálogos desnormalizados a texto; derivadas: `pitch_zone_x`, `pitch_zone_y`, `distance_to_goal`, `angle_to_goal`, `is_progressive_pass`, `possession_sequence_id`, `is_open_play` |
| **gold** | Esquema estrella | Dimensiones conformadas + hechos + agregados |

**Modelo gold (estrella)**

Dimensiones:

| Tabla | Grano | Notas |
|---|---|---|
| `dim_date` | día | Calendario generado, no derivado de los datos |
| `dim_player` | jugador | Con `country_name`, `primary_position` |
| `dim_team` | equipo | Con `country_name`, `team_gender` |
| `dim_competition_season` | competición × temporada | Clave surrogada `competition_season_key` |
| `dim_match` | partido | Degenerada: marcador, jornada, estadio, etapa |
| `dim_event_type` | tipo de evento | Jerarquía tipo → subtipo |
| `dim_position` | posición | Agrupación en líneas (portero/defensa/medio/ataque) |
| `dim_pitch_zone` | zona | Rejilla 6×5 sobre 120×80 |

Hechos:

| Tabla | Grano | Medidas |
|---|---|---|
| `fct_event` | 1 evento | `duration`, `location_x`, `location_y`, `under_pressure` |
| `fct_shot` | 1 tiro | `xg`, `is_goal`, `is_on_target`, `distance_to_goal`, `angle_to_goal` |
| `fct_pass` | 1 pase | `length`, `angle`, `is_complete`, `is_progressive`, `is_key_pass`, `is_assist` |
| `fct_player_match` | jugador × partido | `minutes_played`, `goals`, `assists`, `xg`, `shots`, `passes`, `passes_completed`, `pass_accuracy_pct`, `key_passes`, `dribbles_completed`, `duels_won`, `pressures`, `cards` |
| `fct_team_match` | equipo × partido | `goals_for`, `goals_against`, `xg_for`, `xg_against`, `possession_pct`, `shots`, `passes`, `pass_accuracy_pct`, `points`, `result` |
| `agg_player_season` | jugador × competición-temporada | Agregados de `fct_player_match` + tasas por 90 minutos |
| `agg_team_season` | equipo × competición-temporada | Tabla de posiciones derivada + tasas |

**Regla de granos**: ninguna métrica de la capa semántica puede mezclar hechos de distinto grano en una sola consulta sin pasar por un agregado explícito. El compilador debe rechazar esas combinaciones.

### 6.3 Contratos de datos (sustituyen a dbt)

Sin dbt, la gobernanza es explícita. Cada modelo del lakehouse tiene un archivo hermano:

```
data-platform/models/gold/fct_player_match.sql
data-platform/models/gold/fct_player_match.yaml   # contrato
```

El contrato YAML declara: `name`, `layer`, `grain`, `depends_on`, `columns` (nombre, tipo, nullable, descripción), `tests` (`not_null`, `unique`, `accepted_values`, `relationships`, `row_count_min`, `expression`). Se valida con un modelo **Pydantic** (`DataContract`) al arrancar el runner: contrato inválido = build detenido antes de tocar datos.

El runner Python resuelve el DAG desde `depends_on`, ejecuta en orden topológico, aplica los tests tras cada modelo y escribe el resultado en `ingestion_run`. Un test fallido en severidad `error` aborta la capa.


---

## 7. Capa semántica

Es el contrato entre el negocio y el almacén. **Nada consulta gold directamente**: ni el tablero, ni el explorador, ni el agente. Todo pasa por aquí.

### 7.1 Definición declarativa

Ubicación: `ai-sidecar/semantic/*.yaml`, versionado en git, validado con Pydantic (`SemanticModel`).

```yaml
version: 1
entity: player_performance
label: "Rendimiento de jugador"
description: "Métricas de jugador agregadas por partido"
base_table: gold.fct_player_match
grain: [player_key, match_key]
synonyms: ["jugador", "futbolista", "player", "rendimiento individual"]

joins:
  - to: dim_player
    on: "fct_player_match.player_key = dim_player.player_key"
    type: inner
  - to: dim_match
    on: "fct_player_match.match_key = dim_match.match_key"
    type: inner

dimensions:
  - name: player_name
    label: "Jugador"
    column: dim_player.player_name
    type: string
    synonyms: ["nombre del jugador", "quién"]
  - name: season_name
    label: "Temporada"
    column: dim_competition_season.season_name
    type: string
    synonyms: ["año", "campaña", "temporada"]

metrics:
  - name: goals
    label: "Goles"
    expression: "SUM(fct_player_match.goals)"
    type: additive
    format: integer
    synonyms: ["goles", "anotaciones", "dianas"]
  - name: xg
    label: "Goles esperados"
    expression: "SUM(fct_player_match.xg)"
    type: additive
    format: "0.00"
    synonyms: ["xg", "goles esperados", "expected goals"]
  - name: pass_accuracy_pct
    label: "Precisión de pase"
    expression: "100.0 * SUM(passes_completed) / NULLIF(SUM(passes),0)"
    type: ratio          # no aditiva: prohibido sumarla
    format: "0.0%"
    synonyms: ["precisión de pase", "porcentaje de pases completados"]

default_filters:
  - "fct_player_match.minutes_played > 0"
limits:
  max_rows: 5000
  requires_time_filter: false
```

### 7.2 Requisitos funcionales de la capa semántica

- Toda métrica declara su **tipo de agregación** (`additive`, `semi_additive`, `ratio`, `derived`). Las de tipo `ratio` nunca se suman: se recalculan al nivel de agregación pedido.
- Toda dimensión y métrica declara **sinónimos en español e inglés** — son el insumo del schema linking.
- La capa expone un **catálogo introspectivo** (`GET /semantic/catalog`) que alimenta simultáneamente el explorador ad-hoc y el prompt del agente. Una sola fuente, dos consumidores.
- El compilador aplica **límite de filas obligatorio** y rechaza cualquier expresión que no provenga del YAML.

---

## 8. Requisitos funcionales

### 8.1 Ingesta y OLTP

| ID | Requisito | Prioridad |
|---|---|---|
| RF-01 | Descargar el dataset StatsBomb a `data/raw/` mediante un comando, sin versionarlo en git | Debe |
| RF-02 | Validar cada archivo JSON contra modelos Pydantic antes de escribir en base de datos; los registros inválidos van a cuarentena con su motivo, sin abortar el lote | Debe |
| RF-03 | Cargar los datos normalizados en PostgreSQL 3NF respetando integridad referencial | Debe |
| RF-04 | La ingesta es idempotente: reejecutarla sobre los mismos archivos no duplica filas ni falla | Debe |
| RF-05 | La ingesta es reanudable: usa `ingestion_file.file_sha256` para saltar lo ya procesado | Debe |
| RF-06 | La ingesta corre en paralelo con grado configurable y reporta progreso | Debe |
| RF-07 | Cada corrida registra métricas de auditoría en `ingestion_run` | Debe |
| RF-08 | El alcance de ingesta es parametrizable (subset o completo) desde `config/subset.yaml` | Debe |
| RF-09 | Los datos 360 se ingieren en carga diferida, sin bloquear la ruta crítica | Puede |

### 8.2 Lakehouse

| ID | Requisito | Prioridad |
|---|---|---|
| RF-10 | Materializar bronze como copia fiel de OLTP en Parquet particionado, con columnas de auditoría | Debe |
| RF-11 | Materializar silver con tipado, deduplicación y columnas derivadas documentadas | Debe |
| RF-12 | Materializar gold en esquema estrella con las dimensiones y hechos de la sección 6.2 | Debe |
| RF-13 | Cada modelo tiene contrato YAML validado con Pydantic antes de ejecutarse | Debe |
| RF-14 | El runner resuelve dependencias en orden topológico y aborta la capa ante un test de severidad `error` | Debe |
| RF-15 | Cada modelo es reconstruible de forma aislada (`make model MODEL=fct_shot`) | Debe |
| RF-16 | Exponer un reporte de calidad de datos legible tras cada corrida | Debe |

### 8.3 Capa semántica y NLtoSQL

| ID | Requisito | Prioridad |
|---|---|---|
| RF-17 | Definir el modelo semántico en YAML versionado, validado con Pydantic al arranque | Debe |
| RF-18 | Exponer el catálogo semántico vía API para explorador y agente | Debe |
| RF-19 | Compilar una especificación de consulta validada a SQL de DuckDB, con `LIMIT` forzado | Debe |
| RF-20 | Rechazar toda consulta que referencie métricas, dimensiones o tablas ausentes del catálogo | Debe |
| RF-21 | Bloquear SQL no analítico: DDL, DML, múltiples sentencias, comentarios, `ATTACH`, acceso a archivos | Debe |
| RF-22 | Ejecutar sobre una conexión DuckDB de solo lectura, con timeout configurable | Debe |
| RF-23 | Realizar schema linking recuperando entidades candidatas por similitud semántica (embeddings en pgvector) y coincidencia léxica de sinónimos | Debe |
| RF-24 | Devolver, junto al resultado, la consulta ejecutada y las entidades semánticas usadas | Debe |
| RF-25 | Implementar un bucle de reparación acotado ante error de validación o ejecución (máx. 2 reintentos) | Debe |
| RF-26 | Mantener un golden set versionado de ≥ 40 preguntas con su resultado esperado | Debe |
| RF-27 | Ejecutar la evaluación por comando y publicar exactitud, validez, latencia y tasa de reparación | Debe |

> **La estrategia concreta de generación** (intención estructurada → compilador determinista, SQL directo validado, híbrido o recuperación de plantillas) **no se predefine**: es la salida del spike E3-H1, decidida con datos y firmada en `docs/adr/ADR-003-nl2sql-strategy.md`.

### 8.4 Agente conversacional

| ID | Requisito | Prioridad |
|---|---|---|
| RF-28 | Implementar un **único agente** Google ADK con herramientas explícitas | Debe |
| RF-29 | Herramientas mínimas: `search_semantic_catalog`, `run_analytical_query`, `suggest_chart`, `describe_metric` | Debe |
| RF-30 | Mantener sesión conversacional con memoria de turnos para permitir seguimiento ("¿y en la temporada anterior?") | Debe |
| RF-31 | Ante pregunta ambigua, repreguntar una sola vez con opciones concretas en lugar de adivinar | Debe |
| RF-32 | Declarar explícitamente cuando la pregunta no es respondible con el modelo semántico disponible | Debe |
| RF-33 | Proponer tipo de gráfica y mapeo de ejes a partir de la forma del resultado | Debe |
| RF-34 | Persistir la traza completa del turno: pregunta, herramientas invocadas, consulta, filas, latencia y tokens | Debe |
| RF-35 | Transmitir la respuesta al frontend en streaming | Puede |

### 8.5 Backend (Go)

| ID | Requisito | Prioridad |
|---|---|---|
| RF-36 | Exponer API REST versionada bajo `/api/v1` | Debe |
| RF-37 | `GET /api/v1/dashboard/:id` — definición y datos del tablero | Debe |
| RF-38 | `GET /api/v1/semantic/catalog` — catálogo para el explorador | Debe |
| RF-39 | `POST /api/v1/query` — ejecuta una especificación de consulta del explorador | Debe |
| RF-40 | `POST /api/v1/chat` — delega al sidecar y devuelve respuesta, consulta, datos y traza | Debe |
| RF-41 | `GET /api/v1/traces/:id` — recupera la traza de un turno | Debe |
| RF-42 | `GET /api/v1/export?format=csv` — exporta el resultado de una consulta | Debe |
| RF-43 | `GET /healthz` y `GET /readyz` — verifican DuckDB, sidecar y Ollama | Debe |
| RF-44 | Servir el bundle del frontend desde el mismo binario, con fallback SPA | Debe |
| RF-45 | Respetar la regla de dependencia hexagonal, verificada por test automatizado | Debe |

### 8.6 Frontend

| ID | Requisito | Prioridad |
|---|---|---|
| RF-46 | **Pantalla Tablero**: KPIs de cabecera, evolución temporal, ranking de jugadores, comparativa de equipos, mapa de tiros; filtro global por competición-temporada | Debe |
| RF-47 | **Pantalla Explorador**: selección de métricas, dimensiones y filtros desde el catálogo; resultado en tabla y gráfica; exportación a CSV | Debe |
| RF-48 | **Pantalla Chat**: conversación, respuesta en lenguaje natural, tabla, gráfica y panel plegable con la consulta ejecutada | Debe |
| RF-49 | Mostrar estados de carga, vacío y error con texto accionable, nunca genérico | Debe |
| RF-50 | Ofrecer preguntas sugeridas en el estado inicial del chat | Debe |
| RF-51 | Ser navegable por teclado, con foco visible y `prefers-reduced-motion` respetado | Debe |
| RF-52 | Ser responsivo hasta 375 px de ancho | Debe |
| RF-53 | Mostrar la atribución a StatsBomb/Hudl en el pie | Debe |

---

## 9. Requisitos no funcionales

| ID | Categoría | Requisito | Verificación |
|---|---|---|---|
| RNF-01 | Rendimiento | Tablero p95 ≤ 2 s con caché tibia | Prueba de carga con `k6` o `hey` |
| RNF-02 | Rendimiento | Consulta del explorador p95 ≤ 3 s sobre el subset | Medición instrumentada |
| RNF-03 | Rendimiento | Chat p95 ≤ 15 s de extremo a extremo | Suite de evaluación |
| RNF-04 | Rendimiento | Ingesta del subset ≤ 10 min con paralelismo 8 | Cronometrado en `ingestion_run` |
| RNF-05 | Local-first | Cero llamadas de red saliente en tiempo de ejecución salvo a Ollama en platypy | Revisión de código + prueba con red cortada |
| RNF-06 | Recursos | El LLM debe operar dentro de 8 GB de VRAM sin descarga a CPU | `ollama ps` durante la evaluación |
| RNF-07 | Seguridad | Solo lectura sobre el lakehouse; el usuario de DuckDB no puede escribir | Prueba negativa |
| RNF-08 | Seguridad | Toda entrada del usuario llega al motor como parámetro enlazado o identificador validado contra el catálogo; jamás por concatenación | Revisión + pruebas de inyección |
| RNF-09 | Seguridad | Sin autenticación por decisión de alcance; despliegue restringido a red local y documentado como tal | `README.md` |
| RNF-10 | Fiabilidad | Toda etapa del pipeline es idempotente y reanudable | Doble ejecución produce estado idéntico |
| RNF-11 | Observabilidad | Logs estructurados en JSON con `request_id` propagado entre Go, sidecar y Ollama | Inspección de logs |
| RNF-12 | Observabilidad | Trazas OpenTelemetry en frontera de servicio y en cada herramienta del agente | Colector local |
| RNF-13 | Mantenibilidad | Cobertura de pruebas ≥ 60 % en dominio Go y en compilador/validador del sidecar | Reporte de cobertura |
| RNF-14 | Mantenibilidad | Linters y formateadores en CI: `golangci-lint`, `ruff`, `mypy`, `eslint`, `prettier` | Pipeline |
| RNF-15 | Portabilidad | Todo levanta con `docker compose up` en Linux x86_64 con Docker ≥ 24 | Prueba en máquina limpia |
| RNF-16 | Reproducibilidad | Versiones fijadas: `go.mod`, `uv.lock`, `pnpm-lock.yaml`, tags de imagen | Revisión |
| RNF-17 | Calidad de datos | Cero violaciones de severidad `error` en gold | Reporte de calidad |
| RNF-18 | Usabilidad | Accesibilidad nivel AA en contraste y foco | `axe` en CI |
| RNF-19 | Legal | Atribución a StatsBomb/Hudl visible; sin uso comercial | Inspección visual |
| RNF-20 | Documentación | Cada ADR registra contexto, opciones, decisión y consecuencias | Revisión |

---

## 10. Stack técnico detallado

> Las versiones marcadas con `≥` se fijan exactas en E0-H1 y se registran en `docs/adr/ADR-001-stack-versions.md`. Ninguna versión se asume: se verifica contra el registro correspondiente antes de fijarla.

### 10.1 Datos

| Componente | Elección | Versión | Justificación |
|---|---|---|---|
| Base OLTP | PostgreSQL | ≥ 17 | Fuente de verdad, integridad referencial |
| Extensión vectorial | pgvector | ≥ 0.8 | Embeddings para schema linking |
| Migraciones | golang-migrate | ≥ 4.17 | SQL versionado, hacia adelante y atrás |
| Motor analítico | DuckDB | ≥ 1.1 | Columnar embebido, lectura directa de Parquet |
| Formato de lakehouse | Apache Parquet | — | Columnar, comprimido, particionable |
| Ingesta / ELT | Python | 3.12 | Ecosistema de datos |
| Gestor de paquetes | uv | ≥ 0.5 | Resolución determinista y rápida |
| Validación | Pydantic | v2 | Contratos de ingesta, modelos y capa semántica |
| Manipulación | Polars + PyArrow | ≥ 1.0 / ≥ 17 | Rendimiento sobre Parquet sin sobrecarga de pandas |
| Driver Postgres | psycopg | v3 | `COPY` binario para carga masiva |
| Orquestación | GNU Make | — | Decisión de alcance: sin orquestador |

### 10.2 IA

| Componente | Elección | Notas |
|---|---|---|
| Servidor de modelos | Ollama | Corre en platypy; expone API OpenAI-compatible |
| LLM | Gemma, variante instruida cuantizada Q4 que quepa en 8 GB | El tag exacto se **verifica en el registro de Ollama** durante E0-H3; si la variante objetivo no cabe en VRAM, se degrada al siguiente tamaño menor y se registra en ADR-002 |
| Embeddings | `gemma-embedding` o equivalente local | Se elige en el mismo spike, midiendo recall de schema linking |
| Framework de agente | Google ADK (Python) | Un solo agente con herramientas |
| API del sidecar | FastAPI | ≥ 0.115 |
| Contratos | Pydantic v2 | Entrada/salida de herramientas y del compilador |
| Cliente HTTP | httpx | Asíncrono, con timeouts explícitos |

### 10.3 Backend

| Componente | Elección | Notas |
|---|---|---|
| Lenguaje | Go ≥ 1.23 | Binario único que sirve API y frontend |
| Router | chi v5 | Ligero, middleware estándar |
| Driver Postgres | pgx v5 | Pool nativo |
| DuckDB | `marcboeker/go-duckdb` | Conexión de solo lectura |
| Configuración | Variables de entorno + `koanf` | Sin secretos en código |
| Logs | `log/slog` | JSON estructurado |
| Trazas | OpenTelemetry Go SDK | — |
| Pruebas | `testing` + `testify` + `testcontainers-go` | Integración real contra Postgres |

### 10.4 Frontend

| Componente | Elección | Notas |
|---|---|---|
| Framework | React 19 + TypeScript ≥ 5.6 | `strict: true`, sin `any` |
| Empaquetador | Vite ≥ 6 | — |
| Estilos | Tailwind CSS ≥ 4 | — |
| Componentes | **shadcn/ui** | Requisito del proyecto |
| Datos remotos | TanStack Query v5 | Caché y reintentos |
| Gráficas | Recharts ≥ 2.13 | Compatible con shadcn/ui charts |
| Estado de UI | Zustand | Solo estado local de interfaz |
| Formularios | react-hook-form + zod | Validación compartida con el catálogo |
| Pruebas | Vitest + Testing Library + Playwright | Unitarias y E2E |
| Mockups | **Google Stitch** | Insumo previo a la implementación |

### 10.5 Skills de diseño obligatorias

Las skills `emil-kowalski`, `impeccable` y `design-taste-frontend` residen en `~/.claude/skills/` y **deben copiarse al repositorio** en `.claude/skills/`, versionadas, para que el agente implementador las tenga disponibles. Rigen todo el trabajo de frontend: dirección tipográfica, movimiento, densidad y detalle de interacción.

### 10.6 Infraestructura

| Componente | Elección |
|---|---|
| Contenedores | Docker ≥ 24 + Docker Compose v2 |
| Contenedor `app` | Multi-stage: build de Vite → build de Go → imagen `distroless` final con frontend + backend |
| Contenedor `ai-sidecar` | Python 3.12 slim con uv |
| Contenedor `postgres` | `pgvector/pgvector:pg17` |
| Ollama | Externo, en platypy; alcanzable por red |
| Lakehouse | Volumen Docker montado en `app` y `ai-sidecar` en solo lectura |
| CI | GitHub Actions: lint, test, build de imágenes |

---

## 11. Estructura del repositorio

```
genbi-futbol/
├── .claude/
│   └── skills/
│       ├── emil-kowalski/
│       ├── impeccable/
│       └── design-taste-frontend/
├── docs/
│   ├── PRD.md
│   ├── adr/
│   │   ├── ADR-001-stack-versions.md
│   │   ├── ADR-002-local-model-selection.md
│   │   └── ADR-003-nl2sql-strategy.md
│   └── mockups/                       # exportaciones de Google Stitch
├── config/
│   └── subset.yaml                    # alcance determinista de la ruta crítica
├── data-platform/
│   ├── src/genbi_data/
│   │   ├── contracts/                 # modelos Pydantic (StatsBomb + DataContract)
│   │   ├── ingest/                    # descarga, validación, carga a OLTP
│   │   ├── runner/                    # DAG, ejecución de SQL, tests de calidad
│   │   └── quality/
│   ├── models/
│   │   ├── bronze/{*.sql,*.yaml}
│   │   ├── silver/{*.sql,*.yaml}
│   │   └── gold/{*.sql,*.yaml}
│   ├── migrations/                    # DDL de OLTP (golang-migrate)
│   └── tests/
├── ai-sidecar/
│   ├── src/genbi_ai/
│   │   ├── agent/                     # agente ADK + herramientas
│   │   ├── semantic/                  # carga y validación del modelo semántico
│   │   ├── compiler/                  # especificación → SQL
│   │   ├── guard/                     # validación y allow-list
│   │   ├── linking/                   # embeddings y recuperación de entidades
│   │   ├── eval/                      # golden set y arnés de evaluación
│   │   └── api/                       # FastAPI
│   ├── semantic/*.yaml
│   └── tests/
├── backend/
│   ├── cmd/server/main.go
│   ├── internal/{domain,application,adapter}/
│   └── tests/
├── frontend/
│   ├── src/{app,components,features,lib}/
│   └── tests/
├── infra/
│   ├── docker-compose.yml
│   └── Dockerfile.{app,sidecar}
├── scripts/
├── Makefile
└── README.md
```

---

## 12. Backlog

### 12.1 Convenciones del backlog

- **Jerarquía**: Épica → Historia → Tarea → Subtarea.
- **Estimación**: `S` ≤ 1 h · `M` 1-3 h · `L` 3-6 h · `XL` > 6 h (candidata a división).
- **Cada subtarea** indica archivo objetivo y **verificación ejecutable**. Una subtarea sin verificación no está terminada.
- **Definición de Hecho global (DoD-G)**, aplicable a toda historia:
  1. Código formateado y sin advertencias del linter del lenguaje.
  2. Pruebas nuevas que cubren los criterios de aceptación, en verde.
  3. Comando de verificación de cada subtarea ejecutado y con salida esperada.
  4. Sin secretos, rutas absolutas ni valores fijos que dependan de la máquina.
  5. Documentación tocada si la historia cambia contratos o comandos.
  6. La historia no rompe `make verify`.

### 12.2 Orden de ejecución

```
E0 ──► E1 ──► E2 ──┬──► E3 ──► E4 ──► E5 ──► E7
                   └──► E6 ─────────────────►
```

E6 puede arrancar en paralelo a E3 usando datos simulados contra el contrato de API, y se integra al cerrar E5.

---

## ÉPICA E0 — Fundaciones y entorno

**Objetivo**: que cualquiera clone el repositorio y levante el sistema vacío con un comando.

### E0-H1 — Andamiaje del monorepo y fijación de versiones

**Como** implementador, **quiero** una estructura de repositorio y versiones fijadas, **para** que ningún componente se desarrolle sobre supuestos distintos.

- Dependencias: ninguna · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Estructura completa
  Dado un clon limpio del repositorio
  Cuando ejecuto "make bootstrap"
  Entonces se instalan las dependencias de los cuatro módulos
  Y "make verify" termina con código de salida 0

Escenario: Versiones registradas
  Dado que las herramientas están instaladas
  Cuando abro "docs/adr/ADR-001-stack-versions.md"
  Entonces cada componente de la sección 10 aparece con su versión exacta verificada
```

**Tareas**

- **T1 — Crear el árbol de directorios de la sección 11**
  - T1.1 Generar todas las carpetas con `.gitkeep` donde estén vacías — verificación: `tree -L 2` coincide con la sección 11.
  - T1.2 `.gitignore` que excluya `data/raw/`, `lakehouse/`, `node_modules/`, `.venv/`, `dist/`, `*.duckdb` — verificación: `git status --porcelain` limpio tras una corrida de datos.
- **T2 — Copiar las skills de diseño**
  - T2.1 Copiar `~/.claude/skills/{emil-kowalski,impeccable,design-taste-frontend}` a `.claude/skills/` — verificación: los tres `SKILL.md` existen bajo `.claude/skills/`.
  - T2.2 Versionar las skills en git (no ignorarlas) — verificación: `git ls-files .claude/skills | wc -l` > 0.
- **T3 — Inicializar los módulos**
  - T3.1 `backend/go.mod` con módulo `github.com/<org>/genbi-futbol/backend` — verificación: `go build ./...` compila.
  - T3.2 `data-platform/pyproject.toml` y `ai-sidecar/pyproject.toml` con uv — verificación: `uv sync` genera `uv.lock` en ambos.
  - T3.3 `frontend/` con Vite + React + TS + Tailwind + shadcn/ui inicializado — verificación: `pnpm build` produce `dist/`.
- **T4 — Makefile raíz**
  - T4.1 Metas: `bootstrap`, `verify`, `lint`, `test`, `fmt`, `data-pull`, `ingest`, `bronze`, `silver`, `gold`, `serve`, `eval`, `demo`, `clean` — verificación: `make -n <meta>` no falla en ninguna.
  - T4.2 `make verify` encadena lint + test de los cuatro módulos — verificación: código de salida 0.
- **T5 — Registrar ADR-001**
  - T5.1 Verificar cada versión contra su registro oficial y escribirla en el ADR — verificación: ninguna celda del ADR dice "≥" ni "por definir".

**DoD**: DoD-G + `make bootstrap && make verify` funciona en máquina limpia.

---

### E0-H2 — Orquestación de contenedores

**Como** implementador, **quiero** levantar Postgres, sidecar y app con un comando, **para** eliminar la instalación manual.

- Dependencias: E0-H1 · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Arranque limpio
  Dado Docker en ejecución
  Cuando ejecuto "make serve"
  Entonces los contenedores app, ai-sidecar y postgres quedan saludables
  Y "GET /healthz" responde 200

Escenario: Persistencia
  Dado que ingerí datos previamente
  Cuando reinicio los contenedores
  Entonces los datos de Postgres y del lakehouse siguen presentes
```

**Tareas**

- **T1 — Compose**
  - T1.1 `infra/docker-compose.yml` con servicios `app`, `ai-sidecar`, `postgres`; volúmenes `pgdata` y `lakehouse`; red interna — verificación: `docker compose config` válido.
  - T1.2 Montar `lakehouse` en `app` y `ai-sidecar` como **solo lectura** — verificación: escribir dentro del contenedor falla con permiso denegado.
  - T1.3 `healthcheck` por servicio con `depends_on: condition: service_healthy` — verificación: `docker compose ps` muestra los tres saludables.
- **T2 — Imágenes**
  - T2.1 `infra/Dockerfile.app` multi-stage: Node → Go → distroless, con el bundle embebido — verificación: la imagen final pesa < 80 MB y sirve la SPA.
  - T2.2 `infra/Dockerfile.sidecar` sobre `python:3.12-slim` con uv — verificación: `uvicorn` arranca y `/health` responde.
- **T3 — Configuración**
  - T3.1 `.env.example` con `POSTGRES_*`, `OLLAMA_BASE_URL`, `LAKEHOUSE_PATH`, `SIDECAR_URL`, `QUERY_TIMEOUT_MS`, `MAX_ROWS` — verificación: arrancar sin `.env` produce un error claro que nombra la variable faltante.
  - T3.2 Documentar que Ollama es externo (platypy) y alcanzable por red — verificación: `README.md` lo indica.

**DoD**: DoD-G + `docker compose down && make serve` reproduce el estado saludable.

---

### E0-H3 — Verificación del modelo local en platypy

**Como** implementador, **quiero** confirmar qué modelo cabe realmente en 8 GB de VRAM, **para** no diseñar sobre una suposición.

- Dependencias: E0-H2 · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Modelo dentro del presupuesto de VRAM
  Dado Ollama corriendo en platypy con 8 GB de VRAM
  Cuando cargo el modelo candidato y ejecuto 20 generaciones de 512 tokens
  Entonces el modelo permanece completamente en GPU sin descarga a CPU
  Y la latencia mediana de primera respuesta es menor a 3 segundos

Escenario: Degradación registrada
  Dado que el modelo candidato no cabe en VRAM
  Cuando aplico la política de degradación
  Entonces se selecciona la siguiente variante menor
  Y ADR-002 documenta la evidencia de la medición
```

**Tareas**

- **T1 — Inventario de modelos disponibles**
  - T1.1 Consultar el registro de Ollama y listar variantes de Gemma instruidas con cuantización Q4, con su tamaño en disco — verificación: tabla en `docs/adr/ADR-002-local-model-selection.md`.
  - T1.2 Descargar la variante candidata y la de respaldo — verificación: `ollama list` las muestra.
- **T2 — Banco de pruebas**
  - T2.1 `scripts/bench_model.py`: mide VRAM ocupada, tokens/s, latencia de primer token y ventana de contexto efectiva — verificación: emite JSON con las métricas.
  - T2.2 Probar con un prompt representativo: catálogo semántico de ~40 entidades + pregunta — verificación: el prompt cabe en la ventana sin truncar.
- **T3 — Embeddings**
  - T3.1 Descargar el modelo de embeddings y medir dimensión y latencia por lote — verificación: métricas en el ADR.
  - T3.2 Confirmar que LLM y embeddings coexisten en VRAM o definir política de carga secuencial — verificación: `ollama ps` durante uso concurrente.
- **T4 — Cerrar ADR-002**
  - T4.1 Registrar modelo elegido, cuantización, parámetros de generación (`temperature=0`, `top_p`, `num_ctx`, `seed`) y evidencia — verificación: el ADR nombra un tag concreto de Ollama.

**DoD**: DoD-G + el tag del modelo queda fijado en `.env.example` y en ADR-002.

---

## ÉPICA E1 — Ingesta y base OLTP

### E1-H1 — Esquema OLTP 3NF y migraciones

**Como** ingeniero de datos, **quiero** un esquema normalizado con integridad referencial, **para** que el OLTP sea fuente de verdad confiable.

- Dependencias: E0-H2 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Migración hacia adelante
  Dado un Postgres vacío
  Cuando ejecuto "make migrate-up"
  Entonces existen todas las tablas de la sección 6.1 en el esquema oltp
  Y todas las claves foráneas están declaradas

Escenario: Reversión
  Dado un esquema migrado
  Cuando ejecuto "make migrate-down"
  Entonces el esquema oltp queda vacío sin errores

Escenario: Integridad
  Dado el esquema creado
  Cuando intento insertar un evento con un match_id inexistente
  Entonces la operación falla por violación de clave foránea
```

**Tareas**

- **T1 — Catálogos**
  - T1.1 `data-platform/migrations/0001_catalogs.up.sql` con las 15 tablas de referencia — verificación: `\dt oltp.*` las lista.
  - T1.2 Semilla de catálogos derivada del propio dataset — verificación: `SELECT count(*) FROM oltp.event_type` > 30.
- **T2 — Maestros y transaccionales**
  - T2.1 `0002_master.up.sql`: `country`, `competition`, `season`, `competition_season`, `team`, `player`, `manager`, `stadium`, `referee` — verificación: todas con PK y FK declaradas.
  - T2.2 `0003_match.up.sql`: `match`, `match_manager`, `match_player`, `match_player_position`, `match_player_card` — verificación: prueba negativa de FK falla como se espera.
  - T2.3 `0004_event.up.sql`: `event` y `event_relation` con PK UUID e índices de la sección 6.1 — verificación: `EXPLAIN` de filtro por `match_id` usa índice.
  - T2.4 `0005_event_subtypes.up.sql`: las 18 especializaciones — verificación: cada una con FK 1:0..1 a `event`.
  - T2.5 `0006_positional.up.sql`: `shot_freeze_frame`, `tactics_lineup`, `tactics_player`, `three_sixty_frame`, `three_sixty_actor` — verificación: tablas creadas.
- **T3 — Auditoría y vectores**
  - T3.1 `0007_audit.up.sql`: `ingestion_run`, `ingestion_file` — verificación: tablas creadas.
  - T3.2 `0008_pgvector.up.sql`: `CREATE EXTENSION vector` y tabla `semantic_embedding(entity_ref, kind, embedding vector(N))` — verificación: `SELECT * FROM pg_extension WHERE extname='vector'` devuelve fila.
- **T4 — Diagrama**
  - T4.1 Generar el diagrama entidad-relación a `docs/erd-oltp.md` en Mermaid — verificación: el diagrama renderiza y cubre todas las tablas.

**DoD**: DoD-G + `make migrate-up && make migrate-down && make migrate-up` sin errores.

---

### E1-H2 — Contratos Pydantic y descarga del dataset

**Como** ingeniero de datos, **quiero** modelar el formato StatsBomb con Pydantic, **para** detectar datos malformados antes de tocar la base.

- Dependencias: E0-H1 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Descarga acotada
  Dado el subset definido en config/subset.yaml
  Cuando ejecuto "make data-pull SCOPE=subset"
  Entonces se descargan solo los archivos de esa competición-temporada
  Y cada archivo queda registrado con su hash SHA-256

Escenario: Validación estricta
  Dado un archivo de eventos con un campo de tipo incorrecto
  Cuando lo valido contra el contrato
  Entonces el registro va a cuarentena con la ruta del campo y el motivo
  Y el resto del archivo se procesa
```

**Tareas**

- **T1 — Contratos**
  - T1.1 `contracts/statsbomb/competition.py`, `match.py`, `lineup.py` — verificación: validan las muestras reales sin error.
  - T1.2 `contracts/statsbomb/event.py`: modelo base + unión discriminada por `type.id` para los 18 subtipos — verificación: prueba parametrizada cubre cada subtipo con una muestra real.
  - T1.3 `contracts/statsbomb/three_sixty.py` — verificación: valida una muestra con `visible_area`.
  - T1.4 Configurar `model_config = ConfigDict(extra='forbid')` y registrar campos nuevos como fallo explícito — verificación: un campo desconocido produce error tipado, no silencio.
- **T2 — Descarga**
  - T2.1 `ingest/fetch.py`: clona o sincroniza el repositorio StatsBomb a `data/raw/` — verificación: `data/raw/data/competitions.json` existe.
  - T2.2 Soporte de `SCOPE=subset|full` leyendo `config/subset.yaml` — verificación: con `subset`, la cantidad de archivos de eventos coincide con los partidos declarados.
  - T2.3 Calcular y registrar SHA-256 por archivo — verificación: reejecutar no vuelve a descargar lo íntegro.
- **T3 — Cuarentena**
  - T3.1 `ingest/quarantine.py`: escribe `data/quarantine/{entity}/{file}.jsonl` con `error_path`, `error_type`, `raw_record` — verificación: al corromper una muestra, aparece la entrada correspondiente.

**DoD**: DoD-G + los contratos validan el 100 % de los archivos del subset.

---

### E1-H3 — Cargador paralelo e idempotente a OLTP

**Como** ingeniero de datos, **quiero** cargar los JSON validados en el OLTP de forma reanudable, **para** procesar miles de partidos sin reiniciar desde cero.

- Dependencias: E1-H1, E1-H2 · Estimación: XL

**Criterios de aceptación**

```gherkin
Escenario: Carga del subset
  Dado el subset descargado y validado
  Cuando ejecuto "make ingest SCOPE=subset"
  Entonces todos los partidos, alineaciones y eventos quedan en oltp
  Y ingestion_run registra estado "success" con el conteo de filas

Escenario: Idempotencia
  Dado un subset ya ingerido
  Cuando ejecuto "make ingest SCOPE=subset" de nuevo
  Entonces el conteo de filas de oltp.event no cambia
  Y los archivos ya procesados se omiten por hash

Escenario: Reanudación tras interrupción
  Dado que interrumpo la ingesta a la mitad
  Cuando la vuelvo a ejecutar
  Entonces continúa desde el primer archivo no confirmado
  Y no queda ninguna transacción parcial
```

**Tareas**

- **T1 — Núcleo de carga**
  - T1.1 `ingest/loader.py` con `COPY` binario de psycopg3 por tabla — verificación: cargar un partido tarda menos de 2 s.
  - T1.2 Resolución de entidades maestras con caché en memoria (`upsert` idempotente de `player`, `team`, `country`) — verificación: cero duplicados tras cargar 50 partidos.
  - T1.3 Transacción por archivo: confirma el partido completo o revierte todo — verificación: matar el proceso a media carga no deja eventos huérfanos.
- **T2 — Aplanado de eventos**
  - T2.1 `ingest/flatten.py`: separa el evento base de su especialización — verificación: `SELECT count(*) FROM oltp.event` iguala la suma de eventos del JSON.
  - T2.2 Poblar `event_relation` desde `related_events` — verificación: cada `related_event_id` existe en `event`.
  - T2.3 Poblar `shot_freeze_frame` y `tactics_*` — verificación: conteos coinciden con el JSON de origen.
- **T3 — Paralelismo**
  - T3.1 Pool de procesos con grado configurable (`INGEST_WORKERS`, por defecto 8) — verificación: el tiempo del subset se reduce de forma medible frente a grado 1.
  - T3.2 Barra de progreso y log estructurado por archivo — verificación: la salida muestra procesados/total.
  - T3.3 Ordenar la carga por dependencias (catálogos → maestros → partidos → eventos) — verificación: sin violaciones de FK con paralelismo activo.
- **T4 — Auditoría**
  - T4.1 Escribir `ingestion_run` e `ingestion_file` en cada corrida — verificación: consultar la tabla muestra la corrida con sus conteos.
  - T4.2 `make ingest-report` imprime resumen: archivos, filas, cuarentena, duración — verificación: salida legible.

**DoD**: DoD-G + doble ejecución produce conteos idénticos + RNF-04 medido.

---

### E1-H4 — Carga completa en segundo plano

**Como** implementador, **quiero** ingerir el repositorio íntegro sin bloquear la demo, **para** cumplir el alcance de datos sin arriesgar la sesión.

- Dependencias: E1-H3 · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Carga completa desatendida
  Dado el subset ya operativo
  Cuando lanzo "make ingest SCOPE=full" en segundo plano
  Entonces la ingesta avanza sin interrumpir las consultas al subset
  Y puede detenerse y reanudarse en cualquier momento

Escenario: Datos 360 diferidos
  Dado que la carga completa terminó con los eventos
  Cuando ejecuto "make ingest-360"
  Entonces se cargan three_sixty_frame y three_sixty_actor
  Y el resto del sistema sigue funcionando igual sin ellos
```

**Tareas**

- **T1 — Modo desatendido**
  - T1.1 Ejecutable con `nohup`, log rotado a `logs/ingest-full.log` — verificación: el proceso sobrevive al cierre de la terminal.
  - T1.2 Manejo de `SIGTERM` con confirmación del archivo en curso — verificación: detener y reanudar no pierde ni duplica.
- **T2 — Datos 360**
  - T2.1 Meta `ingest-360` independiente — verificación: corre por separado.
  - T2.2 Todas las consultas de silver y gold toleran ausencia de 360 — verificación: gold se construye sin esas tablas.

**DoD**: DoD-G + carga completa reanudable demostrada con una interrupción real.

---

## ÉPICA E2 — Medallón (bronze / silver / gold)

### E2-H1 — Runner de modelos con contratos y DAG

**Como** ingeniero de datos, **quiero** un ejecutor propio de modelos SQL con contratos y pruebas, **para** tener la gobernanza de dbt sin adoptar dbt.

- Dependencias: E1-H3 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Orden topológico
  Dado un conjunto de modelos con dependencias declaradas
  Cuando ejecuto "make gold"
  Entonces cada modelo se materializa después de sus dependencias
  Y el orden de ejecución queda en el log

Escenario: Contrato inválido detiene el build
  Dado un contrato YAML con un tipo de columna desconocido
  Cuando arranco el runner
  Entonces falla antes de ejecutar cualquier SQL
  Y el mensaje nombra el archivo y el campo inválido

Escenario: Prueba de calidad fallida
  Dado un modelo cuyo test not_null de severidad error falla
  Cuando el runner lo evalúa
  Entonces aborta la capa y devuelve código de salida distinto de cero

Escenario: Modelo aislado
  Dado el lakehouse construido
  Cuando ejecuto "make model MODEL=fct_shot"
  Entonces solo se reconstruye ese modelo
```

**Tareas**

- **T1 — Contrato de datos**
  - T1.1 `contracts/data_contract.py`: modelo Pydantic `DataContract` con `name`, `layer`, `grain`, `depends_on`, `columns`, `tests` — verificación: un YAML válido se carga y uno inválido lanza `ValidationError`.
  - T1.2 Validar todos los contratos al arranque, agregando errores en un solo reporte — verificación: con dos contratos rotos, se reportan ambos.
- **T2 — Motor**
  - T2.1 `runner/dag.py`: grafo desde `depends_on`, orden topológico, detección de ciclos — verificación: un ciclo artificial produce error explícito.
  - T2.2 `runner/execute.py`: ejecuta el `.sql` en DuckDB y materializa a Parquet particionado — verificación: aparecen archivos bajo `lakehouse/{layer}/{table}/`.
  - T2.3 Selector `--select` para un modelo, una capa o un modelo y sus dependientes — verificación: las tres formas funcionan.
- **T3 — Pruebas de calidad**
  - T3.1 `quality/tests.py` con `not_null`, `unique`, `accepted_values`, `relationships`, `row_count_min`, `expression` — verificación: prueba unitaria por cada tipo.
  - T3.2 Severidades `error` y `warn` con comportamiento distinto — verificación: `warn` registra y continúa; `error` aborta.
  - T3.3 Reporte a `lakehouse/_reports/quality-{run_id}.json` y resumen en consola — verificación: el archivo existe con el detalle por prueba.
- **T4 — Linaje**
  - T4.1 `make lineage` genera un diagrama Mermaid del DAG a `docs/lineage.md` — verificación: el diagrama incluye todos los modelos.

**DoD**: DoD-G + el runner corre las tres capas encadenadas con reporte de calidad.

---

### E2-H2 — Capa bronze

**Como** ingeniero de datos, **quiero** una copia fiel del OLTP en Parquet, **para** aislar el almacén analítico de la base transaccional.

- Dependencias: E2-H1 · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Fidelidad
  Dado el OLTP cargado con el subset
  Cuando ejecuto "make bronze"
  Entonces cada tabla de oltp tiene su Parquet en bronze con el mismo conteo de filas
  Y no hay ninguna transformación de negocio aplicada

Escenario: Auditoría y partición
  Dado bronze materializado
  Cuando inspecciono cualquier tabla particionable
  Entonces existen las columnas _ingested_at, _source_table, _batch_id y _row_hash
  Y los archivos están particionados por competition_id y season_id
```

**Tareas**

- **T1 — Extracción**
  - T1.1 `models/bronze/*.sql` leyendo Postgres desde DuckDB con la extensión `postgres` — verificación: `SELECT count(*)` coincide con OLTP tabla por tabla.
  - T1.2 Columnas de auditoría añadidas en la proyección — verificación: presentes en todas las tablas de bronze.
  - T1.3 Particionar `event` y sus subtipos por `competition_id/season_id` — verificación: la estructura de carpetas es la esperada.
- **T2 — Contratos**
  - T2.1 Un `.yaml` por tabla con `unique` sobre la PK y `not_null` sobre las FK — verificación: `make bronze` pasa todas las pruebas.

**DoD**: DoD-G + conteo de filas idéntico entre OLTP y bronze para las 40+ tablas.

---

### E2-H3 — Capa silver

**Como** ingeniero de datos, **quiero** datos limpios, conformados y enriquecidos, **para** que gold se construya sobre semántica estable.

- Dependencias: E2-H2 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Conformado
  Dado bronze materializado
  Cuando ejecuto "make silver"
  Entonces los identificadores de catálogo aparecen resueltos a su etiqueta de texto
  Y no hay filas duplicadas por clave natural

Escenario: Derivadas espaciales
  Dado silver materializado
  Cuando consulto silver.event
  Entonces existen pitch_zone_x, pitch_zone_y, distance_to_goal y angle_to_goal
  Y todas las coordenadas están dentro de los límites 0-120 y 0-80

Escenario: Secuencias de posesión
  Dado silver.event
  Cuando agrupo por possession_sequence_id
  Entonces cada secuencia pertenece a un solo partido y a una sola posesión
```

**Tareas**

- **T1 — Limpieza**
  - T1.1 `models/silver/event.sql`: tipado explícito, nulos normalizados, catálogos desnormalizados — verificación: `DESCRIBE` muestra los tipos esperados.
  - T1.2 Deduplicación por clave natural con `QUALIFY ROW_NUMBER()` — verificación: prueba `unique` en verde.
  - T1.3 `models/silver/match.sql`, `player.sql`, `team.sql`, `lineup.sql` — verificación: pruebas `relationships` en verde.
- **T2 — Enriquecimiento**
  - T2.1 Zonas de cancha: rejilla 6×5 sobre 120×80 — verificación: la distribución cubre las 30 zonas.
  - T2.2 `distance_to_goal` y `angle_to_goal` desde la portería rival — verificación: prueba contra tres casos calculados a mano.
  - T2.3 `is_progressive_pass` según regla documentada en el contrato — verificación: la regla está escrita en el YAML y hay prueba con casos límite.
  - T2.4 `possession_sequence_id` estable por partido y posesión — verificación: prueba `unique` sobre (`match_id`,`possession`).
  - T2.5 `minutes_played` por jugador y partido desde alineaciones y sustituciones — verificación: la suma por equipo y partido es coherente con 11 jugadores en cancha.
- **T3 — Contratos**
  - T3.1 Contrato por modelo con pruebas de rango sobre coordenadas y porcentajes — verificación: `make silver` en verde.

**DoD**: DoD-G + cero violaciones de severidad `error` en silver.

---

### E2-H4 — Capa gold (esquema estrella)

**Como** analista, **quiero** un esquema estrella con hechos y agregados, **para** que las consultas sean simples, rápidas y consistentes.

- Dependencias: E2-H3 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Estrella completa
  Dado silver materializado
  Cuando ejecuto "make gold"
  Entonces existen las 8 dimensiones y los 7 hechos de la sección 6.2
  Y toda clave foránea de un hecho resuelve contra su dimensión

Escenario: Consistencia de agregados
  Dado gold materializado
  Cuando comparo la suma de goles de fct_player_match contra fct_team_match
  Entonces ambas cifras coinciden para toda competición-temporada

Escenario: Métricas no aditivas
  Dado agg_player_season
  Cuando comparo pass_accuracy_pct con el recálculo desde los totales
  Entonces coinciden, es decir la razón no se promedió
```

**Tareas**

- **T1 — Dimensiones**
  - T1.1 `dim_date` generada por calendario, no derivada de los datos — verificación: cubre el rango completo sin huecos.
  - T1.2 `dim_player`, `dim_team`, `dim_competition_season`, `dim_match`, `dim_event_type`, `dim_position`, `dim_pitch_zone` con clave surrogada — verificación: prueba `unique` por dimensión.
  - T1.3 Miembro desconocido (`-1`) en cada dimensión para hechos sin correspondencia — verificación: ningún hecho tiene FK nula.
- **T2 — Hechos**
  - T2.1 `fct_event`, `fct_shot`, `fct_pass` — verificación: conteos coinciden con silver filtrado por tipo.
  - T2.2 `fct_player_match` con las 13 medidas de la sección 6.2 — verificación: cotejo manual de un partido conocido.
  - T2.3 `fct_team_match` con posesión, puntos y resultado — verificación: los puntos suman correctamente por temporada.
- **T3 — Agregados**
  - T3.1 `agg_player_season` con tasas por 90 minutos — verificación: recálculo desde `fct_player_match` coincide.
  - T3.2 `agg_team_season` con tabla de posiciones derivada — verificación: la clasificación reproduce el orden real de la temporada del subset.
- **T4 — Rendimiento**
  - T4.1 Ordenar los Parquet por las claves de filtrado más frecuentes y ajustar tamaño de grupo de filas — verificación: consulta de tablero por debajo de 500 ms.

**DoD**: DoD-G + los tres escenarios de consistencia verificados + reporte de calidad sin errores.

---

## ÉPICA E3 — Capa semántica y NLtoSQL

### E3-H1 — Spike: exploración de datos y decisión de estrategia NLtoSQL

**Como** equipo, **queremos** decidir la estrategia de generación de consultas con evidencia y no por intuición, **para** elegir la que mejor rinda con un modelo de 8 GB.

- Dependencias: E2-H4 · Estimación: L
- **Compuerta de decisión: ninguna historia posterior de E3 arranca sin ADR-003 firmado.**

**Criterios de aceptación**

```gherkin
Escenario: Exploración documentada
  Dado gold materializado
  Cuando ejecuto el cuaderno de exploración
  Entonces se documentan cardinalidades, cobertura, sesgos y huecos por dimensión
  Y se listan las preguntas que los datos sí pueden responder

Escenario: Comparación de estrategias
  Dado un conjunto de 15 preguntas piloto
  Cuando evalúo las cuatro estrategias candidatas con el modelo local
  Entonces obtengo exactitud de ejecución, validez sintáctica y latencia por estrategia
  Y los resultados quedan en una tabla comparativa

Escenario: Decisión firmada
  Dado los resultados de la comparación
  Cuando escribo ADR-003
  Entonces la decisión cita las cifras medidas
  Y enumera las consecuencias y el plan de reversión
```

**Tareas**

- **T1 — Exploración**
  - T1.1 `ai-sidecar/notebooks/01_data_exploration.py` sobre gold: perfilado de cardinalidades, nulos, rangos y distribución por competición — verificación: informe en `docs/data-profile.md`.
  - T1.2 Inventario de preguntas de negocio respondibles, clasificadas por dificultad (agregación simple, filtro temporal, comparación, ranking, razón, multi-grano) — verificación: ≥ 60 preguntas listadas.
  - T1.3 Identificar los huecos: qué preguntas naturales **no** son respondibles y por qué — verificación: sección explícita en el informe.
- **T2 — Prototipos de las cuatro estrategias**
  - T2.1 Estrategia A: intención estructurada Pydantic → compilador determinista — verificación: prototipo responde las 15 preguntas piloto.
  - T2.2 Estrategia B: SQL directo + validación de AST y allow-list + reparación — verificación: ídem.
  - T2.3 Estrategia C: híbrida, intención estructurada con degradación a SQL libre — verificación: ídem.
  - T2.4 Estrategia D: recuperación de plantillas parametrizadas por similitud — verificación: ídem.
- **T3 — Medición**
  - T3.1 Arnés común que ejecuta las cuatro con el mismo modelo y el mismo prompt base — verificación: salida comparable en un solo JSON.
  - T3.2 Métricas: exactitud de ejecución, validez al primer intento, latencia p50/p95, tasa de reparación, tokens por consulta — verificación: tabla en el ADR.
- **T4 — ADR-003**
  - T4.1 Escribir contexto, opciones, evidencia, decisión, consecuencias y criterio de reversión — verificación: el ADR nombra una estrategia ganadora y su umbral de fallo.

**DoD**: DoD-G + ADR-003 firmado + prototipo ganador promovido a rama de trabajo.

---

### E3-H2 — Modelo semántico y catálogo

**Como** analista, **quiero** un modelo semántico declarativo, **para** que tableros, explorador y chat hablen del mismo negocio.

- Dependencias: E3-H1 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Carga y validación
  Dado el modelo semántico en YAML
  Cuando arranca el sidecar
  Entonces todas las entidades, dimensiones y métricas se validan con Pydantic
  Y una expresión que referencia una columna inexistente en gold impide el arranque

Escenario: Catálogo expuesto
  Dado el sidecar en ejecución
  Cuando consulto GET /semantic/catalog
  Entonces recibo entidades, dimensiones, métricas, tipos, formatos y sinónimos
  Y ninguna expresión SQL interna se filtra al cliente

Escenario: Métricas de razón protegidas
  Dado una métrica declarada como ratio
  Cuando pido agregarla a un nivel superior
  Entonces se recalcula desde sus componentes y no se promedia
```

**Tareas**

- **T1 — Modelos Pydantic**
  - T1.1 `semantic/models.py`: `SemanticModel`, `Entity`, `Dimension`, `Metric`, `Join`, `Limits` — verificación: prueba de carga con YAML válido e inválido.
  - T1.2 Validador cruzado contra el esquema real de gold vía DuckDB — verificación: columna inexistente produce error nombrando entidad y columna.
- **T2 — Definiciones**
  - T2.1 `semantic/player_performance.yaml` — verificación: ≥ 12 métricas y ≥ 8 dimensiones.
  - T2.2 `semantic/team_performance.yaml` — verificación: ídem.
  - T2.3 `semantic/shot_analysis.yaml` y `semantic/pass_analysis.yaml` — verificación: incluyen dimensiones espaciales.
  - T2.4 Sinónimos en español e inglés para cada métrica y dimensión — verificación: ninguna entrada sin sinónimos.
- **T3 — Catálogo**
  - T3.1 `GET /semantic/catalog` con proyección segura (sin expresiones SQL) — verificación: la respuesta no contiene la palabra `SUM`.
  - T3.2 `GET /semantic/metric/{name}` con definición legible y linaje hasta el modelo gold — verificación: devuelve la cadena de dependencias.

**DoD**: DoD-G + el catálogo alimenta explorador y agente sin duplicar definiciones.

---

### E3-H3 — Compilador, guardas y ejecución

**Como** responsable del sistema, **quiero** que ninguna consulta llegue al motor sin validarse, **para** que el chat sea seguro y verificable.

- Dependencias: E3-H2 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Compilación válida
  Dado una especificación con métricas y dimensiones del catálogo
  Cuando la compilo
  Entonces obtengo SQL de DuckDB con LIMIT aplicado
  Y los joins provienen exclusivamente de las relaciones declaradas

Escenario: Entidad inexistente
  Dado una especificación que pide la métrica "goles_de_cabeza_en_lluvia"
  Cuando la compilo
  Entonces falla con un error que dice que la métrica no existe
  Y sugiere las tres métricas más cercanas del catálogo

Escenario: Intento de escritura
  Dado una consulta que contiene DROP, INSERT, ATTACH o COPY
  Cuando pasa por las guardas
  Entonces se rechaza antes de ejecutarse

Escenario: Mezcla de granos
  Dado una especificación que combina fct_shot y fct_player_match sin agregado
  Cuando la compilo
  Entonces se rechaza indicando el conflicto de grano

Escenario: Tiempo límite
  Dado una consulta que excede el timeout configurado
  Cuando se ejecuta
  Entonces se cancela y se devuelve un error accionable
```

**Tareas**

- **T1 — Especificación de consulta**
  - T1.1 `compiler/spec.py`: `QuerySpec` Pydantic con `entity`, `metrics`, `dimensions`, `filters`, `order_by`, `limit`, `time_range` — verificación: rechaza campos desconocidos.
  - T1.2 Filtros tipados por operador (`eq`, `in`, `between`, `gte`, `lte`, `contains`) — verificación: prueba por operador.
- **T2 — Compilador**
  - T2.1 `compiler/build.py`: resuelve joins mínimos necesarios, agrupa por dimensiones y aplica métricas — verificación: SQL generado esperado en pruebas doradas.
  - T2.2 Recalculo correcto de métricas `ratio` al nivel pedido — verificación: prueba comparando contra cálculo manual.
  - T2.3 Detección de conflicto de granos — verificación: escenario de aceptación en verde.
  - T2.4 `LIMIT` forzado según `limits.max_rows` — verificación: no hay ruta que emita SQL sin `LIMIT`.
- **T3 — Guardas**
  - T3.1 `guard/validate.py`: análisis del SQL con `sqlglot`; solo se permite un `SELECT`; sin DDL, DML, múltiples sentencias ni comentarios — verificación: batería de 20 cadenas maliciosas, todas rechazadas.
  - T3.2 Allow-list de tablas y columnas derivada del catálogo — verificación: referenciar `oltp.player` se rechaza.
  - T3.3 Prohibir funciones de acceso a sistema de archivos y `ATTACH` — verificación: prueba negativa.
- **T4 — Ejecución**
  - T4.1 `executor/duckdb.py`: conexión de solo lectura, timeout, límite de memoria — verificación: escribir falla; consulta larga se cancela.
  - T4.2 Resultado tipado `QueryResult` con columnas, filas, SQL ejecutado, duración y entidades usadas — verificación: contrato Pydantic validado en prueba.
  - T4.3 Parámetros enlazados para todo valor de filtro proveniente del usuario — verificación: prueba de inyección con comilla simple no altera la consulta.

**DoD**: DoD-G + suite de seguridad completa en verde + cobertura ≥ 60 % en compilador y guardas.

---

### E3-H4 — Schema linking, golden set y evaluación

**Como** equipo, **queremos** medir la calidad del NLtoSQL de forma continua, **para** que las mejoras sean demostrables y no anecdóticas.

- Dependencias: E3-H3 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Recuperación de entidades relevantes
  Dado la pregunta "quién generó más goles esperados en la liga"
  Cuando ejecuto el schema linking
  Entonces las métricas y dimensiones correctas aparecen entre las cinco primeras candidatas

Escenario: Evaluación reproducible
  Dado el golden set versionado
  Cuando ejecuto "make eval"
  Entonces obtengo exactitud de ejecución, validez, latencia p50 y p95 y tasa de reparación
  Y el reporte se guarda con fecha y versión del modelo

Escenario: Umbral de aceptación
  Dado el reporte de evaluación
  Cuando la exactitud de ejecución baja del 70 por ciento
  Entonces "make eval" devuelve código de salida distinto de cero
```

**Tareas**

- **T1 — Embeddings**
  - T1.1 `linking/embed.py`: genera embeddings de nombres, etiquetas, descripciones y sinónimos hacia `semantic_embedding` en pgvector — verificación: conteo de vectores igual al de entidades semánticas.
  - T1.2 Índice HNSW y consulta de similitud coseno con `k` configurable — verificación: `EXPLAIN` usa el índice.
  - T1.3 Recuperación híbrida: similitud vectorial combinada con coincidencia léxica de sinónimos — verificación: mejora medible de recall frente a solo vectorial.
- **T2 — Golden set**
  - T2.1 `eval/golden_set.yaml` con ≥ 40 preguntas: pregunta, especificación esperada, resultado esperado y dificultad — verificación: todas ejecutan contra el subset.
  - T2.2 Distribución por dificultad: 10 agregación simple, 10 filtro temporal, 8 comparación, 6 ranking, 4 métricas de razón, 2 ambiguas que deben provocar repregunta — verificación: conteo por categoría.
- **T3 — Arnés**
  - T3.1 `eval/run.py`: ejecuta el golden set, compara resultados por conjunto de filas normalizado — verificación: informe JSON + Markdown.
  - T3.2 Métricas de MS-1, MS-2, MS-3 y tasa de reparación — verificación: presentes en el informe.
  - T3.3 Umbral configurable que hace fallar el comando — verificación: bajar el umbral artificialmente lo hace pasar y subirlo lo hace fallar.
- **T4 — Bucle de reparación**
  - T4.1 Ante error de validación o ejecución, reintento con el mensaje de error como contexto, máximo 2 — verificación: contador de reparaciones en la traza.
  - T4.2 Tras agotar reintentos, respuesta explícita de imposibilidad, sin inventar cifras — verificación: prueba con pregunta no respondible.

**DoD**: DoD-G + `make eval` produce un informe que cumple MS-1, MS-2 y MS-3.

---

## ÉPICA E4 — Agente conversacional (Google ADK)

### E4-H1 — Sidecar FastAPI y contratos de servicio

**Como** backend, **quiero** un contrato estable con el sidecar de IA, **para** que Go y Python evolucionen sin acoplarse.

- Dependencias: E3-H3 · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Contrato publicado
  Dado el sidecar en ejecución
  Cuando consulto /openapi.json
  Entonces el esquema describe /chat, /query, /semantic/catalog y /health
  Y todos los cuerpos de petición y respuesta son modelos Pydantic

Escenario: Salud dependiente
  Dado que Ollama está caído
  Cuando consulto GET /health
  Entonces la respuesta es 503 e indica cuál dependencia falla
```

**Tareas**

- **T1 — Aplicación**
  - T1.1 `api/main.py` con FastAPI, ciclo de vida que carga y valida el modelo semántico al arrancar — verificación: modelo semántico inválido impide el arranque.
  - T1.2 Middleware de `request_id` propagado desde la cabecera `X-Request-ID` — verificación: el identificador aparece en todos los logs del turno.
  - T1.3 Manejo global de errores con cuerpo tipado `ErrorResponse` — verificación: excepción no controlada devuelve 500 con estructura estable.
- **T2 — Endpoints**
  - T2.1 `POST /chat` con `ChatRequest`/`ChatResponse` — verificación: prueba de contrato.
  - T2.2 `POST /query` que ejecuta un `QuerySpec` del explorador — verificación: prueba de contrato.
  - T2.3 `GET /health` verificando DuckDB, Postgres y Ollama — verificación: escenario de aceptación.
- **T3 — Cliente de Ollama**
  - T3.1 `llm/ollama.py` con httpx asíncrono, timeouts explícitos y reintentos con retroceso — verificación: prueba con servidor simulado que falla y se recupera.
  - T3.2 Parámetros de generación deterministas fijados desde ADR-002 — verificación: dos ejecuciones con la misma entrada producen la misma salida.

**DoD**: DoD-G + contrato OpenAPI congelado y consumido por Go.

---

### E4-H2 — Agente único con herramientas

**Como** analista, **quiero** preguntar en lenguaje natural, **para** obtener respuestas sin escribir SQL.

- Dependencias: E4-H1, E3-H4 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Pregunta directa
  Dado el agente en ejecución
  Cuando pregunto "¿quién marcó más goles en la temporada?"
  Entonces el agente invoca search_semantic_catalog y run_analytical_query
  Y responde con una tabla ordenada y una frase que cita la cifra principal

Escenario: Seguimiento con contexto
  Dado que acabo de preguntar por goles de un equipo
  Cuando pregunto "¿y los goles esperados?"
  Entonces el agente conserva el equipo y la temporada del turno anterior

Escenario: Ambigüedad
  Dado la pregunta "compara a los dos mejores"
  Cuando el agente no puede resolver el criterio de "mejor"
  Entonces repregunta una sola vez ofreciendo opciones concretas del catálogo

Escenario: Fuera de alcance
  Dado la pregunta "¿cuánto cuesta el pase de este jugador?"
  Cuando el catálogo no tiene métricas de mercado
  Entonces el agente declara que no puede responder con los datos disponibles
  Y no inventa ninguna cifra
```

**Tareas**

- **T1 — Definición del agente**
  - T1.1 `agent/root_agent.py`: agente ADK único, modelo apuntando a Ollama, instrucción de sistema versionada en `agent/prompts/system.md` — verificación: el agente arranca y responde a un saludo.
  - T1.2 Instrucción que prohíbe explícitamente inventar métricas y exige usar el catálogo — verificación: escenario "fuera de alcance" en verde.
  - T1.3 Presupuesto de contexto: el catálogo se inyecta recortado por schema linking, nunca completo — verificación: el prompt no supera el `num_ctx` fijado.
- **T2 — Herramientas**
  - T2.1 `search_semantic_catalog(question)` → entidades candidatas ordenadas — verificación: prueba con 10 preguntas del golden set.
  - T2.2 `run_analytical_query(spec)` → `QueryResult`, pasando por compilador y guardas — verificación: no existe ruta que evada las guardas.
  - T2.3 `describe_metric(name)` → definición, fórmula legible y linaje — verificación: devuelve texto sin SQL crudo.
  - T2.4 `suggest_chart(result)` → tipo de gráfica y mapeo de ejes según cardinalidad y tipos — verificación: matriz de casos (1 dimensión + 1 métrica, temporal, 2 métricas, alta cardinalidad).
- **T3 — Sesión**
  - T3.1 Servicio de sesión ADK con memoria de los últimos N turnos, N configurable — verificación: escenario de seguimiento en verde.
  - T3.2 Resolución de referencias anafóricas por reescritura de la pregunta con el contexto previo — verificación: prueba con tres turnos encadenados.
- **T4 — Redacción de la respuesta**
  - T4.1 La respuesta en lenguaje natural se genera **a partir de las filas devueltas**, nunca de memoria del modelo — verificación: prueba que altera las filas y comprueba que la frase cambia en consecuencia.
  - T4.2 Formateo de cifras según el `format` declarado en la métrica — verificación: porcentajes y decimales correctos.

**DoD**: DoD-G + los cuatro escenarios de aceptación en verde + MS-5 igual a 0 %.

---

### E4-H3 — Trazabilidad del turno

**Como** analista, **quiero** ver de dónde salió cada cifra, **para** poder defenderla.

- Dependencias: E4-H2 · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Traza completa
  Dado un turno de chat respondido
  Cuando consulto la traza de ese turno
  Entonces incluye pregunta, entidades recuperadas, herramientas invocadas, SQL ejecutado, número de filas, duración y tokens

Escenario: Recuperación posterior
  Dado un identificador de traza
  Cuando lo consulto por API
  Entonces recibo la traza persistida aunque la sesión haya terminado
```

**Tareas**

- **T1 — Persistencia**
  - T1.1 Tabla `oltp.agent_trace` con `trace_id`, `session_id`, `turn_index`, `question`, `payload` JSONB, `latency_ms`, `created_at` — verificación: migración aplicada.
  - T1.2 Escritura de la traza al cerrar cada turno, sin bloquear la respuesta — verificación: la latencia del turno no aumenta de forma medible.
- **T2 — Exposición**
  - T2.1 `GET /traces/{trace_id}` en el sidecar — verificación: devuelve la traza completa.
  - T2.2 Redacción de la traza en formato apto para la interfaz, separando SQL, entidades y tiempos — verificación: contrato Pydantic.

**DoD**: DoD-G + toda respuesta del chat incluye un `trace_id` recuperable.

---

## ÉPICA E5 — Backend Go hexagonal

### E5-H1 — Esqueleto hexagonal y salud

**Como** implementador, **quiero** la separación estricta de capas verificada por prueba, **para** que la arquitectura no se erosione.

- Dependencias: E0-H2 · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Regla de dependencia
  Dado el paquete internal/domain
  Cuando ejecuto la prueba de arquitectura
  Entonces se confirma que domain no importa ningún paquete de adapter ni librería de infraestructura
  Y la prueba falla si alguien introduce esa importación

Escenario: Salud y disponibilidad
  Dado el servidor en ejecución
  Cuando consulto /healthz y /readyz
  Entonces /healthz responde 200 siempre que el proceso viva
  Y /readyz responde 503 si DuckDB, el sidecar u Ollama no responden
```

**Tareas**

- **T1 — Capas**
  - T1.1 `internal/domain/model` con `QuerySpec`, `QueryResult`, `Dashboard`, `ChatTurn`, `SemanticEntity` — verificación: el paquete compila sin dependencias externas.
  - T1.2 `internal/domain/errors` con errores tipados y mapeo a códigos HTTP en el adaptador — verificación: prueba de mapeo.
  - T1.3 `internal/application/port/{inbound,outbound}` con las interfaces de la sección 5.3 — verificación: los casos de uso solo dependen de interfaces.
- **T2 — Prueba de arquitectura**
  - T2.1 `tests/architecture_test.go` que analiza importaciones con `go/packages` — verificación: introducir una importación prohibida hace fallar la prueba.
- **T3 — Servidor**
  - T3.1 `cmd/server/main.go`: composición de dependencias en un solo lugar, apagado ordenado — verificación: `SIGTERM` cierra conexiones sin peticiones truncadas.
  - T3.2 Middleware: `request_id`, logs `slog` en JSON, recuperación de pánico, CORS restringido, tiempo límite — verificación: prueba por middleware.
  - T3.3 `/healthz` y `/readyz` — verificación: escenario de aceptación.

**DoD**: DoD-G + prueba de arquitectura en CI.

---

### E5-H2 — Adaptador analítico y endpoints de datos

**Como** frontend, **quiero** una API estable de tablero, consulta y exportación, **para** renderizar sin conocer el almacén.

- Dependencias: E5-H1, E2-H4, E3-H2 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Tablero
  Dado gold materializado
  Cuando consulto GET /api/v1/dashboard/overview con una competición-temporada
  Entonces recibo los KPIs, la serie temporal, el ranking y la comparativa en una sola respuesta
  Y la latencia p95 es menor a 2 segundos

Escenario: Consulta del explorador
  Dado el catálogo semántico
  Cuando envío POST /api/v1/query con métricas y dimensiones válidas
  Entonces recibo columnas tipadas, filas y el SQL ejecutado

Escenario: Consulta inválida
  Dado una petición con una métrica inexistente
  Cuando la envío
  Entonces recibo 422 con el nombre del campo ofensor y sugerencias

Escenario: Exportación
  Dado un resultado de consulta
  Cuando pido GET /api/v1/export?format=csv
  Entonces descargo un CSV con las mismas filas y cabeceras legibles
```

**Tareas**

- **T1 — Adaptador DuckDB**
  - T1.1 `adapter/outbound/duckdb/repository.go` implementando `AnalyticsRepository`, conexión de solo lectura y pool — verificación: prueba de integración contra el lakehouse del subset.
  - T1.2 Delegar la construcción de SQL al sidecar o al catálogo compartido, sin duplicar el compilador en Go — verificación: `grep -r "SELECT" backend/internal/adapter/outbound/duckdb` no muestra SQL de negocio embebido.
- **T2 — Catálogo**
  - T2.1 `adapter/outbound/semantic/catalog.go` que consume `/semantic/catalog` con caché de corta duración — verificación: cambiar un YAML se refleja tras invalidar la caché.
- **T3 — Endpoints**
  - T3.1 `GET /api/v1/dashboard/:id` con definición de tablero en `backend/config/dashboards/overview.yaml` — verificación: escenario de tablero.
  - T3.2 `POST /api/v1/query` — verificación: escenarios de consulta válida e inválida.
  - T3.3 `GET /api/v1/semantic/catalog` — verificación: contrato idéntico al del sidecar.
  - T3.4 `GET /api/v1/export` — verificación: escenario de exportación.
- **T4 — Servir el frontend**
  - T4.1 Incrustar `dist/` con `embed.FS` y fallback SPA a `index.html` — verificación: recargar una ruta profunda no da 404.

**DoD**: DoD-G + RNF-01 y RNF-02 medidos y registrados.

---

### E5-H3 — Adaptador del agente y endpoint de chat

**Como** frontend, **quiero** un único endpoint de chat, **para** no hablar directamente con el sidecar.

- Dependencias: E5-H1, E4-H3 · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Turno completo
  Dado el sidecar disponible
  Cuando envío POST /api/v1/chat con una pregunta y un identificador de sesión
  Entonces recibo respuesta en texto, datos tabulares, sugerencia de gráfica y trace_id

Escenario: Sidecar caído
  Dado que el sidecar no responde
  Cuando envío una pregunta
  Entonces recibo 503 con un mensaje que explica qué falla y qué hacer
  Y el error no expone rutas internas ni trazas de pila
```

**Tareas**

- **T1 — Adaptador**
  - T1.1 `adapter/outbound/sidecar/client.go` implementando `AgentGateway`, con timeout y propagación de `request_id` — verificación: el identificador aparece en los logs de ambos servicios.
  - T1.2 Interruptor de circuito simple ante fallos consecutivos — verificación: prueba con sidecar simulado caído.
- **T2 — Endpoints**
  - T2.1 `POST /api/v1/chat` — verificación: escenario de turno completo.
  - T2.2 `GET /api/v1/traces/:id` — verificación: devuelve la traza persistida.
  - T2.3 Streaming por SSE si el spike lo permite dentro del presupuesto de tiempo — verificación: opcional, marcado como RF-35.

**DoD**: DoD-G + los dos escenarios en verde.

---

## ÉPICA E6 — Frontend

### E6-H1 — Dirección de diseño, mockups y armazón

**Como** usuario, **quiero** una interfaz con identidad propia y coherente, **para** que la herramienta se sienta terminada y no una plantilla.

- Dependencias: E0-H1 · Estimación: L
- **Obligatorio**: aplicar las skills `.claude/skills/emil-kowalski`, `.claude/skills/impeccable` y `.claude/skills/design-taste-frontend` antes de escribir componentes.

**Criterios de aceptación**

```gherkin
Escenario: Dirección documentada antes del código
  Dado el brief del producto
  Cuando reviso docs/design-direction.md
  Entonces encuentro paleta de 4 a 6 valores hex nombrados, dos o más familias tipográficas con roles, concepto de layout y un elemento distintivo justificado
  Y cada elección está argumentada desde el dominio del fútbol, no desde una plantilla genérica

Escenario: Mockups como insumo
  Dado la dirección aprobada
  Cuando reviso docs/mockups/
  Entonces existen mockups de Google Stitch para las tres pantallas
  Y las decisiones de layout del código se corresponden con ellos

Escenario: Sistema de tokens
  Dado el armazón implementado
  Cuando inspecciono los estilos
  Entonces todo color, espaciado y tamaño tipográfico proviene de tokens
  Y no hay valores fijos dispersos en los componentes

Escenario: Piso de calidad
  Dado cualquier pantalla
  Cuando navego solo con teclado
  Entonces el foco es visible en todo control interactivo
  Y con prefers-reduced-motion activo no hay animaciones de desplazamiento
```

**Tareas**

- **T1 — Dirección de diseño**
  - T1.1 Redactar `docs/design-direction.md` con paleta, tipografía, layout y elemento distintivo — verificación: el documento nombra el elemento distintivo y por qué pertenece a este dominio.
  - T1.2 Autocrítica documentada: revisar la propuesta contra los tres clichés de diseño generado por IA y registrar qué se cambió — verificación: sección "qué descarté y por qué".
- **T2 — Mockups**
  - T2.1 Generar en Google Stitch los mockups de tablero, explorador y chat — verificación: tres archivos en `docs/mockups/`.
  - T2.2 Anotar sobre cada mockup los componentes de shadcn/ui que lo implementan — verificación: mapa componente↔mockup en el mismo documento.
- **T3 — Armazón**
  - T3.1 Configurar tokens en Tailwind desde la dirección de diseño — verificación: `tailwind.config` refleja la paleta nombrada.
  - T3.2 Instalar los componentes shadcn/ui necesarios y ajustarlos a los tokens — verificación: ningún componente conserva la paleta por defecto.
  - T3.3 `AppShell` con navegación de tres pantallas, pie con atribución a StatsBomb/Hudl — verificación: la atribución es visible en las tres rutas.
  - T3.4 Estados compartidos: `LoadingState`, `EmptyState`, `ErrorState` con texto accionable en voz de la interfaz — verificación: prueba de renderizado por estado.
  - T3.5 Cliente de API tipado generado o derivado del contrato OpenAPI — verificación: `tsc --noEmit` sin errores y sin `any`.

**DoD**: DoD-G + `axe` sin violaciones críticas + responsivo verificado a 375 px.

---

### E6-H2 — Pantalla Tablero

**Como** Ana, **quiero** un panorama de la competición, **para** orientarme antes de preguntar nada.

- Dependencias: E6-H1, E5-H2 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Carga inicial
  Dado que abro la aplicación
  Cuando el tablero termina de cargar
  Entonces veo KPIs de cabecera, evolución temporal, ranking de jugadores, comparativa de equipos y mapa de tiros

Escenario: Filtro global
  Dado el tablero cargado
  Cuando cambio la competición-temporada
  Entonces todas las visualizaciones se actualizan de forma consistente
  Y la selección persiste al navegar a otra pantalla y volver

Escenario: Sin datos
  Dado una combinación de filtros sin resultados
  Cuando se renderiza el tablero
  Entonces cada visualización muestra un estado vacío que explica qué cambiar
```

**Tareas**

- **T1 — Filtro global**
  - T1.1 Selector de competición-temporada alimentado por el catálogo — verificación: opciones provienen de la API, no fijas en código.
  - T1.2 Persistencia en la URL como parámetro de consulta — verificación: compartir el enlace reproduce la vista.
- **T2 — Visualizaciones**
  - T2.1 Tarjetas de KPI: partidos, goles, goles esperados, precisión de pase — verificación: cifras coinciden con la consulta directa a gold.
  - T2.2 Serie temporal de goles y goles esperados por jornada — verificación: gráfica de líneas con ejes etiquetados y formato correcto.
  - T2.3 Ranking de jugadores con métrica conmutable — verificación: cambiar la métrica reordena sin recargar la página.
  - T2.4 Comparativa de equipos con barras — verificación: orden y escala correctos.
  - T2.5 Mapa de tiros sobre cancha 120×80, tamaño por goles esperados y color por resultado — verificación: las coordenadas caen dentro del campo dibujado.
- **T3 — Rendimiento**
  - T3.1 Una sola petición para todo el tablero, con caché de TanStack Query — verificación: la pestaña de red muestra una llamada por cambio de filtro.

**DoD**: DoD-G + RNF-01 cumplido.

---

### E6-H3 — Pantalla Explorador ad-hoc

**Como** Ana, **quiero** armar mi propia consulta sin SQL, **para** responder preguntas que el tablero no cubre.

- Dependencias: E6-H1, E5-H2 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Construcción guiada
  Dado el catálogo semántico cargado
  Cuando selecciono una entidad, dos métricas y una dimensión
  Entonces el botón de ejecutar se habilita
  Y al ejecutar recibo tabla y gráfica del resultado

Escenario: Combinación inválida bloqueada
  Dado que elijo métricas de entidades con granos incompatibles
  Cuando intento ejecutar
  Entonces la interfaz lo impide y explica el conflicto en lenguaje de negocio

Escenario: Exportación
  Dado un resultado en pantalla
  Cuando pulso "Descargar CSV"
  Entonces obtengo un archivo con las mismas filas y cabeceras legibles

Escenario: Consulta visible
  Dado un resultado en pantalla
  Cuando abro el panel de detalle
  Entonces veo el SQL ejecutado y las métricas usadas con su definición
```

**Tareas**

- **T1 — Constructor**
  - T1.1 Panel de entidades, métricas, dimensiones y filtros con búsqueda — verificación: buscar por sinónimo en español encuentra la métrica.
  - T1.2 Validación en cliente con zod derivada del catálogo — verificación: escenario de combinación inválida.
  - T1.3 Filtros por tipo de dato: rango de fechas, selección múltiple, numérico — verificación: prueba por tipo.
- **T2 — Resultados**
  - T2.1 Tabla con ordenamiento, paginación y formato por tipo de métrica — verificación: porcentajes y decimales según el catálogo.
  - T2.2 Gráfica automática según cardinalidad y tipos, conmutable manualmente — verificación: matriz de casos.
  - T2.3 Panel de detalle con SQL y definiciones — verificación: escenario de consulta visible.
- **T3 — Exportación**
  - T3.1 Descarga de CSV desde el endpoint del backend — verificación: escenario de exportación.

**DoD**: DoD-G + RNF-02 cumplido.

---

### E6-H4 — Pantalla Chat

**Como** Ana, **quiero** preguntar en mi idioma, **para** obtener respuestas sin construir nada.

- Dependencias: E6-H1, E5-H3 · Estimación: L

**Criterios de aceptación**

```gherkin
Escenario: Estado inicial
  Dado que abro el chat por primera vez
  Entonces veo preguntas sugeridas construidas desde el catálogo real
  Y al pulsar una se envía tal cual

Escenario: Respuesta completa
  Dado que envío una pregunta respondible
  Cuando llega la respuesta
  Entonces veo el texto, la tabla, la gráfica sugerida y un enlace al detalle de la consulta

Escenario: Repregunta
  Dado una pregunta ambigua
  Cuando el agente necesita aclaración
  Entonces la interfaz muestra las opciones como botones seleccionables

Escenario: Imposible de responder
  Dado una pregunta fuera del modelo semántico
  Cuando llega la respuesta
  Entonces la interfaz lo declara con claridad y sugiere qué sí se puede preguntar
  Y no muestra ninguna tabla vacía

Escenario: Espera
  Dado que envío una pregunta
  Mientras se procesa
  Entonces veo un indicador de progreso que refleja la etapa actual
```

**Tareas**

- **T1 — Conversación**
  - T1.1 Lista de turnos con burbujas de usuario y agente, desplazamiento automático respetuoso del foco — verificación: prueba con teclado.
  - T1.2 Identificador de sesión persistido en el cliente — verificación: el seguimiento contextual funciona entre turnos.
  - T1.3 Preguntas sugeridas generadas desde el catálogo, no fijas en código — verificación: cambiar el YAML cambia las sugerencias.
- **T2 — Presentación de resultados**
  - T2.1 Tabla compacta con expansión a vista completa — verificación: resultados de 500 filas no bloquean la interfaz.
  - T2.2 Gráfica según `suggest_chart`, conmutable — verificación: matriz de casos.
  - T2.3 Panel plegable con SQL, entidades usadas, filas y duración — verificación: escenario de respuesta completa.
- **T3 — Estados**
  - T3.1 Indicador de etapa: interpretando, consultando, redactando — verificación: escenario de espera.
  - T3.2 Repregunta como opciones pulsables — verificación: escenario de repregunta.
  - T3.3 Mensaje de imposibilidad sin tabla vacía — verificación: escenario correspondiente.

**DoD**: DoD-G + MS-3 cumplido en la interfaz real, no solo en el arnés.

---

## ÉPICA E7 — Observabilidad, evaluación y entrega

### E7-H1 — Observabilidad extremo a extremo

**Como** operador, **quiero** seguir una petición por los tres servicios, **para** diagnosticar sin adivinar.

- Dependencias: E5-H3 · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Correlación
  Dado una pregunta del chat
  Cuando busco su request_id en los logs
  Entonces encuentro las entradas de frontend, backend, sidecar y llamada al modelo

Escenario: Trazas de herramienta
  Dado un turno del agente
  Cuando reviso las trazas
  Entonces cada invocación de herramienta es un tramo con su duración
```

**Tareas**

- **T1 — Logs**
  - T1.1 `slog` en JSON en Go y `structlog` en Python con el mismo esquema de campos — verificación: ambos emiten `ts`, `level`, `msg`, `request_id`, `service`.
  - T1.2 Propagación de `X-Request-ID` en toda llamada saliente — verificación: escenario de correlación.
- **T2 — Trazas**
  - T2.1 OpenTelemetry en frontera HTTP de Go y del sidecar — verificación: aparecen tramos padre-hijo.
  - T2.2 Instrumentar cada herramienta del agente y la ejecución de DuckDB — verificación: escenario de trazas de herramienta.
  - T2.3 Colector local en Compose con visor — verificación: la traza se ve completa en la interfaz del colector.

**DoD**: DoD-G + una traza de ejemplo capturada en `docs/observability.md`.

---

### E7-H2 — Cumplimiento de métricas de éxito

**Como** equipo, **queremos** verificar formalmente los umbrales, **para** declarar la POC exitosa con evidencia.

- Dependencias: E6-H4, E7-H1 · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Reporte consolidado
  Dado el sistema completo en ejecución
  Cuando ejecuto "make report"
  Entonces obtengo un documento con las siete métricas de la sección 2.3
  Y cada una indica valor medido, umbral y si cumple

Escenario: Fallo bloqueante
  Dado que una métrica obligatoria no cumple
  Cuando ejecuto "make report"
  Entonces el comando devuelve código de salida distinto de cero
```

**Tareas**

- **T1 — Medición**
  - T1.1 MS-1, MS-2, MS-3 y MS-5 desde `make eval` — verificación: valores en el reporte.
  - T1.2 MS-4 con prueba de carga sobre el tablero — verificación: p95 registrado.
  - T1.3 MS-6 verificado en contenedor limpio — verificación: log de la ejecución adjunto.
  - T1.4 MS-7 desde el reporte de calidad de datos — verificación: cobertura del subset al 100 %.
- **T2 — Reporte**
  - T2.1 `scripts/report.py` que consolida a `docs/acceptance-report.md` — verificación: el documento existe y es legible.

**DoD**: DoD-G + reporte de aceptación generado y versionado.

---

### E7-H3 — Guion de demostración y documentación

**Como** profesor, **quiero** una demostración reproducible, **para** exponerla en clase sin sorpresas.

- Dependencias: E7-H2 · Estimación: M

**Criterios de aceptación**

```gherkin
Escenario: Demostración en un comando
  Dado una máquina con Docker y acceso a platypy
  Cuando ejecuto "make demo"
  Entonces se ingiere el subset, se construye el medallón, se levantan los servicios y se abre el tablero
  Y todo el proceso termina sin intervención manual

Escenario: Guion verificado
  Dado el guion de demostración
  Cuando ejecuto cada paso en orden
  Entonces cada resultado esperado se cumple
```

**Tareas**

- **T1 — Automatización**
  - T1.1 Meta `demo` encadenando `data-pull SCOPE=subset`, `ingest`, `bronze`, `silver`, `gold`, `serve` — verificación: escenario de un comando.
  - T1.2 Comprobación previa de requisitos que falla temprano con mensaje claro — verificación: sin Docker, el mensaje lo dice.
- **T2 — Documentación**
  - T2.1 `README.md`: arquitectura, requisitos, arranque, comandos, atribución y aviso de ausencia de autenticación — verificación: alguien ajeno al proyecto levanta el sistema siguiéndolo.
  - T2.2 `docs/demo-script.md` con 10 preguntas de chat verificadas y su resultado esperado — verificación: las 10 producen respuesta correcta.
  - T2.3 `docs/architecture.md` con diagramas Mermaid de componentes, flujo de datos y hexágono — verificación: los diagramas renderizan.

**DoD**: DoD-G + `make demo` ejecutado con éxito en máquina limpia.

---

## 13. Riesgos y mitigaciones

| ID | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R-01 | La ingesta completa no cabe en 1-2 sesiones | Alta | Alto | Ruta crítica sobre subset determinista; carga completa en segundo plano reanudable (E1-H4) |
| R-02 | El modelo de 8 GB no alcanza la exactitud objetivo | Alta | Alto | Robustez en la arquitectura, no en el modelo: capa semántica, compilador, guardas y reparación. Spike E3-H1 decide la estrategia con datos |
| R-03 | La variante de Gemma prevista no existe o no cabe en VRAM | Media | Medio | Política de degradación al siguiente tamaño menor, registrada en ADR-002 |
| R-04 | Datos 360 inflan el almacenamiento y el tiempo de proceso | Media | Medio | Ingesta diferida e independiente; silver y gold funcionan sin ellos |
| R-05 | Sin dbt, se pierde gobernanza del linaje | Media | Medio | Contratos YAML validados con Pydantic, DAG propio, pruebas de calidad y `make lineage` |
| R-06 | Deriva de la arquitectura hexagonal bajo presión de tiempo | Media | Medio | Prueba de arquitectura automatizada que rompe el build |
| R-07 | El agente inventa métricas | Media | Alto | Allow-list desde el catálogo; imposible por construcción emitir SQL fuera del modelo semántico (MS-5 = 0 %) |
| R-08 | Latencia del chat por encima del umbral | Media | Medio | Contexto recortado por schema linking, `temperature=0`, caché de catálogo, reintentos acotados a 2 |
| R-09 | Diseño de interfaz genérico | Media | Bajo | Skills de diseño obligatorias y dirección documentada antes de codificar (E6-H1) |
| R-10 | Incumplimiento de la licencia de StatsBomb | Baja | Alto | Atribución obligatoria, uso no comercial, datos fuera del control de versiones |

---

## 14. Decisiones de arquitectura pendientes

| ADR | Título | Momento | Responsable de cerrarlo |
|---|---|---|---|
| ADR-001 | Versiones exactas del stack | E0-H1 | Implementador |
| ADR-002 | Selección del modelo local y parámetros | E0-H3 | Implementador |
| ADR-003 | Estrategia de generación NLtoSQL | E3-H1 | Equipo, con evidencia medida |
| ADR-004 | Estrategia de caché de consultas | E5-H2, si RNF-01 no se cumple | Implementador |
| ADR-005 | Streaming de la respuesta del chat | E5-H3, si sobra presupuesto | Implementador |

Formato obligatorio de cada ADR: contexto, opciones consideradas, evidencia, decisión, consecuencias, criterio de reversión.

---

## 15. Anexos

### 15.1 Glosario

| Término | Definición |
|---|---|
| GenBI | Inteligencia de negocio donde un modelo generativo media entre la pregunta y el almacén |
| Medallón | Organización en capas bronze (crudo), silver (limpio) y gold (consumible) |
| Capa semántica | Definición declarativa de métricas, dimensiones y relaciones, independiente del SQL físico |
| Schema linking | Recuperación de las entidades del esquema relevantes para una pregunta |
| Exactitud de ejecución | Proporción de preguntas cuyo resultado coincide con el esperado, sin exigir SQL idéntico |
| Grano | Nivel de detalle de una tabla de hechos, es decir qué representa una fila |
| Métrica de razón | Métrica no aditiva que debe recalcularse desde sus componentes en cada nivel de agregación |
| xG | Goles esperados, probabilidad de que un tiro termine en gol |

### 15.2 Atribución

Los datos provienen de **StatsBomb Open Data**, distribuidos por Hudl. Su uso en este proyecto es exclusivamente académico y no comercial. La atribución debe aparecer en el pie de todas las pantallas y en el `README.md`, conforme al acuerdo de uso de datos abiertos de StatsBomb.

### 15.3 Trazabilidad de decisiones tomadas en el levantamiento

| # | Decisión | Efecto en el PRD |
|---|---|---|
| 1 | POC de 1-2 sesiones, un equipo | Alcance vertical delgado; sin autenticación, sin orquestador |
| 2 | Dataset StatsBomb completo | Estrategia de dos vías (subset crítico + carga de fondo) |
| 3 | OLTP como fuente de verdad | Flujo unidireccional JSON → OLTP → medallón |
| 4 | Postgres OLTP + DuckDB/Parquet | Lakehouse en archivos; Go y Python leen en solo lectura |
| 5 | Python + Makefile, sin dbt | Runner propio con contratos Pydantic, DAG y pruebas de calidad |
| 6 | Pydantic para contratos | Ingesta, contratos de datos, capa semántica y API del sidecar |
| 7 | 8 GB de VRAM, Ollama | Robustez por arquitectura; contexto recortado; spike de modelo obligatorio |
| 8 | Estrategia NLtoSQL sin predefinir | Spike E3-H1 con compuerta de decisión y ADR-003 |
| 9 | Persona genérica de BI | Gold cubre patrones canónicos de BI |
| 10 | Un solo agente ADK con herramientas | Cuatro herramientas explícitas; sin enrutamiento multiagente |
| 11 | Tres pantallas | Tablero, explorador ad-hoc y chat |
| 12 | Sin autenticación | Documentado como restricción de red local |
| 13 | Historias con Gherkin, dependencias y DoD | Backlog de 8 épicas y 28 historias con verificación por subtarea |

---

*Fin del documento.*
