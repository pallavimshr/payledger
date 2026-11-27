# Shortcuts. Run `make help` to list them.
.PHONY: help db db-down migrate seed dev test test-pg retry worker fake-payment

help:
	@echo "make db       - start Postgres in Docker"
	@echo "make db-down  - stop Postgres"
	@echo "make migrate  - create/update database tables"
	@echo "make seed     - add the default chart of accounts"
	@echo "make dev      - run the API at http://localhost:8000/docs"
	@echo "make test     - run the test suite (fast, SQLite)"
	@echo "make test-pg  - run tests on a separate Postgres test DB (incl. race tests)"
	@echo "make retry    - retry failed/pending webhook events once"
	@echo "make worker   - keep retrying webhook events every 10s"
	@echo "make fake-payment - send a signed fake Razorpay payment (Rs 1000)"

db:
	docker compose up -d --wait

db-down:
	docker compose down

migrate:
	cd backend && uv run alembic upgrade head

seed:
	cd backend && uv run python -m app.seed

dev:
	cd backend && uv run uvicorn app.main:app --reload

test:
	cd backend && uv run pytest -q

# Uses its own database (payledger_test) so tests never wipe your dev data.
test-pg: db
	@docker exec payledger-db psql -U payledger -tc "SELECT 1 FROM pg_database WHERE datname='payledger_test'" | grep -q 1 || \
		docker exec payledger-db psql -U payledger -c "CREATE DATABASE payledger_test"
	cd backend && TEST_DATABASE_URL=postgresql+psycopg://payledger:payledger@localhost:5432/payledger_test uv run pytest -q

retry:
	cd backend && uv run python -m app.worker

worker:
	cd backend && uv run python -m app.worker --loop

fake-payment:
	cd backend && uv run python scripts/fake_razorpay.py payment --amount 1000
