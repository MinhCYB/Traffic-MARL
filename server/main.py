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

# ── Comm counter cho GAT worker ───────────────────────────────────────────────
_gat_total_comm: int   = 0
_gat_steps_with_comm: int = 0   # số step đã nhận comm_this_step > 0 (để tính avg)

# pending_cmds: mỗi worker giữ command của riêng mình.
# Chỉ clear khi chính worker đó đã poll — không bị worker khác clear mất.
pending_cmds: dict[str, str | None] = {mode: None for mode in WORKER_MODES}

# Barrier cho lệnh "start" và "reset":
# Server chỉ trả command cho worker khi TẤT CẢ workers đang ALIVE đã poll
# (đảm bảo mọi worker nhận lệnh đồng thời và bắt đầu cùng step 0).
#
# "Alive" = đã từng poll /command trong vòng BARRIER_TTL giây gần nhất.
# Điều này cho phép chạy 1, 2, hoặc 3 workers tùy ý — không bị deadlock.
#
# Cơ chế:
#   1. Dashboard POST /command  → lưu cmd + reset barrier
#   2. Mỗi worker GET /command/{mode} → cập nhật _alive_seen[mode], chưa trả cmd
#   3. Khi đủ tất cả alive workers poll → release cmd cho tất cả cùng lúc
#
# Lệnh inject_accident / clear_accident KHÔNG dùng barrier (cần tức thì).

import time as _time

_BARRIER_CMDS = {"start", "reset"}
_BARRIER_TTL  = 30.0   # giây — worker được coi là alive nếu poll trong vòng này

_barrier_cmd:      str | None      = None
_barrier_target:   set[str]        = set()   # snapshot alive workers TẠI LÚC gửi lệnh — cố định
_barrier_ready:    set[str]        = set()
_barrier_release:  dict[str, bool] = {mode: False for mode in WORKER_MODES}
_alive_seen:       dict[str, float] = {}   # mode → timestamp lần poll gần nhất


# ── Worker endpoints ──────────────────────────────────────────────────────────

@app.post("/data")
async def receive_data(payload: WorkerPayload):
    """
    Worker gửi data sau mỗi DELTA_TIME giây.

    Có 2 loại payload:
      - Simulation data: có đầy đủ intersections + metrics → push vào sync_buffer để broadcast.
      - Event-only (vd: episode_done): chỉ có mode/step/event → bỏ qua, không push.
    """
    if payload.intersections is not None and payload.metrics is not None:
        # Tích lũy comm stats cho GAT worker
        if payload.mode == "gat_marl" and payload.comm_this_step is not None:
            global _gat_total_comm, _gat_steps_with_comm
            _gat_total_comm      += payload.comm_this_step
            _gat_steps_with_comm += 1
        await sync_buffer.push(payload.mode, payload.dict())
    else:
        # Event-only payload (episode_done, v.v.) — log nhẹ, không broadcast
        print(f"[server] Event from {payload.mode}: {payload.event} (step={payload.step})")
    return {"ok": True}


@app.get("/command/{mode}")
async def get_command(mode: str):
    """
    Worker poll lệnh.

    - Lệnh thông thường (inject_accident, clear_accident): trả về và clear ngay.
    - Lệnh barrier (start, reset): ghi nhận worker đã ready;
      khi đủ tất cả workers poll → release đồng thời cho mọi worker.
    """
    global _barrier_cmd, _barrier_target, _barrier_ready, _barrier_release, _alive_seen

    # Cập nhật alive timestamp cho worker này mỗi khi poll
    _alive_seen[mode] = _time.time()

    # ── 1. Kiểm tra có lệnh barrier đang pending không ──────────────────────
    if _barrier_cmd is not None:
        _barrier_ready.add(mode)

        # _barrier_target được snapshot cố định lúc dashboard gửi lệnh.
        # Không tính lại ở đây — tránh race condition khi worker release
        # sớm làm thay đổi alive_modes giữa chừng.
        if _barrier_ready >= _barrier_target:
            for m in _barrier_target:
                _barrier_release[m] = True
            _barrier_cmd   = None
            _barrier_ready = set()

        if _barrier_release.get(mode):
            _barrier_release[mode] = False
            return {"command": pending_cmds[mode]}
        else:
            return {"command": None}  # chờ worker còn lại

    # ── 2. Lệnh thông thường (inject_accident, clear_accident, v.v.) ─────────
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
        start                      → bắt đầu simulation (barrier)
        reset                      → restart episode (barrier)
        inject_accident:<edge_id>  → inject tai nạn tại edge (tức thì)
        clear_accident             → xóa tai nạn (tức thì)
    """
    global _barrier_cmd, _barrier_ready, _barrier_release

    cmd_type = payload.command.split(":")[0]

    for mode in WORKER_MODES:
        pending_cmds[mode] = payload.command

    if cmd_type in _BARRIER_CMDS:
        # Snapshot alive workers TẠI THỜI ĐIỂM NÀY — cố định suốt barrier round.
        # Workers poll sau khoảng này sẽ không được tính vào target.
        now = _time.time()
        alive = {m for m, t in _alive_seen.items() if now - t < _BARRIER_TTL}
        # Nếu chưa có worker nào alive (server vừa khởi động), dùng toàn bộ WORKER_MODES
        _barrier_target  = alive if alive else set(WORKER_MODES)
        _barrier_cmd     = payload.command
        _barrier_ready   = set()
        _barrier_release = {mode: False for mode in WORKER_MODES}
        # Reset step counter để tất cả workers bắt đầu từ step 1 sau khi sync
        _reset_broadcast_step()
        print(f"[server] Barrier set for {_barrier_target} — waiting for all to poll")

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


_broadcast_step: int = 0   # step counter chung — tất cả workers dùng giá trị này


def _reset_broadcast_step():
    """Gọi khi nhận lệnh start/reset để đồng bộ lại step về 0."""
    global _broadcast_step, _gat_total_comm, _gat_steps_with_comm
    _broadcast_step      = 0
    _gat_total_comm      = 0
    _gat_steps_with_comm = 0


async def broadcast_loop():
    """
    Background task — chờ sync_buffer rồi broadcast cho tất cả WS clients.
    Chạy vô hạn song song với FastAPI.

    Server dùng _broadcast_step chung thay vì step từng worker —
    tránh lệch step do thời gian inference khác nhau giữa Fixed-time vs NN models.
    """
    global _broadcast_step
    while True:
        merged = await sync_buffer.wait_and_get()
        if not merged:
            await asyncio.sleep(0.1)
            continue

        # Override step của tất cả workers về cùng giá trị server
        _broadcast_step += 1
        for mode in merged:
            if isinstance(merged[mode], dict):
                merged[mode]["step"] = _broadcast_step

        # Inject comm stats vào GAT payload để dashboard render
        if "gat_marl" in merged and isinstance(merged["gat_marl"], dict):
            avg_comm = (
                round(_gat_total_comm / _gat_steps_with_comm, 1)
                if _gat_steps_with_comm > 0 else 0.0
            )
            merged["gat_marl"]["total_comm"] = _gat_total_comm
            merged["gat_marl"]["avg_comm"]   = avg_comm

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
                    "episode":              int(row["episode"]),
                    "global_reward":        float(row["global_reward"]),
                    "avg_speed":            float(row["avg_speed"]),
                    "avg_waiting_time":     float(row["avg_waiting_time"]),
                    "throughput":           float(row["throughput"]),
                    "epsilon":              float(row["epsilon"]),
                    "loss":                 float(row["loss"]) if row.get("loss") else None,
                    "duration_s":           float(row["duration_s"]) if row.get("duration_s") else None,
                    "learning_rate":         float(row["learning_rate"]) if row.get("learning_rate") else None,
                    "vehicles_teleported":  int(row["vehicles_teleported"]) if row.get("vehicles_teleported") else 0,
                    # had_obstacle (parallel) hoặc had_accident (single) — cùng nghĩa
                    "had_obstacle":         (
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