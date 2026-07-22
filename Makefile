.PHONY: setup backend chatbot admin dev test lint format db-init db-status db-verify db-backup db-upgrade

PYTHON := $(if $(wildcard venv/bin/python),venv/bin/python,python3)

setup:
	./scripts/setup.sh

backend:
	./scripts/run_backend.sh

chatbot:
	./scripts/run_chatbot.sh

admin:
	./scripts/run_admin.sh

dev:
	./scripts/run_all.sh

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

db-init:
	$(PYTHON) -c 'from backend.core.config import get_settings; from backend.database.migrations import initialize_database; initialize_database(get_settings().resolved_database_path)'

db-status:
	$(PYTHON) -m backend.database.migrations status

db-verify:
	$(PYTHON) -m backend.database.migrations verify

db-backup:
	$(PYTHON) -m backend.database.migrations backup

db-upgrade:
	$(PYTHON) -m backend.database.migrations upgrade
