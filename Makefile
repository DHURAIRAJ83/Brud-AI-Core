.PHONY: setup backend chatbot admin dev test lint format db-init

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
