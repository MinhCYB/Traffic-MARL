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


# ── Stream buffer — vehicle + lights mỗi 1s ──────────────────────────────────
# Lưu snapshot mới nhất từ mỗi worker, broadcast ngay khi nhận
_stream_clients: list[WebSocket] = []
_stream_latest:  dict[str, dict] = {}   # mode → payload mới nhất


@app.post("/stream")
async def receive_stream(request: Request):
    """
    Worker POST substep snapshot (vehicles + lights) mỗi 1s sim-time.
    Broadcast ngay lập tức cho tất cả /ws/stream clients — không cần barrier.
    """
    payload = await request.json()
    mode = payload.get("mode")
    if not mode:
        return {"ok": False, "error": "missing mode"}

    _stream_latest[mode] = payload

    # Broadcast ngay cho tất cả stream clients
    dead = []
    for ws in _stream_clients:
        try:
            await ws.send_json({"stream": _stream_latest})
        except Exception:
            dead.append(ws)
    for ws in dead:
        _stream_clients.remove(ws)

    return {"ok": True}


@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    """
    Dashboard subscribe vào đây để nhận vehicle + light data mỗi ~1s.
    Tách biệt hoàn toàn với /ws (vẫn giữ cho metrics + attention mỗi 5s).
    """
    await ws.accept()
    _stream_clients.append(ws)
    # Gửi snapshot hiện tại ngay lúc connect để FE có data liền
    if _stream_latest:
        try:
            await ws.send_json({"stream": _stream_latest})
        except Exception:
            pass
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in _stream_clients:
            _stream_clients.remove(ws)


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

# ── Training / finetune log endpoints ────────────────────────────────────────

import csv as _csv
import json as _json
from pathlib import Path
from training.config import ROOT_DIR, LOG_DIR, NUM_EPISODES

# Field order chuẩn — fallback khi file CSV bị thiếu header (vd: file log cũ bị
# ghi đè do log_file_mode detect sai resume). Phải khớp fieldnames trong
# training/train.py và training/train_parallel.py.
_DEFAULT_FIELDNAMES = [
    "episode", "worker_id", "total_steps", "global_reward",
    "avg_speed", "avg_waiting_time", "throughput",
    "loss", "epsilon", "duration_s",
    "had_obstacle", "obstacle_edges", "obstacle_count",
    "vehicles_teleported", "learning_rate",
]


def _read_log_csv(path: Path) -> tuple[dict, list[dict]]:
    """
    Đọc 1 file log CSV (training_log.csv hoặc finetune_log.csv).
    - Skip các dòng comment '#...' ở đầu file (metadata finetune_from/topology).
    - Fallback dùng _DEFAULT_FIELDNAMES nếu file thiếu header.
    Trả (metadata: dict, rows: list[dict]) — rows giữ format response cũ (không đổi
    để FE hiện tại không bị break).
    """
    if not path.exists():
        return {}, []

    meta: dict = {}
    data_lines: list[str] = []
    with open(path, newline="") as f:
        for line in f:
            stripped = line.lstrip()
            if stripped.startswith("#"):
                body = stripped[1:].strip()
                if ":" in body:
                    k, _, v = body.partition(":")
                    meta[k.strip()] = v.strip()
                continue
            data_lines.append(line)

    if not data_lines:
        return meta, []

    first_field = data_lines[0].split(",", 1)[0].strip()
    if first_field == "episode":
        reader = _csv.DictReader(data_lines)
    else:
        reader = _csv.DictReader(data_lines, fieldnames=_DEFAULT_FIELDNAMES)

    rows = []
    for row in reader:
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
    return meta, rows


@app.get("/logs/merged.json")
async def get_merged_logs():
    """
    Serve logs/merged.json (output của scripts/merge_logs.py) cho dashboard CompareTab.

    QUAN TRỌNG: route này phải đứng TRƯỚC @app.get("/logs/{model}") ở dưới — nếu
    không FastAPI sẽ match "merged.json" như path-param {model} và trả no_data nhầm
    (bug cũ: trước đây không có route riêng, request bị /logs/{model} nuốt mất).
    """
    merged_path = ROOT_DIR / "logs" / "merged.json"
    if not merged_path.exists():
        return JSONResponse(
            {"error": "merged.json chưa tồn tại — chạy scripts/merge_logs.py trước"},
            status_code=404,
        )
    try:
        with open(merged_path, encoding="utf-8") as f:
            return JSONResponse(_json.load(f))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/logs/{model}")
async def get_training_log(model: str):
    """
    Đọc CSV training log (+ finetune log nếu có), trả JSON cho dashboard real-time chart.

    Response:
        status, rows, total_episodes               — giữ nguyên như cũ (backward compat)
        has_finetune: bool                          — true nếu model này có finetune_log.csv
        finetune_meta: {finetune_from, topology}    — chỉ có khi has_finetune=true
        finetune_data: [...]                        — chỉ có khi has_finetune=true
    """
    model_dir     = LOG_DIR / model
    train_path    = model_dir / "training_log.csv"
    finetune_path = model_dir / "finetune_log.csv"
    has_finetune  = finetune_path.exists()

    try:
        _, rows = _read_log_csv(train_path)
        result = {
            "status": "ok" if rows else "no_data",
            "rows": rows,
            "total_episodes": NUM_EPISODES,
            "has_finetune": has_finetune,
        }
        if has_finetune:
            ft_meta, ft_rows = _read_log_csv(finetune_path)
            result["finetune_meta"] = {
                "finetune_from": ft_meta.get("finetune_from"),
                "topology":      ft_meta.get("topology"),
            }
            result["finetune_data"] = ft_rows
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse({
            "status": "error", "message": str(e), "rows": [],
            "total_episodes": NUM_EPISODES, "has_finetune": has_finetune,
        })


if __name__ == "__main__":
    import uvicorn
    from training.config import SERVER_PORT
    uvicorn.run("server.main:app", host="0.0.0.0", port=SERVER_PORT, reload=False)