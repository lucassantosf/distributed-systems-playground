from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from app.database import test_connection

app = FastAPI()


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


@app.websocket("/ws/{room}")
async def websocket_endpoint(websocket: WebSocket, room: str):
    await websocket.accept()
    await websocket.send_text(f"Connected to room: {room}")

    try:
        while True:
            message = await websocket.receive_text()
            await websocket.send_text(f"[{room}] {message}")
    except WebSocketDisconnect:
        print(f"Client disconnected from room {room}")
    except Exception as exc:
        print(f"WebSocket error for room {room}: {exc}")