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

**Reward:** Weighted Max Pressure — `reward_i = -|Σ(queue_in × w_e) - Σ(queue_out × w_e)| / N_lanes`
(arterial edges weight 2.0, secondary 1.0)

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
│   ├── reward.py                # Weighted Max Pressure formula
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
│   ├── train.py                 # Single-process training (debug / fixed_time)
│   ├── train_parallel.py        # Parallel rollout training — Ape-X style
│   ├── replay_buffer.py         # Pre-allocated numpy circular buffer
│   ├── scheduler.py
│   └── config.py                # Tất cả hyperparams + TOPOLOGY
│
├── workers/                     # 3 process song song cho demo
│   ├── worker_base.py           # Base class với batch TraCI subscription
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
├── scripts/                     # Dev tools
│   ├── build_map.py             # Build SUMO net + routes (cross-platform)
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
# Windows (thêm vào .env hoặc System Environment Variables)
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
# Build map đã chọn trong config
python scripts/build_map.py mydinh
python scripts/build_map.py 2x2

# Interactive — liệt kê map có sẵn để chọn
python scripts/build_map.py
```

Script tự chạy `netconvert` (gen `net.xml`) và `gen_routes.py` (gen `routes_peak.rou.xml` + `routes_night.rou.xml`).

---

## Training

Có 2 chế độ training tùy mục đích:

### Single-process (`train.py`)

Dùng khi debug config mới, thử nghiệm hyperparams, hoặc train `fixed_time`. Dễ đọc traceback, không có overhead multi-process.

```bash
# Train từng model
python -m training.train --model gat_marl
python -m training.train --model idqn
python -m training.train --model fixed_time   # chỉ dùng single-process

# Resume từ checkpoint
python -m training.train --model gat_marl \
    --resume checkpoints/final/gat_marl_mydinh_best.pt

# Finetune sang map mới
python -m training.train --model gat_marl \
    --finetune checkpoints/final/gat_marl_mydinh_best.pt

# Override số episodes hoặc device
python -m training.train --model gat_marl --episodes 100 --device cpu
```

### Parallel rollout (`train_parallel.py`) — recommended

Chạy N SUMO workers song song, 1 Learner dùng GPU liên tục theo kiến trúc Ape-X. Phù hợp khi config đã ổn định và muốn train nhanh hơn. Output CSV cùng format với `train.py` nên `merge_logs.py` dùng được bình thường.

**Lưu ý quan trọng về số episodes:** `--episodes` là số episodes *mỗi worker* chạy, không phải tổng. Để tương đương với `train.py --episodes 500`, chia đôi:

```bash
# Máy laptop 6-8 core (RTX 3050 Ti, v.v.) — 2 workers là sweet-spot
python -m training.train_parallel --model gat_marl \
    --num-workers 2 --episodes 250
# → tổng 250 × 2 = 500 episodes

# Máy desktop nhiều core hơn có thể thử 3 workers
python -m training.train_parallel --model gat_marl \
    --num-workers 3 --episodes 167
# → tổng ~500 episodes
```

**Workflow gợi ý:**

```bash
# 1. Debug / thử config mới — single process, ít episodes
python -m training.train --model gat_marl --episodes 20

# 2. Train thật khi config ổn — parallel
python -m training.train_parallel --model gat_marl \
    --num-workers 2 --episodes 250

# 3. Fixed-time baseline (chỉ single-process)
python -m training.train --model fixed_time
```

---

## Finetune sang map mới

Finetune cho phép tận dụng model đã train trên một map (ví dụ `2x2`) làm điểm khởi đầu khi chuyển sang map mới (ví dụ `mydinh`), thay vì train từ đầu. Thời gian hội tụ giảm đáng kể vì Local Encoder và Q-head đã học được kiến thức chung về traffic, chỉ cần GAT layer thích nghi với topology mới.

### Cơ chế hoạt động

Khi finetune, agent thực hiện **2-phase training**:

**Phase 1 — Freeze GAT, chỉ train Q-head** (mặc định 20 episodes đầu):

GAT layer giữ nguyên trọng số từ checkpoint cũ. Chỉ Local Encoder và Q-head được update. Mục đích là để Q-head nhanh chóng học lại value function phù hợp với reward scale và state distribution của map mới, tránh gradient lớn từ Q-head phá vỡ GAT weights ngay từ đầu.

**Phase 2 — Unfreeze toàn bộ, train end-to-end** (sau episode thứ 20):

Toàn bộ network được update. GAT layer lúc này có thể điều chỉnh attention pattern theo topology mới trong khi Q-head đã ổn định.

Ngoài ra, khi load checkpoint để finetune, optimizer state và epsilon **không được load lại** — epsilon reset về `EPSILON_START` để agent explore đủ trên map mới, optimizer bắt đầu fresh để tránh momentum cũ từ map khác ảnh hưởng.

### Dùng `train.py` (single-process)

```bash
# Finetune với cài đặt mặc định (freeze 20 episodes đầu)
python -m training.train --model gat_marl \
    --finetune checkpoints/final/gat_marl_2x2_best.pt

# Tăng freeze nếu map mới rất khác (nhiều ngã tư hơn, topology phức tạp hơn)
python -m training.train --model gat_marl \
    --finetune checkpoints/final/gat_marl_2x2_best.pt \
    --freeze-gat-epochs 50

# Giảm freeze về 0 nếu map mới gần giống map cũ (chỉ thêm vài ngã tư)
python -m training.train --model gat_marl \
    --finetune checkpoints/final/gat_marl_2x2_best.pt \
    --freeze-gat-epochs 0
```

### Dùng `train_parallel.py` (recommended)

Parallel finetune nhanh hơn đáng kể vì nhiều workers cùng explore map mới song song — đặc biệt có lợi ở Phase 1 khi cần collect nhiều experience để Q-head hội tụ nhanh.

```bash
# Finetune parallel — freeze 20 episodes đầu (tính theo logged episodes, không phải per-worker)
python -m training.train_parallel --model gat_marl \
    --num-workers 2 --episodes 150 \
    --finetune checkpoints/final/gat_marl_2x2_best.pt

# Tăng freeze-gat-episodes nếu map mới phức tạp hơn nhiều
python -m training.train_parallel --model gat_marl \
    --num-workers 2 --episodes 150 \
    --finetune checkpoints/final/gat_marl_2x2_best.pt \
    --freeze-gat-episodes 50
```

**Lưu ý về `--freeze-gat-episodes` trong parallel mode:**

`freeze_gat_episodes` đếm theo **logged episodes** phía Learner (tổng episodes từ tất cả workers), không phải episodes của từng worker riêng lẻ. Ví dụ với 2 workers và `--freeze-gat-episodes 20`, GAT sẽ được unfreeze sau khi Learner nhận đủ 20 episode summaries — tương đương ~10 episodes/worker.

### Khi nào nên finetune thay vì train fresh

| Tình huống | Nên làm |
|-----------|---------|
| Chuyển từ `2x2` sang `mydinh` (cùng loại bài toán, khác scale) | Finetune từ `2x2_best.pt` |
| Thêm ngã tư mới vào map hiện tại | Finetune với `--freeze-gat-epochs 0` |
| Thay đổi reward function hoặc state representation | Train fresh — weight cũ không còn nghĩa |
| Map mới có số phase khác (NUM_ACTIONS thay đổi) | Train fresh — output layer không tương thích |

### Theo dõi quá trình finetune

Log CSV ghi nhận `epsilon` theo từng episode. Một finetune diễn ra đúng sẽ có dạng:

```
Episode 1–20  : epsilon cao (1.0 → ~0.82), loss dao động lớn  ← Phase 1, Q-head adapt
Episode 20+   : loss bắt đầu ổn định, reward dần cải thiện    ← Phase 2, end-to-end
Episode 50–80 : reward vượt qua mức train-from-scratch tương đương
```

Nếu reward không cải thiện sau 100 episodes, thử tăng `--freeze-gat-epochs` lên 50–100 hoặc giảm learning rate trong `config.py`.

---

## Xem kết quả (dashboard Results tab)

Sau khi train xong cả 3 models, chạy:

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
| [PressLight — Wei et al., KDD 2019](https://faculty.ist.psu.edu/jessieli/Publications/2019-KDD-presslight.pdf) | Max Pressure reward |
| [CoLight — Wei et al., CIKM 2019](https://arxiv.org/abs/1905.05717) | GAT cho traffic signal control |
| [MPLight — Chen et al., AAAI 2020](https://ojs.aaai.org/index.php/AAAI/article/view/5744) | Parameter sharing |
| [GAT — Veličković et al., ICLR 2018](https://arxiv.org/abs/1710.10903) | Graph Attention Networks |
| [Ape-X — Horgan et al., ICLR 2018](https://arxiv.org/abs/1803.00933) | Distributed prioritized experience replay |

**Tools:** [PyTorch Geometric](https://pytorch-geometric.readthedocs.io) · [SUMO](https://sumo.dlr.de/docs) · [TraCI](https://sumo.dlr.de/docs/TraCI.html)