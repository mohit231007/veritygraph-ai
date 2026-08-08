.PHONY: install backend frontend up down qa qa-fast

install:
	python -m pip install -e ".[dev]"
	npm --prefix frontend install
	npm --prefix e2e install

backend:
	uvicorn app.main:app --app-dir backend --reload

frontend:
	npm --prefix frontend run dev

up:
	docker compose up --build

down:
	docker compose down --remove-orphans

qa-fast:
	python scripts/qa.py

qa:
	python scripts/qa.py --e2e
