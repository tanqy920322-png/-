.PHONY: up down api web worker test

up:
	docker compose up -d

down:
	docker compose down

api:
	cd apps/api && .venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	cd apps/api && .venv/bin/python -m app.worker

web:
	npm --prefix apps/web run dev

test:
	cd apps/api && .venv/bin/pytest
