PY_SOURCES := src tests scripts skills/music-discovery-architecture/scripts skills/implementation-roadmap/scripts

.PHONY: help lint format type test test-all boundaries imports check check-frontend serve contract contract-check

help:
	@echo "make check       lint + type + test + boundaries + imports"
	@echo "make test        fast tests (slow/live skipped)"
	@echo "make test-all    include slow tests"
	@echo "make format      apply ruff formatting and safe fixes"
	@echo "make serve       run the API (uvicorn, reload) on http://127.0.0.1:8000"
	@echo "make contract    regenerate frontend/openapi.json and the mock fixtures"

lint:
	uv run ruff check $(PY_SOURCES)
	uv run ruff format --check $(PY_SOURCES)

format:
	uv run ruff check --fix $(PY_SOURCES)
	uv run ruff format $(PY_SOURCES)

type:
	uv run mypy
	uv run mypy tests/fakes tests/unit/fakes/test_fakes_conform.py \
		tests/integration/infrastructure/test_repositories.py
	uv run mypy scripts

test:
	uv run pytest

test-all:
	uv run pytest --run-slow

boundaries:
	uv run python skills/music-discovery-architecture/scripts/check_boundaries.py

imports:
	uv run lint-imports

check: lint type test boundaries imports

check-frontend:
	cd frontend && npm run lint && npm run typecheck && npm run test && npm run build

serve:
	uv run uvicorn music_discovery.api.app:create_app --factory --reload --host 127.0.0.1 --port 8000

contract:
	uv run python scripts/export_openapi.py
	uv run python scripts/export_fixtures.py

contract-check:
	uv run python scripts/export_openapi.py --check
	uv run python scripts/export_fixtures.py --check
