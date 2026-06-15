# 🚦 Smart Traffic MARL

> **GAT-MARL Traffic Signal Control** — Hệ thống điều khiển đèn giao thông thông minh sử dụng Multi-Agent Reinforcement Learning kết hợp Graph Attention Network.

> Bài tập lớn môn Machine Learning — Mô phỏng mạng lưới giao thông đô thị thực tế, so sánh trực quan 3 phương pháp điều khiển: Fixed-time, IDQN, và GAT-MARL.

> **Môn học:** Machine Learning — HK2, 2025–2026 </br>
> **Trường:** Đại học Công nghệ, ĐHQGHN  </br>
> **Nhóm:** 13

| Tên | MSSV |
|-----|------|
| Đặng Quang Minh | 24022397 |
| Ngô Trọng Hiệp | 24022325 |
| Khổng Quang Huy | 24022355 |

---

## Tổng quan

Hệ thống đèn giao thông truyền thống hoạt động theo chu kỳ cố định, không phản ứng với lưu lượng thực tế. Dự án này xây dựng hệ thống **adaptive traffic signal control** sử dụng Deep RL, giải quyết 3 điểm yếu cốt lõi:

| Vấn đề | Giải pháp |
|--------|-----------|
| Không coordination — mỗi ngã tư chỉ nhìn vào bản thân | GAT layer aggregate thông tin từ neighbors |
| Không scale — thêm ngã tư phải train lại từ đầu | Parameter sharing — toàn bộ agents dùng chung 1 bộ trọng số |
| Non-stationarity — policy thay đổi làm môi trường bất ổn | Shared policy converge đồng đều, giảm instability |

### Kiến trúc mô hình

```
obs_i (queue, density, phase, time_since_change)
    │
    ▼
[Local Encoder — Shared MLP]       # h_i ∈ R^64
    │
    ▼
[GAT Layer — 4 heads]              # aggregate h_j từ neighbors
    │
    ▼
[Q-head — Shared MLP]
    │
    ▼
Q(s, keep) · Q(s, switch) → argmax → Action
```

### Reward function

Hybrid **Waiting Time (70%) + Weighted Pressure (30%)**, normalize về [0, 1] trước khi scale:

```
reward_i = -(α × ŵ_i + β × p̂_i) × REWARD_SCALE

  ŵ_i = min(avg_wait_i, 120) / 120     ← normalize [0,1], clip tại 2 phút
  p̂_i = min(pressure_i, 5.0) / 5.0    ← normalize [0,1], clip tại 5.0
  
  α = 0.7  → waiting time là primary signal (sát tiêu chí HCM 7th Edition)
  β = 0.3  → pressure làm regularizer, tránh spillback
```

### Parallel training (Ape-X style)

```
Workers (CPU, SUMO)         Learner (GPU)
┌──────────────┐            ┌──────────────┐
│ W0  ε = 1.00 │──┐         │              │
│ W1  ε = 0.67 │──┤ Queue   │  Drain →     │
│ W2  ε = 0.33 │──┼────────→│  Buffer →    │
│ W3  ε = 0.10 │──┘         │  Backprop    │
│              │←───────────│  Push weights │
└──────────────┘ pull/80    └──────────────┘
```

<!-- [TODO: screenshot dashboard Live Demo — 3 panels hiển thị Fixed / IDQN / GAT-MARL side-by-side, kèm bản đồ ngã tư, metrics panel, và attention arrows] -->

---

## Cấu trúc dự án

```
Smart-Traffic-MARL/
├── simulation/                  # SUMO map files
│   ├── 2x2/                     # Map synthetic 4 ngã tư (train nhanh)
│   └── mydinh/                  # Map thực tế Mỹ Đình 8 ngã tư
│       ├── net/                 # nod.xml, edg.xml, typ.xml → gen net.xml
│       ├── routes/              # gen_routes.py → peak + night
│       ├── detectors/           # E2 detectors mọi incoming lane
│       └── mydinh.sumocfg
│
├── environment/                 # RL Environment layer
│   ├── traffic_env.py           # SUMO wrapper (TraCI batch subscription)
│   ├── state_builder.py         # Build state vector, STATE_DIM tự tính
│   ├── reward.py                # Hybrid Waiting Time + Weighted Pressure
│   └── maps/                    # Topology data từng map
│       ├── __init__.py          # Auto-load theo config.TOPOLOGY
│       ├── map_2x2.py
│       └── map_mydinh.py
│
├── models/                      # Model definitions (PyTorch + PyG)
│   ├── gat_marl.py              # GAT 4-head + shared Q-head
│   ├── idqn.py                  # Independent DQN baseline
│   └── fixed_time.py            # Fixed cycle baseline
│
├── agents/                      # Agent logic (inference + learning)
│   ├── gat_agent.py
│   ├── idqn_agent.py
│   └── fixed_agent.py
│
├── training/                    # Training pipeline
│   ├── train.py                 # Single-process training
│   ├── train_parallel.py        # Parallel rollout — Ape-X style
│   ├── replay_buffer.py         # Pre-allocated numpy circular buffer
│   ├── scheduler.py             # WarmupScheduler (linear → cosine)
│   └── config.py                # Hyperparams + TOPOLOGY
│
├── workers/                     # 3 process song song cho Live Demo
│   ├── worker_base.py
│   ├── worker_gat.py
│   ├── worker_idqn.py
│   └── worker_fixed.py
│
├── server/                      # FastAPI server — sync + WebSocket
│   ├── main.py
│   ├── sync_buffer.py
│   └── schemas.py
│
├── dashboard/                   # React + Vite web dashboard
│   └── src/
│       ├── components/          # IntersectionGrid, AttentionArrows...
│       ├── hooks/               # useWebSocket
│       └── pages/               # Slides, LiveDemo, Results
│
├── scripts/
│   ├── build_map.py             # Build SUMO net + routes
│   ├── merge_logs.py            # Merge CSV logs → JSON cho dashboard
│   ├── run_training.sh
│   └── run_demo.sh
│
├── docs/
│   └── report.tex               # Báo cáo LaTeX IEEE two-column
│
├── checkpoints/                 # Saved model weights (.pt)
├── logs/                        # Training CSV logs
├── .env                         # SUMO_HOME, ports, server URL
└── requirements.txt
```

---

## Cài đặt

### Yêu cầu

- **Python** 3.10+
- **SUMO** ≥ 1.18 — [Hướng dẫn cài đặt](https://sumo.dlr.de/docs/Installing/index.html)
- **Node.js** ≥ 18 (cho dashboard)
- **GPU** có CUDA (khuyến nghị, không bắt buộc)

### 1. Clone & tạo môi trường

```bash
git clone https://github.com/MinhCYB/Traffic-MARL.git
cd Traffic-MARL

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

### 2. Cài dashboard

```bash
cd dashboard
npm install
cd ..
```

### 3. Thiết lập SUMO_HOME

```bash
# Windows (cmd)
set SUMO_HOME=C:\path\to\sumo

# Windows (PowerShell)
$env:SUMO_HOME = "C:\path\to\sumo"

# Linux/Mac
export SUMO_HOME=/path/to/sumo
```

### 4. Build map (chạy 1 lần)

```bash
python scripts/build_map.py mydinh
python scripts/build_map.py 2x2

# Interactive — liệt kê map có sẵn
python scripts/build_map.py
```

---

## Chọn map

Mở `training/config.py`, đổi dòng `TOPOLOGY`:

```python
TOPOLOGY = "mydinh"   # map thực tế Mỹ Đình 8 ngã tư (recommended)
TOPOLOGY = "2x2"      # map synthetic 4 ngã tư (train nhanh / baseline)
```

`STATE_DIM` tự tính theo map — không cần đổi gì khác.

---

## Training

### Fresh train (recommended)

```bash
# Parallel — recommended cho gat_marl / idqn
python -m training.train_parallel --model gat_marl --num-workers 2
python -m training.train_parallel --model idqn    --num-workers 2

# Single-process (debug / fixed_time baseline)
python -m training.train --model gat_marl
python -m training.train --model fixed_time
```

### Override obstacle

```bash
python -m training.train_parallel --model gat_marl --num-workers 2 \
    --obstacle-prob 0.5 \
    --obstacle-max-count 2 \
    --obstacle-duration-min 200 \
    --obstacle-duration-max 600
```

### Resume / Finetune

```bash
# Resume — tiếp tục train, log append
python -m training.train_parallel --model gat_marl --num-workers 2 \
    --resume checkpoints/final/gat_marl_mydinh_best.pt

# Finetune từ map khác (freeze GAT 20 ep đầu)
python -m training.train_parallel --model gat_marl --num-workers 2 \
    --finetune checkpoints/final/gat_marl_2x2_best.pt
```

| Tình huống | Nên làm |
|-----------|---------|
| Cùng map, cùng config, tiếp tục train | `--resume` |
| Chuyển từ `2x2` → `mydinh` | `--finetune` |
| Đổi `SIM_END`, reward, hoặc state dim | Train fresh |

### Workflow gợi ý

```
1. Build map (1 lần)
   └─ python scripts/build_map.py mydinh

2. Debug nhanh (single-process, 20 ep)
   └─ python -m training.train --model gat_marl --episodes 20

3. Train thật — parallel
   └─ python -m training.train_parallel --model gat_marl --num-workers 2
   └─ python -m training.train_parallel --model idqn    --num-workers 2

4. Fixed-time baseline
   └─ python -m training.train --model fixed_time
```

---

## Hyperparameters

| Tham số | Giá trị | Ghi chú |
|---------|---------|---------|
| `LR` | 1e-4 | Learning rate (Adam) |
| `GAMMA` | 0.95 | Discount factor |
| `BATCH_SIZE` | 64 | |
| `REPLAY_BUFFER_SIZE` | 50,000 | Circular, pre-allocated numpy |
| `TARGET_UPDATE_FREQ` | 400 | Gradient updates |
| `SYNC_EVERY` | 50 | Sync weights worker → learner |
| `REWARD_SCALE` | 5.0 | Scale reward signal |
| `GRAD_CLIP` | 10.0 | Max gradient norm |
| `SIM_END` | 1800 | Giây — 1 episode = 30 phút |
| `OBSTACLE_PROB` | 0.4 | Xác suất vật cản mỗi episode |
| `OBSTACLE_MAX_COUNT` | 3 | Tối đa vật cản đồng thời |

---

## Xem kết quả

Sau khi train xong cả 3 models:

```bash
python scripts/merge_logs.py
```

Đọc `logs/<topology>/gat_marl/training_log.csv`, `idqn/...`, `fixed_time/...` → tạo `logs/merged.json` cho dashboard.

<!-- [TODO: screenshot trang Results — learning curves, bảng so sánh metrics, attention heatmap] -->

---

## Live Demo

Mở **5 terminal**, chạy theo thứ tự:

```bash
# Terminal 1 — FastAPI server
python -m server.main

# Terminal 2 — GAT-MARL worker
python -m workers.worker_gat

# Terminal 3 — IDQN worker
python -m workers.worker_idqn

# Terminal 4 — Fixed-time worker
python -m workers.worker_fixed

# Terminal 5 — Dashboard
cd dashboard && npm run dev
```

Truy cập **http://localhost:5173** → tab **Live Demo**.

Thêm `--gui` để mở cửa sổ SUMO trực quan:

```bash
python -m workers.worker_gat --gui
```

<!-- [TODO: screenshot Live Demo với 3 panels song song, xe chạy trên bản đồ, attention arrows] -->

---

## Thêm map mới

1. Tạo structure trong `simulation/<map_name>/`:
   ```
   simulation/<map_name>/
       net/<map_name>.nod.xml    ← bắt buộc
       net/<map_name>.edg.xml    ← bắt buộc
       net/<map_name>.typ.xml    ← optional
       routes/gen_routes.py      ← optional
       <map_name>.sumocfg
   ```

2. Thêm `environment/maps/map_<map_name>.py` với:
   - `INTERSECTION_IDS`
   - `INCOMING_EDGES`, `OUTGOING_EDGES`
   - `ADJACENCY_MATRIX`
   - `EDGE_WEIGHTS` (optional, mặc định 1.0)

3. Đăng ký trong `environment/maps/__init__.py`.

4. Chạy `python scripts/build_map.py <map_name>`.

---

## Tech Stack

| Component | Công nghệ |
|-----------|-----------|
| RL Framework | PyTorch ≥ 2.3 |
| Graph Neural Network | PyTorch Geometric ≥ 2.5 |
| Traffic Simulator | SUMO ≥ 1.18 (TraCI) |
| API Server | FastAPI + Uvicorn |
| Dashboard | React + Vite |
| Data format | CSV logs → JSON |