#!/bin/bash
set -e

echo "[entrypoint] Aplicando migrations no db_inventory..."

until alembic upgrade head; do
  echo "[entrypoint] Falha nas migrations do db_inventory. Aguardando 3s..."
  sleep 3
done

echo "[entrypoint] Migrations do db_inventory aplicadas com sucesso!"
echo "[entrypoint] Iniciando inventory-consumer..."

exec python3 app/main.py
