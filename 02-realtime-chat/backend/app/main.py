import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.infrastructure.database import ensure_schema, test_connection
from app.services.connection_manager import ConnectionManager
from app.services.message_service import MessageService
from app.services.redis_publisher import RedisPublisher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
manager = ConnectionManager()
message_service = MessageService()
redis_publisher = RedisPublisher()

@app.on_event("startup")
async def startup_event() -> None:
    await ensure_schema()

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

    try:
        await websocket.send_text(f"Connected to room: {room}")
        await websocket.send_text(f"Active users: {', '.join(await manager.get_room_users(room))}")

        while True:
            message = await websocket.receive_text()
            logger.info("[ws][room=%s][user=%s] %s", room, username, message)
            persisted_message = await message_service.persist_message(room=room, username=username, content=message)
            await redis_publisher.publish_message(
                room,
                {
                    "room": room,
                    "username": username,
                    "content": message,
                    "message_id": persisted_message.id,
                },
            )
            await manager.broadcast(room, username, message)
    except WebSocketDisconnect:
        await manager.remove_connection(room, username)
        logger.info("Client disconnected from room %s", room)
    except RuntimeError as exc:
        if "disconnect" in str(exc).lower():
            await manager.remove_connection(room, username)
            logger.info("Client disconnected from room %s", room)
        else:
            raise
    except Exception as exc:
        await manager.remove_connection(room, username)
        logger.exception("WebSocket error for room %s", room)
        raise