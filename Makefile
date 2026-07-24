SHELL := /bin/sh

COMPOSE := docker compose -f compose.yaml
FULL_COMPOSE := docker compose -f compose.yaml -f compose.full.yaml

.PHONY: help up up-d full-up full-up-d down full-down logs full-logs ps build full-build test backend-test frontend-test health reset

help:
	@printf '%s\n' \
		'make up             Start backend and persistent PostgreSQL' \
		'make up-d           Start backend in the background' \
		'make full-up        Start backend, PostgreSQL, and frontend' \
		'make full-up-d      Start the full stack in the background' \
		'make down           Stop backend without deleting data' \
		'make full-down      Stop the full stack without deleting data' \
		'make logs           Follow backend logs' \
		'make full-logs      Follow all full-stack logs' \
		'make test           Run backend and frontend container checks' \
		'make health         Check backend and optional frontend health' \
		'make reset          Delete containers and persistent PostgreSQL/uploads'

up:
	$(COMPOSE) up --build

up-d:
	$(COMPOSE) up --build --detach --wait

full-up:
	$(FULL_COMPOSE) up --build

full-up-d:
	$(FULL_COMPOSE) up --build --detach --wait

down:
	$(COMPOSE) down

full-down:
	$(FULL_COMPOSE) down

logs:
	$(COMPOSE) logs --follow backend

full-logs:
	$(FULL_COMPOSE) logs --follow

ps:
	$(FULL_COMPOSE) ps

build:
	$(COMPOSE) build backend

full-build:
	$(FULL_COMPOSE) build

test: backend-test frontend-test

backend-test:
	$(COMPOSE) --profile test run --build --rm backend-test

frontend-test:
	docker build --target test --tag rekakebijakan-frontend-test ./frontend
	docker run --rm rekakebijakan-frontend-test

health:
	@curl --fail --silent http://localhost:$${BACKEND_PORT:-5001}/health
	@printf '\n'
	@if curl --fail --silent http://localhost:$${FRONTEND_PORT:-5173}/ >/dev/null 2>&1; then \
		printf 'frontend: ok\n'; \
	else \
		printf 'frontend: not running (backend-only mode is healthy)\n'; \
	fi

reset:
	@printf 'This deletes the persistent PostgreSQL database and uploaded documents.\n'
	@printf 'Run "make reset-confirm" to continue.\n'

.PHONY: reset-confirm
reset-confirm:
	$(FULL_COMPOSE) down --volumes --remove-orphans
