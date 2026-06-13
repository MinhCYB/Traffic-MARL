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

---

## Training

### Tham số chung

| Tham số | Mô tả | Mặc định |
|---------|-------|----------|
| `--model` | Model cần train: `gat_marl`, `idqn`, `fixed_time` | *(bắt buộc)* |
| `--episodes` | Số episodes | 500 |
| `--device` | `auto`, `cpu`, `cuda` | `auto` |
| `--resume` | Path checkpoint để tiếp tục train | — |
| `--finetune` | Path checkpoint để finetune (warm-start) | — |
| `--freeze-gat-epochs` | Số episodes freeze GAT khi finetune | 20 |
| `--updates-per-step` | Số lần backprop mỗi SUMO step | 4 |
| `--accident-prob` | Xác suất sinh tai nạn mỗi episode (0.0–1.0) | 0.0 |
| `--accident-duration` | Thời gian kéo dài tai nạn (giây) | 300 |

> `train_parallel.py` có thêm `--num-workers` (mặc định 2). Các tham số còn lại giống hệt.

---

### 1. Fresh train

```bash
# Single-process (debug / fixed_time)
python -m training.train --model gat_marl
python -m training.train --model idqn
python -m training.train --model fixed_time   # fixed_time chỉ dùng single-process

# Parallel (recommended cho gat_marl / idqn khi config đã ổn định)
# --episodes là số episodes MỖI WORKER, không phải tổng
# Để tương đương 500 episodes: 500 / num-workers
python -m training.train_parallel --model gat_marl --num-workers 2 --episodes 250
python -m training.train_parallel --model idqn    --num-workers 2 --episodes 250
```

### 2. Resume

Log sẽ tự động ghi tiếp (mode `append`) vào file CSV cũ — không mất data.

```bash
# Single-process
python -m training.train --model gat_marl \
    --resume checkpoints/final/gat_marl_mydinh_best.pt

# Parallel
python -m training.train_parallel --model gat_marl \
    --num-workers 2 --episodes 250 \
    --resume checkpoints/final/gat_marl_mydinh_best.pt
```

### 3. Finetune sang map mới

Dùng khi đã có checkpoint từ map cũ (vd: `2x2`) và muốn chuyển sang map mới (`mydinh`). Nhanh hơn train từ đầu nhờ Local Encoder và Q-head đã học traffic pattern chung.

**Cơ chế 2 phase:**
- **Phase 1** (mặc định 20 episodes đầu): Freeze GAT, chỉ train Q-head — tránh gradient lớn phá vỡ attention weights ngay từ đầu.
- **Phase 2** (sau episode 20): Unfreeze toàn bộ, train end-to-end.

```bash
# Single-process
python -m training.train --model gat_marl \
    --finetune checkpoints/final/gat_marl_2x2_best.pt

# Tăng freeze nếu map mới phức tạp hơn nhiều
python -m training.train --model gat_marl \
    --finetune checkpoints/final/gat_marl_2x2_best.pt \
    --freeze-gat-epochs 50

# Parallel
python -m training.train_parallel --model gat_marl \
    --num-workers 2 --episodes 150 \
    --finetune checkpoints/final/gat_marl_2x2_best.pt
```

| Tình huống | Nên làm |
|-----------|---------|
| Chuyển từ `2x2` → `mydinh` (cùng loại bài toán, khác scale) | Finetune |
| Thêm ngã tư mới vào map hiện tại | Finetune với `--freeze-gat-epochs 0` |
| Thay đổi reward function hoặc state representation | Train fresh |
| Map mới có số phase khác (`NUM_ACTIONS` thay đổi) | Train fresh |

### 4. Finetune với tai nạn

Dùng để dạy model xử lý sự cố giao thông. Nên chạy **sau** khi đã có checkpoint train tốt từ bước trên.

```bash
# Single-process
python -m training.train --model gat_marl \
    --finetune checkpoints/final/gat_marl_mydinh_best.pt \
    --accident-prob 0.3 \
    --accident-duration 300

# Parallel
python -m training.train_parallel --model gat_marl \
    --num-workers 2 --episodes 150 \
    --finetune checkpoints/final/gat_marl_mydinh_best.pt \
    --accident-prob 0.3 \
    --accident-duration 300
```

`--accident-prob 0.0` (mặc định) → không có tai nạn, không ảnh hưởng fresh train.

Log CSV sẽ ghi thêm 2 cột `had_accident` (0/1) và `accident_edge` để theo dõi.

### Workflow gợi ý

```
1. Debug config mới
   └─ train.py --model gat_marl --episodes 20

2. Train thật — parallel
   └─ train_parallel.py --model gat_marl --num-workers 2 --episodes 250

3. Fixed-time baseline (chỉ single-process)
   └─ train.py --model fixed_time

4. Finetune accident sau khi có checkpoint tốt
   └─ train.py --model gat_marl --finetune <best.pt> --accident-prob 0.3
```

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
| [PressLight — Wei et al., KDD 2019](https://faculty.ist.psu.edu/jessieli/Publications/2019-KDD-presslight.pdf) | Max Pressure reward |
| [CoLight — Wei et al., CIKM 2019](https://arxiv.org/abs/1905.05717) | GAT cho traffic signal control |
| [MPLight — Chen et al., AAAI 2020](https://ojs.aaai.org/index.php/AAAI/article/view/5744) | Parameter sharing |
| [GAT — Veličković et al., ICLR 2018](https://arxiv.org/abs/1710.10903) | Graph Attention Networks |
| [Ape-X — Horgan et al., ICLR 2018](https://arxiv.org/abs/1803.00933) | Distributed prioritized experience replay |

**Tools:** [PyTorch Geometric](https://pytorch-geometric.readthedocs.io) · [SUMO](https://sumo.dlr.de/docs) · [TraCI](https://sumo.dlr.de/docs/TraCI.html)