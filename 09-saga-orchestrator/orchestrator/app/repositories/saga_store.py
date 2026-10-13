from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


class InMemorySagaStore:
    """
    Store em memória para suportar os endpoints do Card 1.5 antes da
    persistência definitiva via PostgreSQL/SQLAlchemy no Epic 2.
    """
    def __init__(self):
        self.sagas: Dict[str, Dict[str, Any]] = {}
        self.events: Dict[str, List[Dict[str, Any]]] = {}

    def create(self, order_id: str, payload: dict) -> str:
        saga_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        self.sagas[saga_id] = {
            "saga_id": saga_id,
            "order_id": order_id,
            "status": "STARTED",
            "current_step": "ReservarEstoque",
            "started_at": now,
            "completed_at": None,
            "payload": payload,
            "steps": [
                {
                    "name": "ReservarEstoque",
                    "index": 0,
                    "status": "PENDING",
                    "attempts": 0,
                    "started_at": None,
                    "completed_at": None,
                    "duration_ms": None,
                    "error_message": None,
                },
                {
                    "name": "ProcessarPagamento",
                    "index": 1,
                    "status": "PENDING",
                    "attempts": 0,
                    "started_at": None,
                    "completed_at": None,
                    "duration_ms": None,
                    "error_message": None,
                },
                {
                    "name": "DespacharPedido",
                    "index": 2,
                    "status": "PENDING",
                    "attempts": 0,
                    "started_at": None,
                    "completed_at": None,
                    "duration_ms": None,
                    "error_message": None,
                },
                {
                    "name": "NotificarCliente",
                    "index": 3,
                    "status": "PENDING",
                    "attempts": 0,
                    "started_at": None,
                    "completed_at": None,
                    "duration_ms": None,
                    "error_message": None,
                },
            ],
        }

        self.events[saga_id] = [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "SagaStarted",
                "step": None,
                "created_at": now,
                "payload": {"order_id": order_id},
            }
        ]

        return saga_id

    def get_by_id(self, saga_id: str) -> Optional[Dict[str, Any]]:
        return self.sagas.get(saga_id)

    def list_all(
        self,
        status: Optional[str] = None,
        order_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        results = list(self.sagas.values())

        if status:
            results = [s for s in results if s["status"] == status]
        if order_id:
            results = [s for s in results if s["order_id"] == order_id]

        results.sort(key=lambda s: s["started_at"], reverse=True)
        return results[offset : offset + limit]

    def get_events(self, saga_id: str) -> List[Dict[str, Any]]:
        return self.events.get(saga_id, [])


saga_store = InMemorySagaStore()

