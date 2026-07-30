# Estado del Proyecto — 2026-07-30 (cubo cargado)

## ✅ Completado

### Arquitectura & Código
- ✅ Schema OLAP `rama_olap` (DDL completo: dimensiones + fact + agregados)
- ✅ ETL `scripts/construir_olap.py` (limpieza, carga batch, refresh vistas)
- ✅ API FastAPI (8 endpoints REST, schemas Pydantic, pool psycopg)
- ✅ Dashboard (HTML/CSS/JS, Plotly, Leaflet, filtros interactivos)
- ✅ Docker Compose (servicio API, build Dockerfile)
- ✅ Documentación (README, OLAP_SCHEMA.md, QUICKSTART_DASHBOARD.md)

### Datos
- ✅ OLTP cargado: 50.3M mediciones en `rama.medicion`
- ✅ Dimensiones OLAP pobladas:
  - dim_tiempo: 350,640 horas (1986-01-01 00:00 → 2025-12-31 23:00)
  - dim_alcaldia: 26 canónicas (limpiadas de 31 sucias con HTML entities)
  - dim_contaminante: 9 contaminantes
  - dim_estacion: 54 estaciones (período vigente)
  - dim_categoria_contaminante: 2 (Gases, Partículas)

### Infraestructura
- ✅ PostgreSQL OLTP corriendo (rama-postgres-oltp)
- ✅ API FastAPI levantada (rama-api, puerto 8080)
- ✅ Dashboard accesible en http://localhost:8080/

### Funcionalidad
- ✅ `/health` endpoint funciona
- ✅ `/api/dimensiones/*` endpoints retornan datos limpios
- ✅ `/api/kpis` → 2.7 índice normalizado, 60.6% completitud, 36 estaciones,
  9 contaminantes, 2,345,578 mediciones (período por defecto: últimos 12 meses)
- ✅ `/api/series-tiempo` en las 3 granularidades (hora/día/mes)
- ✅ `/api/mapa-estaciones`, `/api/ranking/*`, `/api/completitud` con datos reales
- ✅ Dashboard HTML se sirve con paleta corporativa (navy + acento)
- ✅ GIF del dashboard en `docs/dashboard-demo.gif`, embebido en el README
- ✅ Swagger docs en http://localhost:8080/docs

### Carga de la Fact Table (resuelta)
- ✅ `fact_medicion_hora`: 50,303,091 filas (2,416 MB heap / 3,766 MB con índices)
- ✅ Vistas materializadas refrescadas y `ANALYZE` corrido
- ✅ Los 8 endpoints validados con datos reales (HTTP 200)

**Qué estaba fallando**: la carga se hacía con los 4 índices parciales y las 3 FKs
activas. Mantener 2.7 GB de índices durante un INSERT de 50M filas es lo que la
volvía interminable — no era un deadlock.

| Paso | Tiempo |
|------|--------|
| DROP de 3 FKs + 4 índices | 1 s |
| TRUNCATE | 0.1 s |
| `INSERT ... SELECT` de 50,303,091 filas | 39 s |
| CREATE de los 4 índices | 32 s |
| ADD de las 3 FKs (revalidadas) | 9 s |
| ANALYZE + REFRESH de las 2 vistas materializadas | 23 s |

Receta correcta (~90 s en total):

```sql
ALTER TABLE rama_olap.fact_medicion_hora DROP CONSTRAINT ...;  -- 3 FKs
DROP INDEX ...;                                                -- 4 índices
TRUNCATE rama_olap.fact_medicion_hora;
INSERT INTO rama_olap.fact_medicion_hora SELECT ... FROM rama.medicion ...;  -- 39 s
CREATE INDEX ...;                                              -- 4 índices, ~32 s
ALTER TABLE ... ADD CONSTRAINT ...;                            -- 3 FKs revalidadas, 9 s
ANALYZE; REFRESH MATERIALIZED VIEW ...;                        -- 23 s
```

No hizo falta COPY ni paralelismo: `INSERT ... SELECT` sobre un heap sin índices
va a ~1.3M filas/s. La receta está implementada en
`pueblar_fact_mediciones()` de `scripts/construir_olap.py`: con `--anio` se
reemplaza sólo ese año y los índices se dejan en su lugar.

### Bugs de la API que sólo aparecieron con datos
- ✅ `obtener_kpis` tomaba `MIN` en vez de `MAX` del rango disponible
  (`fecha_max_str, _ = ...`) → el período por defecto era 1985→1986 y los KPIs
  salían casi vacíos
- ✅ `series-tiempo` (día/mes) devolvía una fila por estación *por fecha* → puntos
  duplicados en el gráfico; ahora agrega sobre estaciones (`GROUP BY fecha`)
- ✅ `series-tiempo` con `granularidad=hora` fallaba con error de `GROUP BY`
  (agrupaba por `fecha_hora::DATE` y ordenaba por `fecha_hora`)
- ✅ Ventana por defecto según granularidad (7 / 30 / 730 días): con 30 días fijos
  la vista mensual devolvía un solo punto
- ✅ Rankings: estaciones/contaminantes sin datos válidos en el período llegaban
  con `indice_normalizado = NULL` y, por `NULLS FIRST` en `DESC`, encabezaban el
  ranking; ahora se excluyen con `HAVING AVG(...) IS NOT NULL` y los schemas
  Pydantic aceptan `Optional[float]`

## 📊 Cifras Finales

| Tabla | Filas | Estado |
|-------|-------|--------|
| rama.medicion | 50,303,091 | ✅ Cargado |
| rama_olap.fact_medicion_hora | 50,303,091 | ✅ Cargado |
| rama_olap.agg_medicion_diaria | 2,096,098 | ✅ Refrescada |
| rama_olap.agg_medicion_mensual | 68,957 | ✅ Refrescada |

### Bugs del dashboard (aparecieron al verificar las capturas)
- ✅ El mapa Leaflet se inicializaba con `#tab-mapa` en `display:none`, así que
  medía un contenedor de 0x0 y cargaba un solo tile. Un usuario que hacía clic en
  "Mapa" veía el mapa roto. Ahora `cambiar_tab()` llama `invalidateSize()` +
  `fitBounds` sobre las estaciones (`L.featureGroup`, no `layerGroup`: sólo el
  primero expone `getBounds()`)
- ✅ Los `circleMarker` no se limpiaban entre refrescos — el chequeo era
  `instanceof L.Marker`, que no los cubre — y se acumulaban. Ahora van en un
  featureGroup y se limpian con `clearLayers()`
- ✅ Los códigos `CHAR(5)`/`CHAR(3)` llegaban con padding (`"PM25 "`), así que
  ninguna pill de contaminante quedaba resaltada y las etiquetas del eje X
  arrastraban espacios. La API los devuelve con `TRIM()`
- ✅ Los inputs de fecha mostraban un rango de 2026 (`valueAsDate` con `hoy`)
  mientras el gráfico dibujaba diciembre de 2025, y cada endpoint resolvía su
  propio default. Nuevo `/api/rango-fechas`: el dashboard fija fechas explícitas
  desde la última fecha con datos y reencuadra la ventana al cambiar de
  granularidad
- ✅ `Plotly.Plots.resize()` al mostrar el tab de Calidad de Datos: la gráfica se
  dibujaba a 700px sobre un contenedor oculto
- ✅ La tarjeta de mediciones dividía siempre entre 1e6 y mostraba "0.0M" para
  16,368 registros

### Seguridad
- ✅ **Inyección SQL corregida**: `api/consultas.py` interpolaba los parámetros de
  query con f-strings (`dc.codigo = '{contaminante}'`). Todos los valores pasan
  ahora como parámetros de psycopg (`%s`). Lo único que queda interpolado son
  fragmentos internos: nombres de tabla y el `ASC`/`DESC` derivado de una
  comparación cerrada
- ✅ `DATABASE_URL` se lee de entorno en los scripts (antes hardcodeada); el
  default `rama:rama@localhost` queda sólo como conveniencia de desarrollo
- ✅ No hay `.env` en el árbol; `.gitignore` cubre `.env*` salvo `.env.example`
- ⚠️ La API no tiene autenticación ni CORS configurado. Está bien para
  `localhost`, pero **no la expongas a una red sin poner auth delante**
- ⚠️ Las credenciales `rama:rama` de `compose.yml` y `.env.example` son de
  desarrollo. Cambiarlas antes de cualquier despliegue

## 🚨 Notas Importantes

- **Índice normalizado 0-100**: Agnóstico a unidades. Cálculo: `100 * (valor - min) / (max - min)`
- **Alcaldías limpias**: 31 variantes (HTML entities) deduplicadas a 26 canónicas
- **NULLs reales**: 18-38% de mediciones son faltantes (sensor inactivo) — se explota como KPI
- **IMECA**: Solo O3 verificado (NADF-009-AIRE-2006); demás pendientes de SEDEMA

## 🔗 URLs

- Dashboard: http://localhost:8080/
- Swagger API Docs: http://localhost:8080/docs
- Health Check: http://localhost:8080/health
- Base datos: postgresql://rama:rama@localhost:5433/rama

## 📝 Commit History

1. `fbf7b2e` — feat: cubo OLAP snowflake + API FastAPI + dashboard McKinsey/PwC
2. `4ddb675` — docs: guía de uso del dashboard OLAP
3. `44a5099` — docs: agregar verificación del cubo OLAP y API
4. `aaa9ba3` — docs: estado del proyecto (2026-07-30)

---

**Última actualización**: 2026-07-30 23:20 UTC — cubo OLAP cargado y validado  
**Rama**: `l01-oltp-olap`
