"""
main.py — FastAPI server

Endpoints:
    POST /data              ← workers gửi data lên
    GET  /command/{mode}    ← workers poll lệnh
    POST /command           ← dashboard gửi lệnh (start/reset/inject_accident)
    WS   /ws                ← dashboard subscribe realtime data
"""

import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from server.schemas import WorkerPayload, CommandPayload
from server.sync_buffer import SyncBuffer, WORKER_MODES

app = FastAPI(title="Smart Traffic MARL Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── State ─────────────────────────────────────────────────────────────────────
sync_buffer   = SyncBuffer()
ws_clients:   list[WebSocket] = []
pending_cmds: dict[str, str | None] = {mode: None for mode in WORKER_MODES}


# ── Worker endpoints ──────────────────────────────────────────────────────────

@app.post("/data")
async def receive_data(payload: WorkerPayload):
    """Worker gửi data sau mỗi DELTA_TIME giây."""
    await sync_buffer.push(payload.mode, payload.dict())
    return {"ok": True}


@app.get("/command/{mode}")
async def get_command(mode: str):
    """Worker poll lệnh — trả về lệnh pending rồi clear."""
    cmd = pending_cmds.get(mode)
    if cmd:
        pending_cmds[mode] = None
    return {"command": cmd}


# ── Dashboard endpoints ───────────────────────────────────────────────────────

@app.post("/command")
async def send_command(payload: CommandPayload):
    """
    Dashboard gửi lệnh xuống tất cả workers.

    Commands:
        start              → bắt đầu simulation
        reset              → restart episode
        inject_accident:<edge_id>  → inject tai nạn tại edge
    """
    for mode in WORKER_MODES:
        pending_cmds[mode] = payload.command
    return {"ok": True, "command": payload.command}


@app.get("/status")
async def get_status():
    """Trạng thái connection của 3 workers."""
    return sync_buffer.get_status()


# ── WebSocket broadcast ───────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Dashboard connect vào đây để nhận realtime data."""
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            # Giữ connection sống — data được push từ broadcast_loop
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_clients.remove(ws)


async def broadcast_loop():
    """
    Background task — chờ sync_buffer rồi broadcast cho tất cả WS clients.
    Chạy vô hạn song song với FastAPI.
    """
    while True:
        merged = await sync_buffer.wait_and_get()
        if not merged:
            await asyncio.sleep(0.1)
            continue

        broadcast_data = {
            "workers": merged,
            "status":  sync_buffer.get_status(),
        }

        dead = []
        for ws in ws_clients:
            try:
                await ws.send_json(broadcast_data)
            except Exception:
                dead.append(ws)

        for ws in dead:
            ws_clients.remove(ws)


@app.on_event("startup")
async def startup():
    asyncio.create_task(broadcast_loop())


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    from training.config import SERVER_PORT
    uvicorn.run("server.main:app", host="0.0.0.0", port=SERVER_PORT, reload=False)