.PHONY: up down build logs health ps migrate

up:
	docker compose up -d --build

down:
	docker compose down -v

build:
	docker compose build

logs:
	docker compose logs -f

health:
	@echo "Checking health..."
	@curl -s http://localhost:8090/health || echo "Orchestrator not responding"
	@echo ""

verify-workers:
	docker compose exec inventory python /app/../../scripts/test_workers.py || python3 scripts/test_workers.py

verify-topology:
	docker compose exec -e RABBITMQ_URL="amqp://guest:guest@rabbitmq:5672/" orchestrator python /scripts/verify_topology.py || python3 scripts/verify_topology.py

verify-api:
	docker compose exec orchestrator python -c "$$(cat scripts/verify_api.py)" || python3 scripts/verify_api.py

verify-happy-path:
	docker compose exec orchestrator python -c "$$(cat scripts/verify_happy_path.py)" || python3 scripts/verify_happy_path.py

verify-compensation:
	docker compose exec orchestrator python -c "$$(cat scripts/verify_compensation.py)" || python3 scripts/verify_compensation.py

verify-timeout:
	docker compose exec orchestrator python -c "$$(cat scripts/verify_timeout.py)" || python3 scripts/verify_timeout.py

verify-idempotency:
	docker compose exec orchestrator python -c "$$(cat scripts/verify_idempotency.py)" || python3 scripts/verify_idempotency.py

test:
	python3 -m unittest discover -s tests -p "test_*.py"

migrate:
	docker compose exec orchestrator alembic upgrade head

ps:
	docker compose ps

