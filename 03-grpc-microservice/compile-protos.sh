#!/bin/bash
# Script to compile proto files using Docker
# Usage: ./compile-protos.sh

set -e

PROTO_DIR="./shared/protos"
OUTPUT_DIR="./shared/common/generated"

echo "Compiling proto files..."

mkdir -p "$OUTPUT_DIR"

docker run --rm \
    -v "$(pwd):/workspace" \
    -w /workspace \
    python:3.11-slim \
    bash -c "pip install grpcio-tools -q && \
             python -m grpc_tools.protoc \
             -I./shared/protos \
             --python_out=./shared/common/generated \
             --grpc_python_out=./shared/common/generated \
             ./shared/protos/common/types.proto \
             ./shared/protos/user/user.proto \
             ./shared/protos/product/product.proto \
             ./shared/protos/order/order.proto"

touch "$OUTPUT_DIR/__init__.py"

echo "Proto files compiled successfully!"
echo "Generated files:"
ls -la "$OUTPUT_DIR/"
