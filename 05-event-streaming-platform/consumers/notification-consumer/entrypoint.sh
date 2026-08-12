#!/bin/bash
set -e

echo "[entrypoint] Aplicando migrations no db_notification..."

until alembic upgrade head; do
  echo "[entrypoint] Falha nas migrations. Aguardando 3s..."
  sleep 3
done

echo "[entrypoint] Migrations aplicadas com sucesso!"
echo "[entrypoint] Iniciando notification-consumer..."

exec python3 app/main.py
