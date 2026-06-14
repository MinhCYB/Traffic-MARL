"""
main.py — FastAPI server

Endpoints:
    POST /data              ← workers gửi data lên
    GET  /command/{mode}    ← workers poll lệnh
    POST /command           ← dashboard gửi lệnh (start/reset/inject_accident)
    WS   /ws                ← dashboard subscribe realtime data
"""

import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print(f"[422] {exc.errors()}")
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.on_event("startup")
async def startup():
    asyncio.create_task(broadcast_loop())


# ── Run ───────────────────────────────────────────────────────────────────────

# ── Training log endpoint ──────────────────────────────────────────────────────

import csv as _csv
from pathlib import Path
from training.config import LOG_DIR, NUM_EPISODES

@app.get("/logs/{model}")
async def get_training_log(model: str):
    """Đọc CSV training log, trả JSON cho dashboard real-time chart."""
    log_path = LOG_DIR / model / "training_log.csv"
    if not log_path.exists():
        return JSONResponse({"status": "no_data", "rows": [], "total_episodes": NUM_EPISODES})
    try:
        rows = []
        with open(log_path, newline="") as f:
            for row in _csv.DictReader(f):
                rows.append({
                    "episode":          int(row["episode"]),
                    "global_reward":    float(row["global_reward"]),
                    "avg_speed":        float(row["avg_speed"]),
                    "avg_waiting_time": float(row["avg_waiting_time"]),
                    "throughput":       float(row["throughput"]),
                    "epsilon":          float(row["epsilon"]),
                    "loss":             float(row["loss"]) if row.get("loss") else None,
                    "had_accident":     (
                        row.get("had_obstacle", row.get("had_accident", "0")) not in ("0", "False", "")
                    ),
                })
        return JSONResponse({
            "status": "ok",
            "rows": rows,
            "total_episodes": NUM_EPISODES,
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e), "rows": [], "total_episodes": NUM_EPISODES})


if __name__ == "__main__":
    import uvicorn
    from training.config import SERVER_PORT
    uvicorn.run("server.main:app", host="0.0.0.0", port=SERVER_PORT, reload=False)