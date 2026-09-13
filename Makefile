.PHONY: dev test lint typecheck up down format
dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
test:
	uv run pytest -q
lint:
	uv run ruff check .
typecheck:
	uv run mypy app
format:
	uv run ruff format .
up:
	docker compose up --build
down:
	docker compose down
