#!/bin/bash
set -e

echo "Running migrations..."
alembic upgrade head

echo "Compiling proto files..."
mkdir -p proto/generated
python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./proto/generated \
    --grpc_python_out=./proto/generated \
    ./proto/common/types.proto \
    ./proto/product/product.proto

touch proto/generated/__init__.py
touch proto/generated/common/__init__.py
touch proto/generated/product/__init__.py

find proto/generated -name "*.py" -not -name "__init__.py" -exec sed -i \
    -e 's/from common import/from proto.generated.common import/g' \
    -e 's/from product import/from proto.generated.product import/g' \
    {} \;

echo "Starting gRPC server on port 50052..."
python -c "from grpc_server import serve; serve()" &

echo "Starting FastAPI server on port 8000..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
