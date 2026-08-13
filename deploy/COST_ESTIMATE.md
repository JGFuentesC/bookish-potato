# Estimación de costo — Forecast Dashboard en Cloud Run

**Fecha:** 2026-08-12 · **Proyecto:** `<MI-PROYECTO-GCP>` · **Región:** `us-central1`
**Recurso desplegado:** Cloud Run (instancia-based? no — request-based), 1 vCPU / 1 GiB,
`--min-instances=0 --max-instances=1`, sin Cloud SQL, sin GCS, sin Load Balancer.

---

## Tarifas aplicadas (us-central1, request-based billing, 2026)

| Recurso | Tarifa | Free tier / mes |
|---|---|---|
| CPU activo (vCPU-s) | $0.000024 | 180 000 vCPU-s (= 50 h @ 1 vCPU) |
| RAM activa (GiB-s) | $0.0000025 | 360 000 GiB-s (= 100 h @ 1 GiB) |
| Requests | $0.40 / 1M | 2M |
| Egress internet | $0.12 / GB | 1 GB |
| Artifact Registry (imagen) | $0.10 / GB/mes | 0.5 GB |
| Secret Manager (1 versión activa) | $0.06 / mes | — |
| Cloud Build | n.a. | Build local (`docker buildx`), sin cargo |

> Con `min-instances=0` el contenedor escala a cero y **no se paga tiempo idle**.
> Solo se factura CPU/RAM mientras el contenedor atiende peticiones.

---

## Escenarios mensuales

| Escenario | CPU activo | Requests | CPU $ | RAM $ | Req $ | Egress $ | AR $ | SM $ | **Total** |
|---|---|---|---|---|---|---|---|---|---|
| Clase (~1 800 cargas/semana, 25 h) | 25 h | 25 k | 0.00 | 0.00 | 0.00 | 0.02 | 0.04 | 0.06 | **$0.12** |
| Uso medio campus (60 h, 200 k) | 60 h | 200 k | 0.86 | 0.00 | 0.00 | 0.36 | 0.04 | 0.06 | **$1.32** |
| Intensivo (150 h, 2.5 M) | 150 h | 2.5 M | 8.64 | 0.45 | 0.20 | 2.28 | 0.04 | 0.06 | **$11.67** |

### Desglose del escenario "uso medio campus"
- **CPU:** 60 h × 3600 = 216 000 vCPU-s − 180 000 gratis = 36 000 × $0.000024 = **$0.86**
- **RAM:** 216 000 GiB-s < 360 000 gratis → **$0.00**
- **Requests:** 200 k < 2 M gratis → **$0.00**
- **Egress:** 4 GB − 1 GB gratis = 3 × $0.12 = **$0.36**
- **Artifact Registry:** imagen ~0.9 GB comprimido − 0.5 gratis = 0.4 × $0.10 = **$0.04**
- **Secret Manager:** **$0.06**

---

## Supuestos y mitigaciones

- **Imagen ~0.9 GB** en Artifact Registry: 510 MB de snapshot SQLite + modelos XGBoost (10 MB)
  + runtime Python. Se almacena comprimida (~50 %).
- **Cold start:** la imagen (≈1 GB) se descarga al arrancar la primera instancia; con
  `min=0` solo ocurre tras 15 min sin tráfico. El segundo arranque en frío es rápido
  (imagen en caché de la zona). El startup se factura como tiempo activo de la primera petición.
- **1 vCPU / 1 GiB** es suficiente: el snapshot se lee por páginas de SQLite (no se carga en RAM)
  y los modelos (~11 MB) se cargan lazy y se cachean en el proceso.
- **Sin servicios adicionales:** no hay Cloud SQL (snapshot estático), no hay GCS, no hay LB/Gateway
  (el tráfico entra directo al endpoint HTTPS de Cloud Run), no hay min-instances que paguen idle.
- **Protección anti-abuso:** token en `/api/v1` + `max-instances=1` + `--cpu-throttling` (CPU solo
  durante handling) limitan el peor caso de scraping.

**Rango esperado: $0.12–1.32/mes** para uso académico (free tier absorbe la mayor parte).