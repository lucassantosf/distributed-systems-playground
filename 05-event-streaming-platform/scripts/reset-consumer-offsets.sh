#!/bin/bash
# =============================================================================
# scripts/reset-consumer-offsets.sh — Reseta Offsets de Consumer Groups
# =============================================================================
# Card 17 & Card 18 — Redefinição de Offsets e Replay
#
# Uso:
#   ./scripts/reset-consumer-offsets.sh <GROUP_ID> <TOPIC> [--to-earliest | --to-latest] [--execute]
#
# Exemplo:
#   ./scripts/reset-consumer-offsets.sh notification-group orders.created --to-earliest --execute
# =============================================================================

CONTAINER="${KAFKA_CONTAINER:-kafka}"
GROUP_ID="${1:-notification-group}"
TOPIC="${2:-orders.created}"
RESET_MODE="${3:---to-earliest}"
EXECUTE_FLAG="${4:---execute}"

if [ -z "$GROUP_ID" ] || [ -z "$TOPIC" ]; then
  echo "Uso: $0 <GROUP_ID> <TOPIC> [--to-earliest|--to-latest] [--execute]"
  exit 1
fi

echo "=================================================================="
echo "🔄 Reset de Offset Kafka"
echo "  Grupo:  $GROUP_ID"
echo "  Tópico: $TOPIC"
echo "  Modo:   $RESET_MODE"
echo "=================================================================="

# Nota: O consumidor PRECISA estar offline para resetar offset
docker exec "$CONTAINER" kafka-consumer-groups \
  --bootstrap-server kafka:9092 \
  --group "$GROUP_ID" \
  --topic "$TOPIC" \
  --reset-offsets \
  "$RESET_MODE" \
  "$EXECUTE_FLAG"

echo "=================================================================="
echo "✅ Operação de reset concluída!"
