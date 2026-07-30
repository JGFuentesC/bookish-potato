# Estado del Proyecto — 2026-07-30

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
- ✅ Dashboard HTML se sirve con paleta corporativa (navy + acento)
- ✅ Swagger docs en http://localhost:8080/docs

## ⏳ En Progreso

### Carga de Datos
- ⏳ `fact_medicion_hora`: Script cargando 50.3M mediciones en batches/año
  - Fase: INSERT batch
  - Filas cargadas: 0 (probablemente completando primer año)
  - ETA: 20-30 minutos

**Monitor activo**: Esperando a que `fact_medicion_hora` > 0

## 🔜 Próximos Pasos (cuando fact complete)

1. Validar endpoints con datos reales:
   - `/api/kpis` → retorna KPIs agregados
   - `/api/series-tiempo` → retorna series temporales
   - `/api/mapa-estaciones` → retorna estaciones con últimas lecturas
   - `/api/ranking/*` → retorna rankings
   - `/api/completitud` → retorna % completitud

2. Probar dashboard interactivo:
   - Cargar filtros (contaminantes, alcaldías, etc.)
   - Verificar rendimiento (queries en agregados, no fact de 50M)
   - Revisar charts (Plotly) y mapa (Leaflet)
   - Validar guardrails (hora limitado a 90 días + estación)

3. Refresh de vistas materializadas:
   ```bash
   docker exec rama-postgres-oltp psql -U rama -d rama -c \
     "REFRESH MATERIALIZED VIEW rama_olap.agg_medicion_diaria; \
      REFRESH MATERIALIZED VIEW rama_olap.agg_medicion_mensual;"
   ```

## 📊 Cifras Finales Esperadas

Cuando `construir_olap.py` complete:

| Tabla | Filas | Estado |
|-------|-------|--------|
| rama.medicion | 50.3M | ✅ Cargado |
| rama_olap.fact_medicion_hora | 50.3M | ⏳ Cargando |
| rama_olap.agg_medicion_diaria | ~13.8M | ⏳ Refrescando |
| rama_olap.agg_medicion_mensual | ~468K | ⏳ Refrescando |

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

---

**Última actualización**: 2026-07-30 22:35 UTC  
**Rama**: `l01-oltp-olap`
