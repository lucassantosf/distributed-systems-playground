import json
import logging
import unittest

from app.logging_config import JsonFormatter


class JsonLoggingTests(unittest.TestCase):
    def test_chat_message_log_contains_conversation_fields(self) -> None:
        record = logging.getLogger("test").makeRecord(
            "test",
            logging.INFO,
            __file__,
            1,
            "Chat message published",
            (),
            None,
            extra={
                "event": "chat_message",
                "room": "general",
                "username": "Alice",
                "message_id": 42,
                "content": "hello",
            },
        )

        payload = json.loads(JsonFormatter().format(record))

        self.assertEqual(payload["event"], "chat_message")
        self.assertEqual(payload["room"], "general")
        self.assertEqual(payload["username"], "Alice")
        self.assertEqual(payload["message_id"], 42)
        self.assertEqual(payload["content"], "hello")


if __name__ == "__main__":
    unittest.main()