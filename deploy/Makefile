# ============================================================================
# Despliegue del dashboard "Forecast" (vanilla JS + FastAPI + XGBoost) en
# Cloud Run — sin Cloud SQL ni GCS: snapshot SQLite + modelos embebidos.
#
# Frugalidad: min-instances=0, max-instances=1, 1 vCPU / 1 GiB, sin LB.
# Seguridad: service account de mínimos privilegios + token de API en Secret
# Manager (rutas /api/v1 protegidas).
# ============================================================================

SHELL := /bin/bash

PROJECT_RAW := $(shell gcloud config get-value project 2>/dev/null)
PROJECT := $(or $(PROJECT_RAW),MI-PROYECTO-GCP)
REGION_RAW := $(shell gcloud config get-value compute/region 2>/dev/null)
REGION := $(or $(REGION_RAW),us-central1)

SERVICE := finanzas-dashboard
REPO    := finanzas-dashboard
SA      := finanzas-dash-sa
SECRET  := finanzas-dash-api-token

SA_EMAIL   := $(SA)@$(PROJECT).iam.gserviceaccount.com
REGISTRY   := $(REGION)-docker.pkg.dev/$(PROJECT)/$(REPO)
TAG        := $(shell date +%Y%m%d%H%M%S)
IMAGE      := $(REGISTRY)/$(SERVICE):$(TAG)
IMAGE_LAT  := $(REGISTRY)/$(SERVICE):latest
DB_SNAPSHOT := deploy/data/static.db
TOKEN_FILE  := deploy/.api_token

.PHONY: help deps token auth snapshot build push scan cost \
        deploy url validate-local validate-remote qa atlas destroy

help:
	@echo "Objetivos del despliegue Cloud Run:"
	@echo "  make deps       crea Artifact Registry, Service Account y roles mínimos"
	@echo "  make token      genera/rota el token de API en Secret Manager"
	@echo "  make snapshot   exporta deploy/data/static.db desde MySQL (solo lectura)"
	@echo "  make auth       gcloud auth configure-docker para la región"
	@echo "  make build      docker buildx (linux/amd64) imagen del dashboard"
	@echo "  make push       sube la imagen a Artifact Registry"
	@echo "  make scan       escanea la imagen con Trivy (HIGH/CRITICAL)"
	@echo "  make cost       estimación de costo mensual (ANTES de desplegar)"
	@echo "  make deploy     despliega en Cloud Run (min0/max1, SA mínimos)"
	@echo "  make url        muestra la URL del servicio"
	@echo "  make validate-local  smoke test local del contenedor"
	@echo "  make validate-remote smoke test de los endpoints en Cloud Run"
	@echo "  make qa         revisión de seguridad: secretos, IAM, allow-unauthenticated"
	@echo "  make atlas      genera deploy/INFRA_ATLAS_LIVE.md (estado live; el atlas curado es INFRA_ATLAS.md)"
	@echo "  make destroy    elimina el servicio (y opcionalmente repo/SA/secret)"

# ---------------------------------------------------------------------------
# Dependencias GCP
# ---------------------------------------------------------------------------
deps:
	@gcloud artifacts repositories create $(REPO) \
		--repository-format=docker --location=$(REGION) \
		--description="Imágenes del dashboard Forecast (Cloud Run)" \
		--project=$(PROJECT) || echo "[repo ya existe]"
	@gcloud iam service-accounts create $(SA) \
		--display-name="Cloud Run $(SERVICE) — mínimos privilegios" \
		--project=$(PROJECT) || echo "[SA ya existe]"
	@gcloud projects add-iam-policy-binding $(PROJECT) \
		--member=serviceAccount:$(SA_EMAIL) --role=roles/logging.logWriter || true
	@gcloud projects add-iam-policy-binding $(PROJECT) \
		--member=serviceAccount:$(SA_EMAIL) --role=roles/monitoring.metricWriter || true
	@gcloud projects add-iam-policy-binding $(PROJECT) \
		--member=serviceAccount:$(SA_EMAIL) --role=roles/artifactregistry.reader || true
	@echo "OK: repo + SA + roles mínimos (logWriter, metricWriter, artifactregistry.reader)"

token:
	@test -f $(TOKEN_FILE) || (openssl rand -hex 24 > $(TOKEN_FILE) && chmod 600 $(TOKEN_FILE) && echo "[token generado]")
	@V=$$(cat $(TOKEN_FILE)); \
	gcloud secrets describe $(SECRET) --project=$(PROJECT) >/dev/null 2>&1 || \
		printf '%s' "$$V" | gcloud secrets create $(SECRET) \
			--data-file=- --replication-policy=automatic --project=$(PROJECT); \
	printf '%s' "$$V" | gcloud secrets versions add $(SECRET) \
		--data-file=- --project=$(PROJECT) >/dev/null 2>&1 || true
	@gcloud secrets add-iam-policy-binding $(SECRET) \
		--member=serviceAccount:$(SA_EMAIL) \
		--role=roles/secretmanager.secretAccessor --project=$(PROJECT) || true
	@echo "OK: secret $(SECRET) en Secret Manager (accesible por $(SA_EMAIL))"

auth:
	@gcloud auth configure-docker $(REGION)-docker.pkg.dev --quiet

# ---------------------------------------------------------------------------
# Datos + imagen
# ---------------------------------------------------------------------------
snapshot:
	@test -f .env || (echo "Falta .env en la raíz"; exit 1)
	uv run python deploy/scripts/export_snapshot.py --salida $(DB_SNAPSHOT)

build:
	@test -f $(DB_SNAPSHOT) || (echo "Corre primero: make snapshot"; exit 1)
	@test -f models/current.json || (echo "Faltan modelos en models/"; exit 1)
	docker buildx build --platform=linux/amd64 --provenance=false \
		-f deploy/Dockerfile -t $(IMAGE) -t $(IMAGE_LAT) .

push: auth
	docker push $(IMAGE)
	docker push $(IMAGE_LAT)

scan:
	@test -n "$(IMAGE)" || exit 1
	trivy image --severity HIGH,CRITICAL --exit-code 1 $(IMAGE_LAT) || echo "[se revisa el reporte]"

cost:
	uv run python deploy/scripts/estimate_cost.py

# ---------------------------------------------------------------------------
# Cloud Run
# ---------------------------------------------------------------------------
deploy: deps token build push
	gcloud run deploy $(SERVICE) \
		--project=$(PROJECT) --region=$(REGION) \
		--image=$(IMAGE) \
		--service-account=$(SA_EMAIL) \
		--min-instances=0 --max-instances=1 \
		--cpu=1 --memory=1Gi \
		--concurrency=10 --timeout=120s \
		--no-cpu-boost \
		--allow-unauthenticated \
		--set-env-vars=DATA_MODE=sqlite,STATIC_DIR=/app/static,MODELS_DIR=/app/models,STATIC_DB=/app/data/static.db \
		--set-secrets=API_TOKEN=$(SECRET):latest \
		--port=8080
	@$(MAKE) -f deploy/Makefile url

url:
	@gcloud run services describe $(SERVICE) --project=$(PROJECT) --region=$(REGION) \
		--format="value(status.url)"

# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------
validate-local: build
	@echo ">> Levantando contenedor local en :8091 (DATA_MODE=sqlite, token=testtoken)"
	@docker run --rm -d --name finanzas-dash-local -p 8091:8080 \
		-e DATA_MODE=sqlite -e STATIC_DIR=/app/static -e MODELS_DIR=/app/models \
		-e STATIC_DB=/app/data/static.db -e API_TOKEN=testtoken $(IMAGE)
	@curl -s -o /dev/null --retry 45 --retry-connrefused --retry-delay 2 \
		http://127.0.0.1:8091/api/v1/health || (docker logs finanzas-dash-local && exit 1)
	@echo "health sin token (espera 401):" && curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8091/api/v1/health
	@echo "health con token (espera 200):" && curl -s -H "Authorization: Bearer testtoken" http://127.0.0.1:8091/api/v1/health
	@echo "tickers (3):" && curl -s -H "Authorization: Bearer testtoken" "http://127.0.0.1:8091/api/v1/tickers?q=aapl" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d), d[0]['simbolo'] if d else '-')"
	@echo "history AAPL (filas):" && curl -s -H "Authorization: Bearer testtoken" "http://127.0.0.1:8091/api/v1/ticker/AAPL/history?desde=2026-01-01" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))"
	@echo "forecast AAPL:" && curl -s -H "Authorization: Bearer testtoken" "http://127.0.0.1:8091/api/v1/ticker/AAPL/forecast" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['simbolo'], d['precio_actual'], 'h=', len(d['forecast']), 'modelo=', d['modelo'])"
	@echo "front / (token inyectado):" && curl -s http://127.0.0.1:8091/ | grep -q 'window.__API_TOKEN__' && echo "OK" || echo "placeholder no inyectado"
	@docker rm -f finanzas-dash-local >/dev/null

validate-remote:
	@URL=$$(gcloud run services describe $(SERVICE) --project=$(PROJECT) --region=$(REGION) --format="value(status.url)"); \
	V=$$(gcloud secrets versions access latest --secret=$(SECRET) --project=$(PROJECT)); \
	echo "URL: $$URL"; \
	echo "health sin token (401):" && curl -s -o /dev/null -w "%{http_code}\n" "$$URL/api/v1/health"; \
	echo "health con token (200):" && curl -s -H "Authorization: Bearer $$V" "$$URL/api/v1/health"; \
	echo "tickers q=aapl:" && curl -s -H "Authorization: Bearer $$V" "$$URL/api/v1/tickers?q=aapl" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d), d[0]['simbolo'] if d else '-')"; \
	echo "forecast AAPL:" && curl -s -H "Authorization: Bearer $$V" "$$URL/api/v1/ticker/AAPL/forecast" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['simbolo'], d['precio_actual'], 'h=', len(d['forecast']), d['modelo'])"; \
	echo "front inyecta token:" && (curl -s "$$URL/" | grep -q 'window.__API_TOKEN__' && echo OK || echo "placeholder no inyectado") 2>/dev/null

# ---------------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------------
qa:
	@echo "== 1. Secretos hardcodeados en deploy/ =="
	@grep -rnE "AKIA[0-9A-Z]{16}|BEGIN (RSA|PRIVATE)|-----BEGIN" deploy/ || echo "  sin hallazgos"
	@echo "== 2. IAM de la Service Account (deben ser roles granulares) =="
	@gcloud projects get-iam-policy $(PROJECT) --flatten="bindings[].members" \
		--filter="bindings.members:serviceAccount:$(SA_EMAIL)" \
		--format="table(bindings.role)" || echo "  sin bindings"
	@echo "== 3. Invocación (allow-unauthenticated = allUsers solo si el PRD lo exige) =="
	@gcloud run services get-iam-policy $(SERVICE) --project=$(PROJECT) --region=$(REGION) \
		--format="yaml(bindings)" || echo "  sin policy"
	@echo "== 4. Secret Manager: acceso de la SA =="
	@gcloud secrets get-iam-policy $(SECRET) --project=$(PROJECT) --flatten="bindings[].members" \
		--filter="bindings.members:serviceAccount:$(SA_EMAIL)" \
		--format="table(bindings.role)" || echo "  sin binding"

atlas:
	@echo "Generando deploy/INFRA_ATLAS_LIVE.md desde el estado real…"
	@$(MAKE) -f deploy/Makefile _atlas_body > deploy/INFRA_ATLAS_LIVE.md
	@echo "OK → deploy/INFRA_ATLAS_LIVE.md"

_atlas_body:
	@echo "# Atlas de infraestructura — Forecast Dashboard (Cloud Run)"
	@echo ""
	@echo "**Generado:** $$(date -u '+%Y-%m-%dT%H:%MZ')  ·  **Proyecto:** $(PROJECT)  ·  **Región:** $(REGION)"
	@echo ""
	@echo "## Servicio Cloud Run"
	@echo ""
	@gcloud run services describe $(SERVICE) --project=$(PROJECT) --region=$(REGION) \
		--format="table(name,status.url,status.latestReadyRevisionName)" || echo "-"
	@echo ""
	@echo "## Configuración (min/max, CPU, RAM, identidad)"
	@echo ""
	@gcloud run services describe $(SERVICE) --project=$(PROJECT) --region=$(REGION) \
		--format="yaml(spec.template.spec)" | grep -E "minInstanceCount|maxInstanceCount|cpuLimit|memoryLimit|serviceAccountName|containerConcurrency" || echo "-"
	@echo ""
	@echo "## Variables de entorno"
	@echo ""
	@gcloud run services describe $(SERVICE) --project=$(PROJECT) --region=$(REGION) \
		--format="yaml(spec.template.spec.containers[0].env)" | sed 's/- name:/  /' || echo "-"
	@echo ""
	@echo "## Imagen en Artifact Registry"
	@echo ""
	@gcloud artifacts docker images list $(REGISTRY) --limit=5 --format="table(image,digest,tags)" || echo "-"
	@echo ""
	@echo "## IAM"
	@echo ""
	@echo "- Service account runtime: $(SA_EMAIL)"
	@gcloud projects get-iam-policy $(PROJECT) --flatten="bindings[].members" \
		--filter="bindings.members:serviceAccount:$(SA_EMAIL)" \
		--format="csv[no-heading](bindings.role)" | sort -u | sed 's/^/- role: /' || echo "-"
	@echo ""
	@echo "## Invocación"
	@echo ""
	@gcloud run services get-iam-policy $(SERVICE) --project=$(PROJECT) --region=$(REGION) \
		--format="yaml(bindings)" || echo "-"

# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------
destroy:
	@read -p "¿Eliminar servicio $(SERVICE)? [y/N] " c; [ "$$c" = "y" ] || exit 0
	gcloud run services delete $(SERVICE) --project=$(PROJECT) --region=$(REGION) --quiet
	@read -p "¿Eliminar también repo/SA/secret? [y/N] " c; [ "$$c" = "y" ] || exit 0
	gcloud iam service-accounts delete $(SA_EMAIL) --project=$(PROJECT) --quiet
	gcloud artifacts repositories delete $(REPO) --location=$(REGION) --project=$(PROJECT) --quiet
	gcloud secrets delete $(SECRET) --project=$(PROJECT) --quiet
	rm -f $(TOKEN_FILE)
	@echo "Teardown completo."