# Plan ML: Forecast + Probabilidad (vanilla JS + FastAPI + XGBoost global)

Contexto del repo: `bookish-potato`, pipeline OLTP/OLAP financiero con MySQL,
Superset y ~5.2M de filas de precios diarios (2021-08-06 → 2026-08-05).

## 1. Decisiones capturadas (Q&A)

| # | Decisión | Valor |
|---|----------|-------|
| 1 | Consumo del dash | **Fuera de Superset**: front vanilla JS servido por el propio servicio FastAPI |
| 2 | Estrategia de modelado | **A. Modelo global único** (todos los tickers juntos) |
| 3 | Modelo de regresión | **XGBoost** (no LSTM), horizonte **2 semanas** = t+1..t+10 días de trading |
| 4 | Probabilidad sube/baja | **B. Clasificador calibrado aparte** (XGBClassifier + calibración isotónica), horizonte 1 mes ≈ t+21 |
| 5 | Datos cloud | Snapshot embebido en el mismo contenedor (stateless); **arquitectura cloud se decide después, local primero** |
| 6 | Features | **B. Tabla persistida** `feat_diaria` en MySQL; la API hace SELECT ligero |
| 7 | UX del front | **A. Autocomplete** global + chips de lista/sector + historia completa con rango de fechas |
| 8 | Acceso a datos para entrenar | Misma LAN: máquina de entrenamiento ↔ host del MySQL (bind en `compose.yml`/`MYSQL_HOST`) + usuario `train` (solo SELECT) |
| 9 | Artefactos | **A. `models/` en el repo**, montado ro en el contenedor + `models/current.json` |
| 10 | Output del regresor | **A. Puntual + banda Q10/Q90** (regresión cuantílica) |
| 11 | Refresco/retrain | **Sin refresco automático**: demo. Datos estáticos, retrain manual on-demand |

Herramientas: **Polars** (reemplaza pandas de los scripts existentes).

## 2. Arquitectura (local primero)

```
Browser (vanilla JS, estático)
        │  GET /  →  index.html
        │  GET /api/v1/tickers          (autocomplete)
        │  GET /api/v1/ticker/{sim}/history
        │  GET /api/v1/ticker/{sim}/forecast
        ▼
forecast-api (FastAPI :8090) ──┐  serve static + reads MySQL
        │  models/ (ro, montado)        │  env: MYSQL_DASHBOARDS_*
        ▼                              ▼
   XGBoost .joblib              MySQL finanzas (127.0.0.1:3306)
                                    │ también bind LAN para entrenamiento (solo train SELECT)
                                    ▼
                              máquina de entrenamiento — entrenamiento por LAN
```

Superset queda intacto y fuera de alcance.

### Servicios docker (compose.yml)
- `mysql`: el bind LAN se configura con la variable `MYSQL_HOST` (ej. `192.168.x.x:3306:3306` para exponer a la máquina de entrenamiento). Crear usuario `train` (SELECT en `finanzas` y `finanzas_olap`).
- `forecast-api` (nuevo): `build: ./docker/forecast`, puerto `127.0.0.1:8090:8090`,
  volumen `./models:/app/models:ro`, `depends_on: mysql: healthy`,
  env `MYSQL_HOST`, `MYSQL_DASHBOARDS_USER`, `MYSQL_DASHBOARDS_PASSWORD`.

## 3. Estructura de datos (nueva)

### `finanzas_olap.feat_diaria`
Tabla denormalizada y autocontenida (para entrenar en la máquina de entrenamiento y servir igual), PK `(simbolo, fecha)`.

| col | tipo | detalle |
|-----|------|---------|
| `simbolo` | VARCHAR(20) | |
| `fecha` | DATE | |
| `sector` | VARCHAR(80) | |
| `es_sp500, es_nasdaq, es_amex` | TINYINT | membresías |
| `close` | DECIMAL(18,6) | precio de cierre |
| `ret_1d, ret_5d, ret_21d, ret_63d` | DECIMAL(18,8) | retornos pasados |
| `ma_5, ma_20, ma_50` | DECIMAL(18,6) | medias móviles |
| `ma_ratio_20_50` | DECIMAL(18,8) | relación de medias |
| `vol_20` | DECIMAL(18,8) | vol. 20d (std de ret_1d) |
| `rng_mean_20` | DECIMAL(18,8) | rango medio 20d |
| `volumen_log` | DECIMAL(18,8) | ln(volumen) |
| `volume_ratio_20` | DECIMAL(18,8) | volumen vs media 20d |
| `mes_num` | TINYINT | calendario |
| `dia_semana` | TINYINT | calendario |
| `mkt_ret_1d`, `mkt_vol_20` | DECIMAL(18,8) | contexto de mercado (agregación cross-tickers) |

Labels NO se persisten: el entrenamiento deriva los targets con lags de `close`.

### `models/`
- `forecast_q10.joblib`, `forecast_q50.joblib`, `forecast_q90.joblib` (XGBoost reg)
- `updown_clf.joblib` (XGBClassifier), `updown_iso.joblib` (CalibratedClassifier isotónico)
- `current.json` → `{"modelo": "vYYYYMMDDHHMM", "rutas": {...}, "entrenado_el": "..."}`
- `.gitignore` mantiene los `.joblib` fuera (o se decide versionarlos si son < ~50MB cada uno).

## 4. Estrategia de modelo (multi-horizon directo con covariable de horizonte)

**No se entrenan 10 modelos por cuantil ni recursión.** Enfoque directo:

- **Entrenamiento**: fila = `(simbolo, fecha, h)` con target `close(t+h)/close(t) - 1` y **`h` (1..10) como feature explícita**. Un modelo por cuantil aprende el efecto del horizonte.
- **Inferencia**: features al último día disponible + *feed* de `h=1..10` para cada cuantil → trayectoria de 10 días con banda Q10/Q90 en un solo forward pass por cuantil.
- **Probabilidad 1 mes**: XGBClassifier sobre el signo de `close(t+21)/close(t) - 1`, calibrado con isotónico (prob = share de P(subir)).
- **Artefactos**: `q10`, `q50`, `q90`, `updown_clf`, `updown_iso` (5 en total).

### Endpoints API (forecast-api :8090)
| método | ruta | responde |
|--------|------|----------|
| GET | `/` | HTML del front |
| GET | `/api/v1/health` | `{status: ok}` |
| GET | `/api/v1/tickers?q=&lista=&sector=` | lista para autocomplete |
| GET | `/api/v1/ticker/{sim}/history?desde=&hasta=` | OHLCV histórico |
| GET | `/api/v1/ticker/{sim}/forecast` | `{asof, historico_ultimo, forecast:[{h, fecha, q10, q50, q90}], prob_up, prob_down, p_actual, modelo}` |

## 5. Entrenamiento en máquina separada (cero duplicación)

1. `scripts/build_features.py` (host con MySQL local) → llena `feat_diaria`.
2. `scp scripts/train_forecast.py scripts/features.py` → máquina de entrenamiento; venv con `polars xgboost scikit-learn pymysql sqlalchemy joblib`.
3. La máquina lee `feat_diaria` por LAN (bind `MYSQL_HOST`, usuario `train`) y entrena.
4. `scp` artefactos → `./models` del repo → `current.json`.

## 6. Front vanilla JS (sin dependencias)

- `static/index.html` + `static/styles.css` + `static/app.js` (gráfico propio SVG).
- Autocomplete símbolo/nombre; chips de lista/sector; inputs de rango de fechas.
- Render: historia (close) + banda Q10/Q90 + mediana 10 días + badge "P(subir mes) = X%".

## 7. Ejecución con swarm de agentes (paralelización)

Tareas no dependientes → lanzadas como agentes independientes en paralelo:

- **Stream A — DB/features** (base): DDL feat_diaria + usuario `train` + `features.py` + `build_features.py` (Polars).
- **Stream B — Entrenamiento** (depende de A): `train_forecast.py` → corre en la máquina de entrenamiento → scp artefactos a `./models`.
- **Stream C — API** (depende solo del contrato de endpoints): `docker/forecast/` (Dockerfile + `main.py` + requirements).
- **Stream D — Front** (depende solo del contrato): `static/` (index/styles/app).

Orden: `A ‖ C ‖ D` en paralelo; `B` arranca cuando A termina; integración
(`docker compose up -d forecast-api` + verificación en `:8090`) al cierre.

## 8. Pasos de ejecución

1. `compose.yml`: bind de MySQL según `MYSQL_HOST` + servicio `forecast-api`. `.env`/`.env.example`: `MYSQL_TRAIN_USER`/`MYSQL_TRAIN_PASSWORD`.
2. DDL `feat_diaria` + usuario `train` (SQL vía root).
3. Swarm: A, C, D en paralelo → luego B en la máquina de entrenamiento → scp artefactos.
4. `docker compose up -d forecast-api` → verificar `http://127.0.0.1:8090` (curl + browser).
5. Post-demo: imagen Cloud Run con snapshot de datos + modelos embebidos (stateless) — fuera de alcance por ahora.

## 9. Riesgos / notas

- Banda Q10/Q90 en XGBoost: objective `reg:quantileerror` (cuantil objetivo). Validar en holdout la cobertura empírica de la banda.
- Dataset expandido ~10×5.2M filas máx.; en la máquina de entrenamiento (mucha RAM) con Polars lazy + sampleo de `h` si hace falta.
- El forecast asume datos frescos hasta `2026-08-05` (demo estática).
- `models/current.json` es la fuente de verdad de la versión activa; la API lo relee en cada request.