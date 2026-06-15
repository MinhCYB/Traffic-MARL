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

Đèn giao thông truyền thống hoạt động theo chu kỳ cố định, không phản ứng với lưu lượng thực tế. Dự án này giải quyết 3 điểm yếu cốt lõi:

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

**Reward:** Hybrid Waiting Time + Weighted Pressure

```
reward_i = -(α × wait_norm_i + β × pressure_i)

  wait_norm_i = mean_waiting_time_i / 120s   ← normalize về [0,1], clip tại 2 phút
  pressure_i  = |Σ(queue_in × w_e) - Σ(queue_out × w_e)| / N_lanes

  α = 0.7  → waiting time là primary signal (sát tiêu chí HCM / SCOOT)
  β = 0.3  → pressure làm regularizer, tránh spillback
```

Lý do chọn hybrid thay vì pure pressure:
- **Waiting time** đo trực tiếp trải nghiệm người dùng — tiêu chí số 1 theo HCM 7th Edition và hệ thống SCOOT/SCATS thực tế
- **Pressure** giữ vai trò regularizer: tránh agent "hy sinh" một hướng để tối ưu waiting time cục bộ, đồng thời ổn định training khi xe còn thưa (đầu episode)
- Arterial edges weight 2.0, secondary 1.0

---

## Cấu trúc dự án

```
Smart-Traffic-MARL/
├── simulation/                  # SUMO map files
│   ├── 2x2/                     # Map synthetic 4 ngã tư (baseline/train nhanh)
│   └── mydinh/                  # Map thực tế Mỹ Đình 8 ngã tư
│       ├── net/                 # nod.xml, edg.xml, typ.xml → gen net.xml
│       ├── routes/              # gen_routes.py → peak + night
│       ├── detectors/           # E2 detectors mọi incoming lane
│       └── mydinh.sumocfg
│
├── environment/                 # RL Environment layer
│   ├── traffic_env.py           # SUMO wrapper qua TraCI (batch subscription)
│   ├── state_builder.py         # Build state vector, STATE_DIM tự tính theo map
│   ├── reward.py                # Hybrid Waiting Time + Weighted Pressure
│   └── maps/                   # Topology data từng map
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
│   ├── scheduler.py
│   └── config.py                # Tất cả hyperparams + TOPOLOGY
│
├── workers/                     # 3 process song song cho Live Demo
│   ├── worker_base.py
│   ├── worker_gat.py
│   ├── worker_idqn.py
│   └── worker_fixed.py
│
├── server/                      # FastAPI — sync + broadcast WebSocket
│   ├── main.py
│   ├── sync_buffer.py
│   └── schemas.py
│
├── dashboard/                   # React + Vite web dashboard
│   └── src/
│       ├── components/          # IntersectionGrid, AttentionArrows, MetricsPanel
│       ├── hooks/               # useWebSocket
│       └── pages/               # Slides, LiveDemo, Results
│
├── scripts/
│   ├── build_map.py             # Build SUMO net + routes
│   ├── merge_logs.py            # Merge CSV logs → JSON cho dashboard
│   ├── run_training.sh
│   └── run_demo.sh
│
├── checkpoints/                 # Saved model weights (.pt)
├── logs/                        # Training CSV logs
├── .env                         # SUMO_HOME, ports, server URL
└── requirements.txt
```

---

## Cài đặt

### Yêu cầu

- Python 3.10+
- [SUMO](https://sumo.dlr.de/docs/Installing/index.html) >= 1.18
- Node.js >= 18 (cho dashboard)

### Backend

```bash
git clone https://github.com/MinhCYB/Traffic-MARL.git
cd Traffic-MARL

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

### Dashboard

```bash
cd dashboard
npm install
```

### SUMO_HOME

```bash
# Windows
set SUMO_HOME=C:\path\to\sumo

# Linux/Mac
export SUMO_HOME=/path/to/sumo
```

---

## Chọn map

Mở `training/config.py`, đổi dòng `TOPOLOGY`:

```python
TOPOLOGY = "mydinh"   # map thực tế Mỹ Đình 8 ngã tư (recommended)
TOPOLOGY = "2x2"      # map synthetic 4 ngã tư (train nhanh / baseline)
```

`STATE_DIM` sẽ tự tính lại theo map, không cần đổi gì thêm.

---

## Build map (chạy 1 lần)

```bash
python scripts/build_map.py mydinh
python scripts/build_map.py 2x2

# Interactive — liệt kê map có sẵn để chọn
python scripts/build_map.py
```

Script tự chạy `netconvert` (gen `net.xml`) và `gen_routes.py` (gen `routes_peak.rou.xml` + `routes_night.rou.xml`).

> **Lưu ý:** Sau khi đổi `SIM_END` trong `config.py`, cần chạy lại `gen_routes.py` để cập nhật `end` và `vehsPerHour` trong file route XML.

---

## Hyperparameters

| Tham số | Giá trị | Ghi chú |
|---------|---------|---------|
| `LR` | 3e-4 | Learning rate |
| `GAMMA` | 0.99 | Discount factor |
| `EPSILON_DECAY` | 0.993 | Nhân mỗi episode |
| `BATCH_SIZE` | 32 | |
| `REPLAY_BUFFER_SIZE` | 50 000 | |
| `TARGET_UPDATE_FREQ` | 100 | Steps |
| `SYNC_EVERY` | 50 | Sync weights worker↔learner |
| `SIM_END` | **1800** | Giây — 1 episode = 30 phút |
| `NUM_EPISODES` | 500 | Per worker |
| `NUM_WORKERS` | 2 | Song song (sweet-spot RTX 3050 Ti) |
| `OBSTACLE_PROB` | 0.4 | Xác suất có vật cản mỗi episode |
| `OBSTACLE_MAX_COUNT` | 3 | Tối đa vật cản đồng thời |
| `OBSTACLE_DURATION_MIN` | 300 | Giây — tối thiểu mỗi vật cản |
| `OBSTACLE_DURATION_MAX` | None | None = xuyên suốt episode |

---

## Training

### 1. Fresh train (recommended)

```bash
# Parallel — recommended cho gat_marl / idqn
python -m training.train_parallel --model gat_marl --num-workers 2
python -m training.train_parallel --model idqn    --num-workers 2

# Single-process (debug / fixed_time baseline)
python -m training.train --model gat_marl
python -m training.train --model fixed_time   # fixed_time chỉ dùng single-process
```

> `--episodes` mặc định = `NUM_EPISODES` trong config (500). Với parallel, đây là số episodes **mỗi worker** — tổng thực tế = episodes × num-workers.

### 2. Override obstacle params

Obstacle đã bật mặc định theo config (`OBSTACLE_PROB=0.4`). Có thể override qua CLI:

```bash
python -m training.train_parallel --model gat_marl --num-workers 2 \
    --obstacle-prob 0.5 \
    --obstacle-max-count 2 \
    --obstacle-duration-min 200 \
    --obstacle-duration-max 600    # None nếu muốn xuyên suốt episode
```

> **Backward compat:** `--accident-prob` và `--accident-duration` vẫn hoạt động, tự map sang obstacle params.

### 3. Resume / Finetune

> ⚠️ Chỉ nên resume khi hyperparams và map **không đổi**. Nếu đã thay `SIM_END`, `reward function`, hoặc chuyển map → **train fresh** để tránh Q-value distribution shift.

```bash
# Resume (tiếp tục train, log ghi append)
python -m training.train_parallel --model gat_marl --num-workers 2 \
    --resume checkpoints/final/gat_marl_mydinh_best.pt

# Finetune từ map khác (freeze GAT 20 ep đầu)
python -m training.train_parallel --model gat_marl --num-workers 2 \
    --finetune checkpoints/final/gat_marl_2x2_best.pt
```

| Tình huống | Nên làm |
|-----------|---------|
| Cùng map, cùng config, tiếp tục train | Resume |
| Chuyển từ `2x2` → `mydinh` | Finetune |
| Đổi `SIM_END`, reward, hoặc state dim | Train fresh |
| Map mới có `NUM_ACTIONS` khác | Train fresh |

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

### Vật cản (obstacle)

Mô phỏng các tình huống thực tế: công trình, xe hỏng, sửa đường... Khác với "tai nạn" đơn lẻ, obstacle có thể:
- Xuất hiện **1–3 cái đồng thời** trong 1 episode
- Kéo dài **từ 300s đến xuyên suốt episode** (tuỳ config)
- Inject vào random edge, clear tự động (hoặc kéo đến hết episode nếu `OBSTACLE_DURATION_MAX=None`)

Log CSV ghi thêm 3 cột: `had_obstacle` (0/1), `obstacle_edges` (danh sách edge), `obstacle_count` (số lượng).

---

## Xem kết quả (dashboard Results tab)

Sau khi train xong cả 3 models:

```bash
python scripts/merge_logs.py
```

Script đọc `logs/<topology>/gat_marl/training_log.csv`, `idqn/training_log.csv`, `fixed_time/training_log.csv` → tạo `logs/merged.json` cho dashboard hiển thị chart so sánh và bảng summary.

---

## Live Demo

Mở 5 terminal, chạy theo thứ tự:

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

Truy cập `http://localhost:5173` → tab **Live Demo**.

Thêm `--gui` để mở cửa sổ SUMO trực quan (khuyến nghị chỉ mở cho 1 worker):

```bash
python -m workers.worker_gat --gui
```

---

## Thêm map mới

Tạo đúng structure sau, chạy `build_map.py` là xong:

```
simulation/<map_name>/
    net/<map_name>.nod.xml    ← bắt buộc
    net/<map_name>.edg.xml    ← bắt buộc
    net/<map_name>.typ.xml    ← optional
    routes/gen_routes.py      ← optional
    <map_name>.sumocfg
```

Thêm `environment/maps/map_<map_name>.py` với `INTERSECTION_IDS`, `INCOMING_EDGES`, `OUTGOING_EDGES`, `ADJACENCY_MATRIX`. Đăng ký trong `environment/maps/__init__.py`.

---

## Tham khảo

| Paper | Liên quan |
|-------|-----------|
| [PressLight — Wei et al., KDD 2019](https://faculty.ist.psu.edu/jessieli/Publications/2019-KDD-presslight.pdf) | Weighted pressure làm regularizer (β=0.3) |
| [AttentionLight — Shao et al., 2023](https://arxiv.org/abs/2307.05170) | Waiting time làm primary reward signal (α=0.7) |
| [CoLight — Wei et al., CIKM 2019](https://arxiv.org/abs/1905.05717) | GAT cho traffic signal control |
| [MPLight — Chen et al., AAAI 2020](https://ojs.aaai.org/index.php/AAAI/article/view/5744) | Parameter sharing |
| [GAT — Veličković et al., ICLR 2018](https://arxiv.org/abs/1710.10903) | Graph Attention Networks |
| [Ape-X — Horgan et al., ICLR 2018](https://arxiv.org/abs/1803.00933) | Distributed prioritized experience replay |

**Tools:** [PyTorch Geometric](https://pytorch-geometric.readthedocs.io) · [SUMO](https://sumo.dlr.de/docs) · [TraCI](https://sumo.dlr.de/docs/TraCI.html)