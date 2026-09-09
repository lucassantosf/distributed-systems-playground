import asyncio
import json
import logging
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from app.infrastructure.database import ensure_schema, test_connection
from app.logging_config import setup_logging
from app.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
    record_connection_closed,
    record_connection_opened,
    record_heartbeat_timeout,
    record_message,
    record_room_seen,
    set_presence,
)
from app.services.connection_manager import ConnectionManager
from app.services.message_service import MessageService
from app.services.redis_publisher import RedisPublisher
from app.services.redis_subscriber import RedisSubscriber

logger = setup_logging()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def record_http_metrics(request: Request, call_next):
    started_at = time.perf_counter()
    response = await call_next(request)
    route = request.scope.get("route")
    route_name = getattr(route, "path", request.url.path)
    duration = time.perf_counter() - started_at
    HTTP_REQUESTS_TOTAL.labels(request.method, route_name, str(response.status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(request.method, route_name).observe(duration)
    logger.info(
        "HTTP request completed",
        extra={
            "event": "http_request",
            "method": request.method,
            "route": route_name,
            "status_code": response.status_code,
            "duration_ms": round(duration * 1000, 2),
        },
    )
    return response


manager = ConnectionManager()
message_service = MessageService()
redis_publisher = RedisPublisher()
redis_subscriber = RedisSubscriber(manager)


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Chat backend starting", extra={"event": "service_start"})
    await ensure_schema()
    await redis_subscriber.start()
    asyncio.create_task(manager.start_heartbeat())

@app.get("/")
async def root():
    connected, result = await test_connection()
    if connected:
        return {
            "message": "Backend running",
            "database": "connected",
            "postgres_version": result,
        }
    else:
        return {
            "message": "Backend running",
            "database": "disconnected",
            "error": result,
        }


@app.get("/rooms")
async def rooms():
    return await manager.get_all_rooms()


@app.get("/history/{room}")
async def get_history(room: str):
    messages = await message_service.get_history(room=room)
    return [
        {
            "id": message.id,
            "room": message.room,
            "username": message.username,
            "content": message.content,
            "created_at": message.created_at.isoformat(),
        }
        for message in messages
    ]


@app.websocket("/ws/{room}/{username}")
async def websocket_endpoint(websocket: WebSocket, room: str, username: str):
    await websocket.accept()
    await manager.add_connection(room, username, websocket)
    record_connection_opened()
    record_room_seen(room)
    await _update_presence_metrics()
    logger.info(
        "User joined chat room",
        extra={"event": "chat_join", "room": room, "username": username},
    )

    try:
        await websocket.send_text(f"Connected to room: {room}")

        room_users = await manager.get_room_users(room)
        await websocket.send_text(f"Active users: {', '.join(room_users)}")

        await manager.broadcast_text(
            room,
            f"Active users: {', '.join(room_users)}",
            exclude_username=username,
        )

        await manager.broadcast_text(room, f"System: {username} joined")

        while True:
            message = await websocket.receive_text()

            try:
                data = json.loads(message)
                if data.get("type") == "pong":
                    await manager.update_pong(room, username)
                    continue
            except json.JSONDecodeError:
                pass

            record_message("received")
            persisted_message = await message_service.persist_message(room=room, username=username, content=message)
            record_message("persisted")
            await redis_publisher.publish_message(
                room,
                {
                    "room": room,
                    "username": username,
                    "content": message,
                    "message_id": persisted_message.id,
                },
            )
            record_message("published")
            logger.info(
                "Chat message published",
                extra={
                    "event": "chat_message",
                    "room": room,
                    "username": username,
                    "message_id": persisted_message.id,
                    "content": message,
                    "created_at": getattr(persisted_message, "created_at", None),
                },
            )
    except WebSocketDisconnect:
        await manager.remove_connection(room, username)
        record_connection_closed()
        await _update_presence_metrics()
        logger.info(
            "User left chat room",
            extra={"event": "chat_leave", "room": room, "username": username},
        )
        await _broadcast_updated_users(room)
        await manager.broadcast_text(room, f"System: {username} left")
    except RuntimeError as exc:
        if "disconnect" in str(exc).lower():
            await manager.remove_connection(room, username)
            record_connection_closed()
            await _update_presence_metrics()
            logger.info(
                "User left chat room",
                extra={"event": "chat_leave", "room": room, "username": username},
            )
            await _broadcast_updated_users(room)
            await manager.broadcast_text(room, f"System: {username} left")
        else:
            raise
    except Exception as exc:
        await manager.remove_connection(room, username)
        record_connection_closed()
        await _update_presence_metrics()
        logger.exception(
            "WebSocket error",
            extra={"event": "websocket_error", "room": room, "username": username},
        )
        await _broadcast_updated_users(room)
        await manager.broadcast_text(room, f"System: {username} left")
        raise


async def _broadcast_updated_users(room: str) -> None:
    room_users = await manager.get_room_users(room)
    await manager.broadcast_text(
        room,
        f"Active users: {', '.join(room_users)}",
    )


async def _update_presence_metrics() -> None:
    rooms = await manager.get_all_rooms()
    set_presence(
        connections=sum(len(users) for users in rooms.values()),
        rooms=len(rooms),
    )