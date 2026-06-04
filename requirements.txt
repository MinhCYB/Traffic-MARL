# 🚦 SMART-TRAFFIC-MARL

> **GAT-MARL Traffic Signal Control** — Hệ thống điều khiển đèn giao thông thông minh sử dụng Multi-Agent Reinforcement Learning kết hợp Graph Attention Network.

Bài tập lớn môn Machine Learning — Mô phỏng mạng lưới giao thông đô thị 2×2, so sánh trực quan 3 phương pháp điều khiển đèn tín hiệu: Fixed-time, IDQN, và GAT-MARL.

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
│   ├── net/                     # Network files (nod, edg, typ, net)
│   ├── routes/                  # 3 route files: peak, weekend, night
│   ├── detectors/               # E2 detector 200m mỗi lane
│   └── accident/                # Script inject tai nạn qua TraCI
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