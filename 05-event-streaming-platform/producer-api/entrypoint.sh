#!/bin/bash
# =============================================================================
# entrypoint.sh — Producer API
# =============================================================================
# Garante que as migrations são aplicadas antes de subir a aplicação.
# O loop de retry protege contra casos onde o postgres passa no healthcheck
# mas ainda não aceita conexões de aplicação (race condition comum no startup).
# =============================================================================

set -e

echo "[entrypoint] Aplicando migrations Alembic..."

until alembic upgrade head; do
  echo "[entrypoint] Falha nas migrations. Aguardando 3s e tentando novamente..."
  sleep 3
done

echo "[entrypoint] Migrations aplicadas com sucesso!"
echo "[entrypoint] Iniciando producer-api..."

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
