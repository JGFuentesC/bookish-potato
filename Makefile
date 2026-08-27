SHELL := /bin/bash
.DEFAULT_GOAL := help

GO   := go
UV   := uv
PNPM := pnpm

# Comandos por defecto de cada módulo (se ajustan en epicas posteriores)
.PHONY: help bootstrap verify lint test fmt clean \
	data-pull ingest bronze silver gold serve \
	eval demo report lineage model \
	migrate-up migrate-down ingest-report ingest-360 \
	up down restart logs ps

help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

bootstrap: ## Instala las dependencias de los cuatro modulos
	cd backend && $(GO) mod download
	cd data-platform && $(UV) sync
	cd ai-sidecar && $(UV) sync
	cd frontend && $(PNPM) install

verify: lint test ## Lint + test de los cuatro modulos (DoD-G)

lint: ## Lint de los cuatro modulos
	cd backend && $(GO) vet ./...
	cd data-platform && $(UV) run ruff check .
	cd ai-sidecar && $(UV) run ruff check .
	cd frontend && $(PNPM) lint

test: ## Test de los cuatro modulos
	cd backend && $(GO) test ./...
	cd data-platform && $(UV) run pytest
	cd ai-sidecar && $(UV) run pytest
	cd frontend && $(PNPM) test

fmt: ## Formatea Go y Python (frontend: sin formateador configurado en E0)
	cd backend && $(GO) fmt ./...
	cd data-platform && $(UV) run ruff format .
	cd ai-sidecar && $(UV) run ruff format .

clean: ## Limpia artefactos generados
	cd backend && $(GO) clean
	cd data-platform && $(UV) run pytest --cache-clear && rm -rf .pytest_cache .ruff_cache .mypy_cache
	cd ai-sidecar && $(UV) run pytest --cache-clear && rm -rf .pytest_cache .ruff_cache .mypy_cache
	rm -rf frontend/dist

# ---- Pipeline de datos (implementado en E1/E2) ----

define STUB
	@echo "?? make $(1): no implementado todavia (ver docs/PRD.md)"
	@exit 1
endef

SCOPE ?= subset

data-pull: ## Baja el subset/full de StatsBomb a data/raw (E1-H2, uso: make data-pull SCOPE=full)
	cd data-platform && $(UV) run python -m genbi_data.ingest.fetch --scope $(SCOPE)

ingest: ## Ingesta de datos validados a OLTP (E1-H3, uso: make ingest SCOPE=subset)
	cd data-platform && $(UV) run python -m genbi_data.ingest --scope $(SCOPE)

bronze: ## Construye capa bronze (E1)
	$(call STUB,bronze)

silver: ## Construye capa silver (E2)
	$(call STUB,silver)

gold: ## Construye capa gold (E2)
	$(call STUB,gold)

serve: ## Sirve la app (E0-H2): construye, levanta y espera healthchecks
	$(COMPOSE) up -d --build --wait

eval: ## Ejecuta el arnes de evaluacion del agente (E3)
	$(call STUB,eval)

demo: ## Levanta el demo end-to-end (E7)
	$(call STUB,demo)

report: ## Genera el reporte del arnes de evaluacion (E3)
	$(call STUB,report)

lineage: ## Genera el lineage del lakehouse (E2)
	$(call STUB,lineage)

model: ## Entrena/valida un modelo (E4, uso: make model MODEL=fct_shot)
	$(call STUB,model)

# ---- Migraciones OLTP (E1-H1) ----

MIGRATE_IMG := migrate/migrate:v4.19.1
PG_NETWORK ?= genbi_default
PG_HOST := postgres
PG_PORT := 5432
MIGRATE = docker run --rm \
	-v $(CURDIR)/data-platform/migrations:/migrations \
	--network $(PG_NETWORK) \
	-e PGPASSWORD=$(POSTGRES_PASSWORD) \
	$(MIGRATE_IMG) -path /migrations \
	-database "postgres://$(POSTGRES_USER)@$(PG_HOST):$(PG_PORT)/$(POSTGRES_DB)?sslmode=disable"

migrate-up: ## Aplica migraciones OLTP (E1-H1)
	$(COMPOSE) up -d --wait postgres
	$(MIGRATE) up

migrate-down: ## Revierte migraciones OLTP (E1-H1)
	$(COMPOSE) up -d --wait postgres
	$(MIGRATE) down -all

ingest-report: ## Reporte de ingesta OLTP (E1-H3)
	cd data-platform && $(UV) run python -m genbi_data.ingest.report

ingest-360: ## Ingesta de datos 360 (E1)
	$(call STUB,ingest-360)

# ---- Compose (E0-H2) ----

COMPOSE := docker compose -f infra/docker-compose.yml

up: ## Levanta contenedores (E0-H2)
	$(COMPOSE) up -d --build

down: ## Mata contenedores (E0-H2)
	$(COMPOSE) down

restart: ## Reinicia contenedores (E0-H2)
	$(COMPOSE) restart

logs: ## Logs de contenedores (E0-H2, uso: make logs SERVICE=app)
	$(COMPOSE) logs -f $(SERVICE)

ps: ## Estado de contenedores (E0-H2)
	$(COMPOSE) ps
