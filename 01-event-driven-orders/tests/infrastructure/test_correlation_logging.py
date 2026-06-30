import json
import logging
from unittest.mock import patch

from src.infrastructure.messaging.publisher import publish_order_created


def test_publish_order_created_includes_correlation_id(caplog):
    with patch("src.infrastructure.messaging.publisher.pika.BlockingConnection") as mock_connection:
        channel = mock_connection.return_value.channel.return_value

        with caplog.at_level(logging.INFO, logger="src.infrastructure.messaging.publisher"):
            publish_order_created(123, correlation_id="corr-123")

    assert any(
        getattr(record, "correlation_id", None) == "corr-123" and getattr(record, "event", None) == "order_created"
        for record in caplog.records
    )


def test_publish_order_created_payload_contains_correlation_id():
    with patch("src.infrastructure.messaging.publisher.pika.BlockingConnection") as mock_connection:
        channel = mock_connection.return_value.channel.return_value

        publish_order_created(123, correlation_id="corr-123")

    payload = json.loads(channel.basic_publish.call_args.kwargs["body"])
    assert payload["correlation_id"] == "corr-123"
