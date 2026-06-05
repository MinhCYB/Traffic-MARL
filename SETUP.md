# Hướng dẫn cài đặt & chạy

## 1. Yêu cầu hệ thống

| Tool | Version | Link |
|------|---------|------|
| Python | 3.10+ | |
| SUMO | ≥ 1.18 | https://sumo.dlr.de/docs/Installing |
| Node.js | ≥ 18 | https://nodejs.org |
| conda | any | https://docs.conda.io |

---

## 2. Cài đặt

### 2.1 Tạo môi trường conda

```bash
conda create -n smart-traffic python=3.10
conda activate smart-traffic
```

### 2.2 Cài PyTorch + PyG

```bash
# PyTorch (CPU) — thay cu121 bằng cu118/cu121 nếu có GPU
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# PyTorch Geometric
pip install torch-geometric
```

> **Có GPU?** Xem hướng dẫn cụ thể tại https://pytorch-geometric.readthedocs.io/en/latest/install/installation.html

### 2.3 Cài các dependencies còn lại

```bash
pip install -r requirements.txt
```

### 2.4 Set SUMO_HOME

```bash
# Windows (thêm vào .env hoặc set trực tiếp)
set SUMO_HOME=C:\Program Files (x86)\Eclipse\Sumo

# Linux/Mac
export SUMO_HOME=/path/to/sumo
```

Hoặc thêm vào file `.env` ở root:

```
SUMO_HOME=C:\Program Files (x86)\Eclipse\Sumo
```

### 2.5 Cài dashboard

```bash
cd dashboard
npm install
cd ..
```

---

## 3. Build SUMO network (1 lần duy nhất)

```bash
cd simulation/net

netconvert \
    --node-files=2x2.nod.xml \
    --edge-files=2x2.edg.xml \
    --type-files=2x2.typ.xml \
    --output-file=2x2.net.xml \
    --tls.default-type=actuated \
    --no-turnarounds true \
    --junctions.corner-detail 5

cd ../..
```

Verify:

```bash
sumo -c simulation/2x2.sumocfg --no-step-log --end 100
# Không có error là ổn
```

---

## 4. Training

### Train từng model

```bash
# Fixed-time baseline (nhanh, không cần GPU)
python -m training.train --model fixed_time

# GAT-MARL
python -m training.train --model gat_marl

# IDQN (đồng đội)
python -m training.train --model idqn
```

> **Ẩn SUMO warnings** (emergency braking, teleporting, v.v.):
> ```bash
> python -m training.train --model gat_marl 2>/dev/null
> ```
> `2>/dev/null` redirect stderr — console chỉ còn log episode.

### Train tất cả

```bash
bash scripts/run_training.sh
```

### Resume từ checkpoint

```bash
python -m training.train --model gat_marl --resume checkpoints/gat_marl_ep200.pt
```

Logs được lưu tại `logs/<model>/training_log.csv`.

---

## 5. Merge logs cho dashboard Results tab

Chạy sau khi train xong:

```bash
python scripts/merge_logs.py
# → tạo logs/merged.json
```

---

## 6. Live Demo

```bash
bash scripts/run_demo.sh
```

Sau đó mở `http://localhost:5173` → Tab **Live Demo**.

Hoặc khởi động thủ công từng process:

```bash
# Terminal 1 — Server
python -m server.main

# Terminal 2 — GAT worker
python -m workers.worker_gat

# Terminal 3 — Fixed worker
python -m workers.worker_fixed

# Terminal 4 — IDQN worker (đồng đội)
python -m workers.worker_idqn

# Terminal 5 — Dashboard
cd dashboard && npm run dev
```

---

## 7. Kịch bản demo

| Hồi | Thao tác | Quan sát |
|-----|----------|----------|
| 1 — Bình thường | Bấm ▶ Start | GAT throughput cao hơn rõ từ đầu |
| 2 — Tai nạn | Bấm 🚨 Inject tai nạn | Fixed-time kẹt dây chuyền, GAT giữ xanh xung quanh |
| 3 — Phục hồi | Quan sát attention arrows | Mũi tên tím dày lên từ N02, GAT bẻ luồng tự động |

---

## 8. Cấu trúc file quan trọng

```
training/config.py       ← Đổi hyperparams ở đây
simulation/2x2.sumocfg   ← SUMO config chính
checkpoints/             ← Model weights sau training
logs/                    ← CSV logs + merged.json
```

---

## 9. Troubleshooting

**`ModuleNotFoundError: traci`**
```bash
pip install traci sumolib
```

**`SUMO_HOME not set`**
```bash
export SUMO_HOME=/path/to/sumo   # Linux/Mac
set SUMO_HOME=C:\...\Sumo        # Windows
```

**`torch_geometric` cài lỗi**
→ Cài PyTorch trước, sau đó mới cài PyG. Xem https://pytorch-geometric.readthedocs.io

**Dashboard không nhận data**
→ Kiểm tra server đang chạy tại `http://localhost:8000/status`

**SUMO báo port đã dùng**
→ Đổi port trong `training/config.py`: `PORT_GAT`, `PORT_IDQN`, `PORT_FIXED`