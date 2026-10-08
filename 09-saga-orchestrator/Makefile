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

ps:
	docker compose ps

