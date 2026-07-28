PROTO_DIR := ./shared/protos
OUTPUT_DIR := ./shared/common

.PHONY: proto help logs logs-user logs-product logs-order logs-pretty up down restart

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

proto: ## Compile all proto files and generate Python code
	@echo "Compiling proto files..."
	@mkdir -p $(OUTPUT_DIR)/generated
	@python -m grpc_tools.protoc \
		-I$(PROTO_DIR) \
		--python_out=$(OUTPUT_DIR)/generated \
		--grpc_python_out=$(OUTPUT_DIR)/generated \
		$(PROTO_DIR)/common/types.proto \
		$(PROTO_DIR)/user/user.proto \
		$(PROTO_DIR)/product/product.proto \
		$(PROTO_DIR)/order/order.proto
	@touch $(OUTPUT_DIR)/generated/__init__.py
	@echo "Proto files compiled successfully!"
	@echo "Generated files:"
	@ls -la $(OUTPUT_DIR)/generated/

clean: ## Remove generated proto files
	@echo "Cleaning generated files..."
	@rm -rf $(OUTPUT_DIR)/generated
	@echo "Clean complete!"

logs: ## Show all logs
	@cat ./logs/user-service.log 2>/dev/null || echo "(empty)"
	@cat ./logs/product-service.log 2>/dev/null || echo "(empty)"
	@cat ./logs/order-service.log 2>/dev/null || echo "(empty)"

logs-user: ## Show user-service logs
	@cat ./logs/user-service.log 2>/dev/null || echo "(empty)"

logs-product: ## Show product-service logs
	@cat ./logs/product-service.log 2>/dev/null || echo "(empty)"

logs-order: ## Show order-service logs
	@cat ./logs/order-service.log 2>/dev/null || echo "(empty)"

logs-pretty: ## Show all logs formatted (JSON pretty-print)
	@echo "=== user-service ===" && \
	(cat ./logs/user-service.log 2>/dev/null | python3 -c "import sys,json; [print(json.dumps(json.loads(l),indent=2)) for l in sys.stdin]" 2>/dev/null || echo "(empty)")
	@echo "\n=== product-service ===" && \
	(cat ./logs/product-service.log 2>/dev/null | python3 -c "import sys,json; [print(json.dumps(json.loads(l),indent=2)) for l in sys.stdin]" 2>/dev/null || echo "(empty)")
	@echo "\n=== order-service ===" && \
	(cat ./logs/order-service.log 2>/dev/null | python3 -c "import sys,json; [print(json.dumps(json.loads(l),indent=2)) for l in sys.stdin]" 2>/dev/null || echo "(empty)")

logs-clear: ## Clear all log files
	@rm -rf ./logs
	@mkdir -p ./logs
	@chmod 777 ./logs
	@echo "Logs cleared!"

up: ## Start services (creates ./logs if needed)
	@mkdir -p ./logs && chmod 777 ./logs
	docker compose up -d
	@echo "Services started. Use 'make logs' to view logs."

down: ## Stop services
	docker compose down

restart: ## Restart services
	@mkdir -p ./logs && chmod 777 ./logs
	docker compose restart
