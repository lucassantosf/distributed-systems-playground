"""
Serviço de reserva de estoque e persistência em db_inventory.
Aplica a garantia de idempotência via event_id.
"""

import logging
from sqlalchemy.orm import Session
from app.models.inventory import InventoryReservation

logger = logging.getLogger(__name__)


def process_order_created_inventory(db: Session, event_data: dict) -> bool:
    """
    Processa o evento OrderCreated:
      1. Checa idempotência (se event_id já existe em db_inventory).
      2. Se novo: reserva o estoque para cada item do pedido e persiste no banco.
      3. Se duplicado: ignora sem erros.

    Returns:
        True se reservas foram gravadas, False se foi ignorado por duplicidade.
    """
    event_id = event_data.get("event_id")
    order_id = event_data.get("order_id")
    payload = event_data.get("payload", {})
    items = payload.get("items", [])

    if not event_id or not order_id or not items:
        logger.warning(f"Evento inválido ou sem itens descartado: {event_data}")
        return False

    # ── 1. Checagem de Idempotência ──────────────────────────────────────────
    existing = db.query(InventoryReservation).filter(InventoryReservation.event_id == event_id).first()
    if existing:
        logger.info(
            f"[IDEMPOTÊNCIA] Evento {event_id} já processado em db_inventory para o pedido {order_id}. Ignorando duplicata."
        )
        return False

    # ── 2. Simular e Registrar Reserva de Estoque ───────────────────────────
    reservations_created = []
    for item in items:
        product_id = item.get("product_id", "DESCONHECIDO")
        product_name = item.get("product_name", "Produto sem nome")
        quantity = item.get("quantity", 1)

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
        logger.info(
            f"📦 [ESTOQUE RESERVADO] Pedido: {order_id} | Produto: {product_name} ({product_id}) | Qtd: {quantity}"
        )

    db.commit()
    logger.info(
        f"✅ {len(reservations_created)} item(ns) de estoque registrados em db_inventory para o pedido {order_id}"
    )

    return True
