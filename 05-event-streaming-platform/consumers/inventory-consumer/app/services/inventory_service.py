"""
Serviço de reserva de estoque e persistência em db_inventory.
Aplica a garantia de idempotência via event_id.

Card 25: Após reservar o estoque com sucesso, publica o evento InventoryReserved
no tópico 'inventory.reserved' — demonstrando o padrão consumidor-que-também-é-produtor.
"""

import logging
from sqlalchemy.orm import Session
from app.models.inventory import InventoryReservation
from shared.kafka.producer import KafkaProducerWrapper
from shared.schemas.order import InventoryReservedPayload, OrderItem
from shared.utils.event_factory import create_inventory_reserved_event

logger = logging.getLogger(__name__)


def process_order_created_inventory(
    db: Session,
    event_data: dict,
    producer: KafkaProducerWrapper,
) -> bool:
    """
    Processa o evento OrderCreated:
      1. Checa idempotência (se event_id já existe em db_inventory).
      2. Se novo: reserva o estoque para cada item do pedido e persiste no banco.
      3. Publica o evento InventoryReserved no tópico 'inventory.reserved' (Card 25).
      4. Se duplicado: ignora sem erros.

    Returns:
        True se reservas foram gravadas e evento derivado publicado, False se duplicata.
    """
    event_id = event_data.get("event_id")
    order_id = event_data.get("order_id")
    correlation_id = event_data.get("correlation_id")
    payload = event_data.get("payload", {})
    items = payload.get("items", [])

    if not event_id or not order_id or not items:
        logger.warning(f"Evento inválido ou sem itens descartado: {event_data}")
        return False

    # ── 1. Checagem de Idempotência (por event_id, compatível com multi-produto) ───────
    # A constraint UNIQUE(event_id, product_id) permite múltiplos itens por evento.
    # Verificamos se todos os itens do evento já foram reservados.
    existing_count = db.query(InventoryReservation).filter(InventoryReservation.event_id == event_id).count()
    if existing_count >= len(items):
        logger.info(
            f"[IDEMPOTÊNCIA] Evento {event_id} já completamente processado em db_inventory para o pedido {order_id}. Ignorando."
        )
        return False

    # ── 2. Simular e Registrar Reserva de Estoque ───────────────────────────
    reservations_created = []
    reserved_items = []

    for item in items:
        product_id = item.get("product_id", "DESCONHECIDO")
        product_name = item.get("product_name", "Produto sem nome")
        quantity = item.get("quantity", 1)
        unit_price = item.get("unit_price", "0.00")

        reservation = InventoryReservation(
            order_id=order_id,
            event_id=event_id,
            product_id=product_id,
            product_name=product_name,
            quantity_reserved=quantity,
            status="RESERVED",
        )
        db.add(reservation)
        reservations_created.append(reservation)
        reserved_items.append(
            OrderItem(
                product_id=product_id,
                product_name=product_name,
                quantity=quantity,
                unit_price=unit_price,
            )
        )
        logger.info(
            f"📦 [ESTOQUE RESERVADO] Pedido: {order_id} | Produto: {product_name} ({product_id}) | Qtd: {quantity}"
        )

    db.commit()
    logger.info(
        f"✅ {len(reservations_created)} item(ns) de estoque registrados em db_inventory para o pedido {order_id}"
    )

    # ── 3. Publicar InventoryReserved (Card 25) ───────────────────────────────
    # O inventory-consumer torna-se aqui um PRODUTOR de evento derivado.
    # O correlation_id é herdado do OrderCreated original para manter
    # a rastreabilidade da cadeia de eventos:
    #   OrderCreated ──► inventory.reserved (mesmo correlation_id)
    try:
        inventory_payload = InventoryReservedPayload(
            items_reserved=reserved_items,
            warehouse_id="WH-001",
        )
        event = create_inventory_reserved_event(
            order_id=order_id,
            payload=inventory_payload,
            correlation_id=correlation_id,
        )
        producer.produce_event(event)
        producer.flush()
        logger.info(
            f"📡 [EVENTO DERIVADO PUBLICADO] InventoryReserved → topic=inventory.reserved "
            f"| order_id={order_id} | event_id={event.event_id} | correlation_id={correlation_id}"
        )
    except Exception as exc:
        # Falha na publicação do evento derivado não deve reverter a reserva já persistida.
        logger.error(
            f"⚠️  Falha ao publicar InventoryReserved | order_id={order_id} | erro={exc}"
        )

    return True
