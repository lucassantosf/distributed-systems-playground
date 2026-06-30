import logging
from unittest.mock import patch

from src.infrastructure.messaging.publisher import publish_order_created


def test_publish_order_created_logs_structured_event(caplog):
    with patch("src.infrastructure.messaging.publisher.pika.BlockingConnection") as mock_connection:
        channel = mock_connection.return_value.channel.return_value

        with caplog.at_level(logging.INFO, logger="src.infrastructure.messaging.publisher"):
            publish_order_created(123)

    assert any(
        getattr(record, "event", None) == "order_created" and getattr(record, "order_id", None) == 123
        for record in caplog.records
    )
