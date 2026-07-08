import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.connection_manager import ConnectionManager
from app.database import test_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat")

app = FastAPI()
manager = ConnectionManager()


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