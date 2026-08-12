#!/bin/bash
# =============================================================================
# scripts/create-topics.sh — Automação de criação de Tópicos no Apache Kafka
# =============================================================================
# Card 7 — Criar Topics por domínio
# Criação explícita dos tópicos do sistema com 3 partições cada.
# =============================================================================

set -e

BOOTSTRAP_SERVER="${KAFKA_BOOTSTRAP_SERVERS:-localhost:29092}"

echo "============================================================"
echo "Criando tópicos no Kafka cluster: $BOOTSTRAP_SERVER"
echo "============================================================"

# Lista de tópicos da plataforma (Domínio de Pedidos)
TOPICS=(
    "orders.created"
    "orders.updated"
    "inventory.reserved"
    "orders.created-retry"
    "orders.created-dlt"
)

PARTITIONS=3
REPLICATION_FACTOR=1

for topic in "${TOPICS[@]}"; do
    echo "Creating topic: '$topic' (Partitions: $PARTITIONS, Replication Factor: $REPLICATION_FACTOR)..."
    docker exec kafka kafka-topics --bootstrap-server kafka:9092 \
        --create --if-not-exists \
        --topic "$topic" \
        --partitions $PARTITIONS \
        --replication-factor $REPLICATION_FACTOR
done

echo ""
echo "============================================================"
echo "Tópicos existentes no cluster:"
echo "============================================================"
docker exec kafka kafka-topics --bootstrap-server kafka:9092 --list

echo "============================================================"
echo "✅ Criação de tópicos concluída com sucesso!"
echo "============================================================"
