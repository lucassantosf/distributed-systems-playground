#!/bin/bash
# =============================================================================
# scripts/watch-consumer-groups.sh — Monitora Consumer Groups em tempo real
# =============================================================================
# Card 10 — Configurar Partitions
#
# Para cada Consumer Group ativo exibe:
#   - Tópico e Partição consumida
#   - Offset atual, LOG-END-OFFSET e LAG (mensagens pendentes)
#
# Uso:
#   ./scripts/watch-consumer-groups.sh            # snapshot único
#   ./scripts/watch-consumer-groups.sh --watch    # atualiza a cada 3s (Ctrl+C para parar)
# =============================================================================

CONTAINER="${KAFKA_CONTAINER:-kafka}"
WATCH_MODE=false
TMPFILE=$(mktemp)

if [ "$1" == "--watch" ]; then
  WATCH_MODE=true
fi

cleanup() { rm -f "$TMPFILE"; }
trap cleanup EXIT

run_once() {
  printf "============================================================\n"
  printf "📡 Consumer Groups — %s\n" "$(date '+%H:%M:%S')"
  printf "============================================================\n"

  # Salva em arquivo temporário para evitar expansão aritmética do subshell $()
  docker exec "$CONTAINER" bash -c \
    "kafka-consumer-groups --bootstrap-server kafka:9092 --list 2>/dev/null" \
    | tr -d '\r' | grep -v "^$" > "$TMPFILE"

  if [ ! -s "$TMPFILE" ]; then
    printf "\n⚠️  Nenhum Consumer Group ativo encontrado.\n"
    printf "   Dica: suba o notification-consumer e publique alguns eventos.\n"
    return
  fi

  while IFS= read -r group; do
    printf "\n┌─ Consumer Group: %s\n" "$group"
    printf "│\n"

    GROUPFILE=$(mktemp)
    docker exec "$CONTAINER" bash -c \
      "kafka-consumer-groups --bootstrap-server kafka:9092 --describe --group '$group' 2>/dev/null" \
      | tr -d '\r' | grep -v "^$" | tail -n +2 > "$GROUPFILE"

    if [ ! -s "$GROUPFILE" ]; then
      printf "│  (sem partições atribuídas — consumidor pode estar offline)\n"
    else
      while IFS= read -r line; do
        read -r grp topic partition current_offset log_end_offset lag rest <<< "$line"
        printf "│  %-22s | Partition: %-3s | Offset: %-8s | LogEnd: %-8s | Lag: %-5s\n" \
          "$topic" "$partition" "$current_offset" "$log_end_offset" "$lag"
      done < "$GROUPFILE"
    fi
    rm -f "$GROUPFILE"

    printf "└─────────────────────────────────────────────────────────────\n"
  done < "$TMPFILE"

  printf "\n"
}

if $WATCH_MODE; then
  printf "Modo watch ativado — atualizando a cada 3s. Pressione Ctrl+C para parar.\n\n"
  while true; do
    clear
    run_once
    sleep 3
  done
else
  run_once
  printf "💡 Dica: execute com --watch para monitorar em tempo real:\n"
  printf "   ./scripts/watch-consumer-groups.sh --watch\n"
fi
