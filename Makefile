PYTHON := $(shell test -x .venv/bin/python && echo .venv/bin/python || echo python3)
PIP    := $(shell test -x .venv/bin/pip && echo .venv/bin/pip || echo pip)
COMPOSE := $(shell if docker compose version >/dev/null 2>&1; then echo "docker compose"; elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; else echo "docker compose"; fi)

.PHONY: start tui up down restart logs ps test test-unit test-integration dump release install venv help
.DEFAULT_GOAL := start

# ──────────────── основной воркфлоу ────────────────

start: .venv/bin/python ## restart всего стека и открыть TUI (default)
	@$(COMPOSE) down --remove-orphans 2>&1 | grep -E '(Removed|Removing)' || true
	@$(COMPOSE) up -d --build 2>&1 | grep -E '(Started|Built|Healthy|Error)' || true
	@.venv/bin/python -m devops.app

tui: .venv/bin/python ## только TUI без передёргивания контейнеров
	@.venv/bin/python -m devops.app

.venv/bin/python:
	@$(MAKE) venv

# ──────────────── установка ────────────────

venv: ## создать .venv и поставить туда проект с dev-зависимостями
	python3 -m venv .venv
	./.venv/bin/pip install --upgrade pip
	./.venv/bin/pip install -e ".[dev]"

install: ## pip install -e ".[dev]" в текущий python
	$(PIP) install -e ".[dev]"

# ──────────────── docker-compose ────────────────

up: ## docker compose up -d --build
	$(COMPOSE) up -d --build

down: ## docker compose down
	$(COMPOSE) down

restart: ## docker compose restart
	$(COMPOSE) restart

ps: ## docker compose ps
	$(COMPOSE) ps

logs: ## live-логи всего стека
	$(COMPOSE) logs -f

logs-bot: ## логи bot
	$(COMPOSE) logs -f bot

logs-parser: ## логи parser
	$(COMPOSE) logs -f parser

logs-api: ## логи api
	$(COMPOSE) logs -f api

# ──────────────── тесты ────────────────

test: ## все тесты
	@$(COMPOSE) up -d postgres >/dev/null 2>&1
	@POSTGRES_TEST_HOST=localhost POSTGRES_TEST_PORT=5433 $(PYTHON) -m pytest -v

test-unit: ## юнит без БД
	$(PYTHON) -m pytest tests/unit -v

test-integration: ## integration с postgres
	@$(COMPOSE) up -d postgres >/dev/null 2>&1
	@POSTGRES_TEST_HOST=localhost POSTGRES_TEST_PORT=5433 $(PYTHON) -m pytest tests/integration -v

# ──────────────── seed-дампы ────────────────

dump: ## снять seed-дамп → dist/problems-YYYY-MM-DD.sql.gz
	./scripts/dump-seed.sh

release: ## опубликовать dist/problems.sql.gz на GitHub Releases (TAG=...)
	@if [ -z "$(TAG)" ]; then \
		echo "укажи TAG: make release TAG=seed-$$(date +%Y-%m-%d)"; \
		exit 1; \
	fi
	./scripts/release-seed.sh $(TAG) "$(NOTES)"

# ──────────────── help ────────────────

help: ## показать этот хелп
	@awk 'BEGIN {FS = ":.*?## "}; /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
