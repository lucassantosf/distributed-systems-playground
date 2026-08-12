"""
Serviço de envio e persistência de notificações.
Aplica a garantia de idempotência via event_id.
"""

import logging
from sqlalchemy.orm import Session
from app.models.notification import Notification

logger = logging.getLogger(__name__)


def process_order_created_notification(db: Session, event_data: dict) -> bool:
    """
    Processa o evento OrderCreated:
      1. Checa idempotência (se event_id já existe em db_notification).
      2. Se novo: simula disparo de e-mail e registra notificação no banco.
      3. Se duplicado: ignora sem erros.

    Returns:
        True se notificação foi enviada/registrada, False se foi ignorada por duplicidade.
    """
    event_id = event_data.get("event_id")
    order_id = event_data.get("order_id")
    payload = event_data.get("payload", {})
    customer_email = payload.get("customer_email")

    if not event_id or not order_id or not customer_email:
        logger.warning(f"Evento inválido ou incompleto descartado: {event_data}")
        return False

    # ── 1. Checagem de Idempotência ──────────────────────────────────────────
    existing = db.query(Notification).filter(Notification.event_id == event_id).first()
    if existing:
        logger.info(
            f"[IDEMPOTÊNCIA] Evento {event_id} já processado anteriormente para o pedido {order_id}. Ignorando duplicata."
        )
        return False

    # ── 2. Simular disparo de e-mail ─────────────────────────────────────────
    total_amount = payload.get("total_amount")
    currency = payload.get("currency", "BRL")
    items_qty = len(payload.get("items", []))

    message = (
        f"Olá! Seu pedido {order_id} com {items_qty} item(ns) no valor total de "
        f"{currency} {total_amount} foi recebido com sucesso!"
    )

    # Simulação do envio físico de e-mail (Log com destaque)
    logger.info(f"📧 [E-MAIL ENVIADO] Para: {customer_email} | Conteúdo: {message}")

    # ── 3. Persistir no PostgreSQL (db_notification) ─────────────────────────
    notification = Notification(
        order_id=order_id,
        event_id=event_id,
        customer_email=customer_email,
        message=message,
    )
    db.add(notification)
    db.commit()
    logger.info(f"✅ Notificação registrada em db_notification | notification_id={notification.id}")

    return True
