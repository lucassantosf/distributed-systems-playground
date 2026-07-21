PROTO_DIR := ./shared/protos
OUTPUT_DIR := ./shared/common

.PHONY: proto help

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
