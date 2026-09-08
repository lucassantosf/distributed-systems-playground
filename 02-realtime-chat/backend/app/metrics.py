from prometheus_client import Counter, Gauge, Histogram


HTTP_REQUESTS_TOTAL = Counter(
    "chat_http_requests_total",
    "Total de requests HTTP recebidos pelo backend.",
    ("method", "route", "status"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "chat_http_request_duration_seconds",
    "Duracao dos requests HTTP do backend em segundos.",
    ("method", "route"),
)

WEBSOCKET_CONNECTIONS_TOTAL = Counter(
    "chat_websocket_connections_total",
    "Total de conexoes WebSocket abertas e encerradas.",
    ("event",),
)
ACTIVE_CONNECTIONS = Gauge(
    "chat_active_connections",
    "Quantidade atual de conexoes WebSocket ativas.",
)
ACTIVE_ROOMS = Gauge(
    "chat_active_rooms",
    "Quantidade atual de salas com pelo menos uma conexao.",
)
ROOMS_SEEN_TOTAL = Counter(
    "chat_rooms_seen_total",
    "Quantidade de salas distintas observadas desde o inicio do processo.",
)
MESSAGES_TOTAL = Counter(
    "chat_messages_total",
    "Total de mensagens de chat recebidas e persistidas.",
    ("event",),
)
HEARTBEAT_TIMEOUTS_TOTAL = Counter(
    "chat_heartbeat_timeouts_total",
    "Total de conexoes removidas por timeout de heartbeat.",
)

_seen_rooms: set[str] = set()


def record_room_seen(room: str) -> None:
    if room not in _seen_rooms:
        _seen_rooms.add(room)
        ROOMS_SEEN_TOTAL.inc()


def record_connection_opened() -> None:
    WEBSOCKET_CONNECTIONS_TOTAL.labels(event="connected").inc()
    ACTIVE_CONNECTIONS.inc()


def record_connection_closed() -> None:
    WEBSOCKET_CONNECTIONS_TOTAL.labels(event="disconnected").inc()
    ACTIVE_CONNECTIONS.dec()


def record_message(event: str) -> None:
    MESSAGES_TOTAL.labels(event=event).inc()


def record_heartbeat_timeout() -> None:
    HEARTBEAT_TIMEOUTS_TOTAL.inc()


def set_presence(*, connections: int, rooms: int) -> None:
    ACTIVE_CONNECTIONS.set(connections)
    ACTIVE_ROOMS.set(rooms)