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

data-pull: ## Baja el subset/full de StatsBomb (E1-H3)
	$(call STUB,data-pull)

ingest: ## Ingesta cruda a lakehouse/bronze (E1)
	$(call STUB,ingest)

bronze: ## Construye capa bronze (E1)
	$(call STUB,bronze)

silver: ## Construye capa silver (E2)
	$(call STUB,silver)

gold: ## Construye capa gold (E2)
	$(call STUB,gold)

serve: ## Sirve la app (E0-H2/E5)
	$(call STUB,serve)

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

migrate-up: ## Aplica migraciones OLTP (E1-H1)
	$(call STUB,migrate-up)

migrate-down: ## Revierte migraciones OLTP (E1-H1)
	$(call STUB,migrate-down)

ingest-report: ## Reporte de calidad de ingesta (E1)
	$(call STUB,ingest-report)

ingest-360: ## Ingesta de datos 360 (E1)
	$(call STUB,ingest-360)

# ---- Compose (E0-H2) ----

up: ## Levanta contenedores (E0-H2)
	$(call STUB,up)

down: ## Mata contenedores (E0-H2)
	$(call STUB,down)

restart: ## Reinicia contenedores (E0-H2)
	$(call STUB,restart)

logs: ## Logs de contenedores (E0-H2)
	$(call STUB,logs)

ps: ## Estado de contenedores (E0-H2)
	$(call STUB,ps)
