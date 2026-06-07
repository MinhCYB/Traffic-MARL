# 🚦 SMART-TRAFFIC-MARL

> **GAT-MARL Traffic Signal Control** — Hệ thống điều khiển đèn giao thông thông minh sử dụng Multi-Agent Reinforcement Learning kết hợp Graph Attention Network.

Đồ án môn Machine Learning — Mô phỏng mạng lưới giao thông đô thị 2×2, so sánh trực quan 3 phương pháp điều khiển đèn tín hiệu: Fixed-time, IDQN, và GAT-MARL.

---

## Tổng quan

Đèn giao thông truyền thống hoạt động theo chu kỳ cố định, không phản ứng với lưu lượng thực tế. Dự án này giải quyết 3 điểm yếu cốt lõi của các hệ thống hiện tại:

| Vấn đề | Giải pháp |
|--------|-----------|
| Không coordination — mỗi ngã tư chỉ nhìn vào bản thân | GAT layer cho phép aggregate thông tin từ neighbors |
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
Có thể chứng minh toán học rằng minimize pressure = maximize network throughput (PressLight, KDD 2019).

---

## Demo

3 simulation chạy song song trên cùng traffic scenario (`seed=42`), visualize realtime qua web dashboard:

- **Fixed-time**: chu kỳ cố định 30s/30s — baseline
- **IDQN**: mỗi agent học độc lập, không communication
- **GAT-MARL**: agents communicate qua attention graph — throughput cao nhất, recovery nhanh nhất khi có tai nạn

Dashboard gồm 3 tab: **Slides** (presentation), **Live Demo** (3 panel song song), **Results** (training charts).

---

## Cấu trúc dự án

```
smart-traffic-marl/
│
├── simulation/                  # SUMO map, routes, detectors
│   └── 2x2/                     # Topology 2x2 (mặc định)
│       ├── net/                 # Network files (nod, edg, typ, net)
│       ├── routes/              # 3 route files: peak, weekend, night
│       ├── detectors/           # E2 detector 180m mỗi lane
│       └── 2x2.sumocfg
│
├── env/                         # RL Environment layer
│   ├── traffic_env.py           # Wrapper sumo-rl, enforce min_green 10s
│   ├── state_builder.py         # Normalize obs 0→1, build adjacency graph
│   └── reward.py                # Max Pressure formula
│
├── models/                      # Model definitions (PyTorch + PyG)
│   ├── gat_marl.py              # GAT 4-head + shared Q-head
│   ├── idqn.py                  # Independent DQN baseline
│   └── fixed_time.py            # Fixed cycle baseline
│
├── agents/                      # Agent logic (inference + learning)
│   ├── base_agent.py            # Abstract interface
│   ├── gat_agent.py
│   ├── idqn_agent.py
│   └── fixed_agent.py
│
├── training/                    # Training pipeline
│   ├── train.py                 # Main training loop
│   ├── replay_buffer.py         # Experience replay
│   ├── scheduler.py             # Epsilon decay, LR schedule
│   └── config.py                # Tất cả hyperparams tập trung 1 chỗ
│
├── workers/                     # 3 process song song (1 per model)
│   ├── worker_base.py           # HTTP POST JSON lên server mỗi 5s
│   ├── worker_gat.py
│   ├── worker_idqn.py
│   └── worker_fixed.py
│
├── server/                      # FastAPI — sync + broadcast
│   ├── main.py                  # WebSocket endpoint, command channel
│   ├── sync_buffer.py           # Chờ 3 process / solo fallback 2s
│   └── schemas.py               # Pydantic schemas JSON payload
│
├── dashboard/                   # React + Vite web dashboard
│   └── src/
│       ├── components/          # IntersectionGrid, AttentionArrows, MetricsPanel
│       ├── hooks/               # useWebSocket custom hook
│       └── pages/               # Slides, LiveDemo, Results
│
├── checkpoints/                 # Saved model weights (.pt)
├── logs/                        # Training CSV logs theo episode
├── notebooks/                   # Ablation study, attention visualization
├── scripts/                     # run_training.sh, run_demo.sh, record_demo.py
│
├── .env                         # SUMO_HOME, TraCI ports, server URL
├── requirements.txt
└── README.md
```

## Simulation & Episode

### Simulation layer

SUMO chạy vật lý xe, đèn, đường. Python điều khiển và đọc data qua TraCI API mỗi 5 giây.

**Topology 2x2:**
```
         [Ngoại thành Bắc]
               │
[NT Tây]──────N01────SRC1────N02──────[NT Đông]
               │      ↑      │
              SRC3   bãi đỗ SRC4
               │      ↓      │
[NT Tây]──────N03────SRC2────N04──────[NT Đông]
               │
         [Ngoại thành Nam]

N01: Công sở + Trường    N02: Công sở mở rộng
N03: Khu dân cư          N04: Vui chơi + dân cư
SRC1-4: Internal sources — xe xuất hiện giữa chừng (departPos=random)
```

**3 loại đường:**

| Loại | Speed | Lanes | Dùng cho |
|------|-------|-------|----------|
| main_road | 50 km/h | 2 | Đường chính ngang/dọc |
| alley | 30 km/h | 2 | Ngõ nhỏ N01↔N03, N02↔N04 |
| outskirts | 70 km/h | 2 | Kết nối ngoại thành |

**E2 Detector:** đặt 180m trước mỗi ngã tư, đọc mỗi 5s — đo queue length và density từng lane. Đây là nguồn data duy nhất agent nhìn thấy.

---

### 1 Episode

```
reset()
    └── SUMO khởi động, chọn ngẫu nhiên 1 route file
        peak (60%) | weekend (30%) | night (10%)
        seed=42 → cùng scenario khi so sánh 3 models
        Đặt tất cả đèn về phase 0

        ↓ lặp 720 lần (3600s / 5s)

step() mỗi 5s:
    ├── Agent đọc state → chọn action (keep/switch)
    ├── Env enforce min_green = 10s
    ├── Apply action → TraCI setPhase
    ├── simulationStep() × 5 lần
    ├── E2 detector đọc queue + density
    ├── reward = -|Σqueue_incoming - Σqueue_outgoing|
    └── trả về (obs, reward, done, info)

Episode kết thúc (step = 3600):
    └── Log: reward, speed, waiting_time, throughput
        Agent update từ replay buffer
        Epsilon decay
```

**Route files** tạo ra traffic pattern khác nhau — model không biết đang chạy route nào, tự học từ observation.

---

## Cài đặt

### Yêu cầu

- Python 3.10+
- [SUMO](https://sumo.dlr.de/docs/Installing/index.html) >= 1.18
- Node.js >= 18 (cho dashboard)

### Backend

```bash
# Clone repo
git clone https://github.com/<your-username>/smart-traffic-marl.git
cd smart-traffic-marl

# Tạo virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Cài dependencies
pip install -r requirements.txt

# Set SUMO_HOME
export SUMO_HOME=/path/to/sumo  # hoặc thêm vào .env
```

### Dashboard

```bash
cd dashboard
npm install
npm run dev
```

---

## Chạy

### Training

```bash
# Train cả 3 models tuần tự
bash scripts/run_training.sh

# Hoặc train từng model
python training/train.py --model gat_marl
python training/train.py --model idqn
```

### Live Demo

```bash
# Khởi động server + 3 workers + dashboard
bash scripts/run_demo.sh
```

Truy cập `http://localhost:5173` → Tab **Live Demo**.

Hoặc khởi động thủ công từng process:

```bash
# Terminal 1 — Server
python -m server.main

# Terminal 2 — Fixed-time worker
python -m workers.worker_fixed

# Terminal 3 — GAT-MARL worker
python -m workers.worker_gat

# Terminal 4 — IDQN worker (đồng đội)
python -m workers.worker_idqn

# Terminal 5 — Dashboard
cd dashboard && npm run dev
```

### Xem simulation thực tế (sumo-gui)

Mỗi worker hỗ trợ flag `--gui` để mở cửa sổ SUMO trực quan.
Khuyến nghị **chỉ mở GUI cho GAT-MARL** — chạy cả 3 GUI cùng lúc sẽ quá tải hệ thống.

```bash
# Chỉ GAT-MARL có GUI — recommended cho demo
python -m workers.worker_gat --gui
python -m workers.worker_fixed          # không GUI
python -m workers.worker_idqn          # không GUI
```

> **Lưu ý:** sumo-gui tốn thêm ~30% CPU so với chạy headless. Nếu máy yếu thì bỏ `--gui`, dùng dashboard để theo dõi metrics.

---

## Tham khảo

| Paper | Liên quan |
|-------|-----------|
| [PressLight — Wei et al., KDD 2019](https://faculty.ist.psu.edu/jessieli/Publications/2019-KDD-presslight.pdf) | Max Pressure reward |
| [CoLight — Wei et al., CIKM 2019](https://arxiv.org/abs/1905.05717) | GAT cho traffic signal control |
| [MPLight — Chen et al., AAAI 2020](https://ojs.aaai.org/index.php/AAAI/article/view/5744) | Parameter sharing, bỏ agent ID |
| [GAT — Veličković et al., ICLR 2018](https://arxiv.org/abs/1710.10903) | Graph Attention Networks |
| [QMIX — Rashid et al., ICML 2018](https://arxiv.org/abs/1803.11485) | Cooperative MARL (CTDE) |

**Tools:** [sumo-rl](https://github.com/LucasAlegre/sumo-rl) · [PyTorch Geometric](https://pytorch-geometric.readthedocs.io) · [SUMO](https://sumo.dlr.de/docs)