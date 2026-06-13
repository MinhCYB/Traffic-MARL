# 🚦 Smart Traffic MARL

> **GAT-MARL Traffic Signal Control** — Hệ thống điều khiển đèn giao thông thông minh sử dụng Multi-Agent Reinforcement Learning kết hợp Graph Attention Network.

Bài tập lớn môn Machine Learning — Mô phỏng mạng lưới giao thông đô thị thực tế, so sánh trực quan 3 phương pháp điều khiển: Fixed-time, IDQN, và GAT-MARL.

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

**Reward:** Max Pressure — `reward_i = -|Σqueue_incoming - Σqueue_outgoing|`

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
│   ├── traffic_env.py           # SUMO wrapper qua TraCI
│   ├── state_builder.py         # Build state vector, STATE_DIM tự tính theo map
│   ├── reward.py                # Max Pressure formula
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
│   ├── train.py                 # Main training loop
│   ├── replay_buffer.py
│   ├── scheduler.py
│   └── config.py                # Tất cả hyperparams + TOPOLOGY
│
├── workers/                     # 3 process song song cho demo
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

```bash
# Train từng model (đứng ở root project)
python -m training.train --model gat_marl
python -m training.train --model idqn
python -m training.train --model fixed_time

# Chạy song song 2 terminal — mỗi model dùng port TraCI riêng
# Terminal 1:
python -m training.train --model gat_marl
# Terminal 2:
python -m training.train --model idqn

# Resume từ checkpoint
python -m training.train --model gat_marl --resume

# Chỉ định device
python -m training.train --model idqn --device cpu
```

**2 phase training** — đổi route file trong config rồi train lại:
- `peak`: giờ cao điểm, 600–900 veh/h trên arterial
- `night`: ban đêm, 70–120 veh/h

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

**Tools:** [PyTorch Geometric](https://pytorch-geometric.readthedocs.io) · [SUMO](https://sumo.dlr.de/docs) · [TraCI](https://sumo.dlr.de/docs/TraCI.html)