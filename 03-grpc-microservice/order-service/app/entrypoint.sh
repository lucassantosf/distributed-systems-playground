#!/bin/bash
set -e

echo "Compiling proto files..."
mkdir -p proto/generated
python -m grpc_tools.protoc \
    -I./proto \
    --python_out=./proto/generated \
    --grpc_python_out=./proto/generated \
    ./proto/common/types.proto \
    ./proto/user/user.proto \
    ./proto/product/product.proto

touch proto/generated/__init__.py
touch proto/generated/common/__init__.py
touch proto/generated/user/__init__.py
touch proto/generated/product/__init__.py

find proto/generated -name "*.py" -not -name "__init__.py" -exec sed -i \
    -e 's/from common import/from proto.generated.common import/g' \
    -e 's/from user import/from proto.generated.user import/g' \
    -e 's/from product import/from proto.generated.product import/g' \
    {} \;

echo "Starting FastAPI server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
