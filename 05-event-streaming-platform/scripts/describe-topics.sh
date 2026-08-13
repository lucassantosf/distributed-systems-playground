#!/bin/bash
# =============================================================================
# scripts/describe-topics.sh — Inspeciona tópicos e partições do Kafka
# =============================================================================
# Card 10 — Configurar Partitions
#
# Exibe para cada tópico:
#   - Número de partições e fator de replicação
#   - Líder de cada partição (broker responsável)
#   - Réplicas e ISR (In-Sync Replicas)
#
# Uso:
#   ./scripts/describe-topics.sh
# =============================================================================

set -e

CONTAINER="${KAFKA_CONTAINER:-kafka}"

echo "============================================================"
echo "🔍 Descrição dos Tópicos — Kafka Cluster"
echo "============================================================"
echo ""

# Lista todos os tópicos excluindo os internos do Kafka
TOPICS=$(docker exec "$CONTAINER" kafka-topics \
  --bootstrap-server kafka:9092 \
  --list 2>/dev/null | grep -v "^__")

if [ -z "$TOPICS" ]; then
  echo "⚠️  Nenhum tópico encontrado. Execute ./scripts/create-topics.sh primeiro."
  exit 1
fi

echo "📋 Tópicos encontrados:"
for topic in $TOPICS; do
  echo "   • $topic"
done

echo ""
echo "============================================================"
echo "📊 Detalhes por tópico:"
echo "============================================================"

for topic in $TOPICS; do
  echo ""
  echo "┌─ Tópico: $topic"
  docker exec "$CONTAINER" kafka-topics \
    --bootstrap-server kafka:9092 \
    --describe \
    --topic "$topic" 2>/dev/null \
    | tail -n +2 \
    | awk '{printf "│  Partition: %-4s | Leader: %-4s | Replicas: %-6s | ISR: %s\n", $4, $6, $8, $10}'
  echo "└─────────────────────────────────────────────────────────────"
done

echo ""
echo "============================================================"
echo "✅ Inspecção concluída."
echo "============================================================"
