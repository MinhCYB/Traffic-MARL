# Hướng dẫn Scale Topology

> Tài liệu này mô tả quy trình mở rộng từ 2x2 lên bất kỳ NxM nào.
> Ví dụ minh hoạ: scale từ 2x2 → 2x3 (thêm N05, N06).

---

## Tổng quan

Kiến trúc GAT-MARL **không cần train lại từ đầu** khi scale nhờ parameter sharing.
Quy trình gồm 3 bước chính:

```
1. Simulation   — thêm nodes/edges trong SUMO
2. Code         — update state_builder.py
3. Training     — load checkpoint cũ, fine-tune
```

---

## Bước 1 — Cập nhật SUMO simulation

### 1.1 Thêm nodes vào `simulation/net/2x2.nod.xml`

```xml
<!-- Ví dụ scale 2x2 → 2x3: thêm N05, N06 -->
<node id="N05" x="600"  y="200"  type="traffic_light"/>
<node id="N06" x="600"  y="-200" type="traffic_light"/>

<!-- Ngoại thành mới phía đông -->
<node id="NT_N_E2" x="600" y="500"  type="priority"/>
<node id="NT_S_E2" x="600" y="-500" type="priority"/>
<node id="NT_E2_N" x="900" y="200"  type="priority"/>
<node id="NT_E2_S" x="900" y="-200" type="priority"/>

<!-- Internal sources mới -->
<node id="SRC5" x="400" y="200"  type="priority"/>  <!-- giữa N02-N05 -->
<node id="SRC6" x="400" y="-200" type="priority"/>  <!-- giữa N04-N06 -->
<node id="SRC7" x="600" y="0"    type="priority"/>  <!-- ngõ N05-N06 -->
```

### 1.2 Thêm edges vào `simulation/net/2x2.edg.xml`

```xml
<!-- Đường chính ngang N02-SRC5-N05 -->
<edge id="N02_SRC5" from="N02"  to="SRC5" type="main_road"/>
<edge id="SRC5_N05" from="SRC5" to="N05"  type="main_road"/>
<edge id="N05_SRC5" from="N05"  to="SRC5" type="main_road"/>
<edge id="SRC5_N02" from="SRC5" to="N02"  type="main_road"/>

<!-- Tương tự cho N04-SRC6-N06, ngõ N05-SRC7-N06, ngoại thành mới -->
<!-- ... pattern giống hệt file edg.xml hiện tại -->
```

### 1.3 Build lại net file

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
```

> Đặt tên file output theo topology mới nếu muốn giữ cả 2 version:
> `--output-file=2x3.net.xml` → tạo `2x3.sumocfg` riêng.

### 1.4 Thêm detectors

Trong `simulation/detectors/e2_detectors.add.xml`, thêm detector cho tất cả incoming lanes của N05, N06 — pattern giống hệt các ngã tư cũ.

### 1.5 Cập nhật route files

Thêm flows đi qua N05, N06 vào 3 file routes. Nhớ rule: flow đi qua SRC node cần `via` chỉ rõ path.

---

## Bước 2 — Cập nhật code

### 2.1 `env/state_builder.py` — phần quan trọng nhất

```python
# Thêm node mới
INTERSECTION_IDS = ["N01", "N02", "N03", "N04", "N05", "N06"]

# Cập nhật incoming/outgoing edges cho từng node
INCOMING_EDGES: dict[str, list[str]] = {
    "N01": [...],   # giữ nguyên
    "N02": [...],   # giữ nguyên
    "N03": [...],   # giữ nguyên
    "N04": [...],   # giữ nguyên
    "N05": ["NT_N_E2_N05", "NT_E2_N_N05", "SRC5_N05", "SRC7_N05"],  # mới
    "N06": ["NT_S_E2_N06", "NT_E2_S_N06", "SRC6_N06", "SRC7_N06"],  # mới
}

OUTGOING_EDGES: dict[str, list[str]] = {
    # ... tương tự
}

# Cập nhật adjacency matrix (6x6 thay vì 4x4)
ADJACENCY_MATRIX = np.array([
    # N01  N02  N03  N04  N05  N06
    [  0,   1,   1,   0,   0,   0],  # N01
    [  1,   0,   0,   1,   1,   0],  # N02
    [  1,   0,   0,   1,   0,   0],  # N03
    [  0,   1,   1,   0,   0,   1],  # N04
    [  0,   1,   0,   0,   0,   1],  # N05
    [  0,   0,   0,   1,   1,   0],  # N06
], dtype=np.float32)
```

### 2.2 `training/config.py` — đổi port nếu cần

```python
# Không cần đổi gì nếu vẫn dùng 3 process (GAT/IDQN/Fixed)
# Chỉ đổi nếu chạy thêm process mới
```

### 2.3 `simulation/2x2.sumocfg` (hoặc tạo `2x3.sumocfg`)

```xml
<net-file value="net/2x3.net.xml"/>
```

---

## Bước 3 — Fine-tune từ checkpoint 2x2

### 3.1 Zero-shot test (không fine-tune)

```bash
# Load checkpoint 2x2, chạy thẳng trên topology 2x3
python -m training.train --model gat_marl \
    --resume checkpoints/gat_marl_final.pt \
    --episodes 10 2>/dev/null
```

Đây là baseline — xem model tổng quát hoá được bao nhiêu mà không cần train thêm.

### 3.2 Fine-tune

```bash
python -m training.train --model gat_marl \
    --resume checkpoints/gat_marl_final.pt 2>/dev/null
```

Model load weights từ checkpoint 2x2, tiếp tục train trên topology mới.
Thường hội tụ sau **50-100 episode** thay vì 500 episode train từ đầu.

### 3.3 So sánh kết quả

| Phương pháp | Episodes cần | Kỳ vọng |
|-------------|-------------|---------|
| Train từ đầu | ~500 | Baseline |
| Zero-shot | 0 | ~60-70% hiệu năng |
| Fine-tune | ~50-100 | ~90-95% hiệu năng |

Headline kết quả: *"Thích nghi topology mới nhanh hơn 5-6x so với train lại từ đầu."*

---

## Checklist scale

```
Simulation:
  [ ] Thêm nodes vào nod.xml
  [ ] Thêm edges vào edg.xml
  [ ] Build lại net.xml (netconvert)
  [ ] Thêm detectors vào e2_detectors.add.xml
  [ ] Cập nhật route files (thêm flows qua node mới)
  [ ] Verify: sumo -c <config> --no-step-log --end 100

Code:
  [ ] INTERSECTION_IDS trong state_builder.py
  [ ] INCOMING_EDGES / OUTGOING_EDGES trong state_builder.py
  [ ] ADJACENCY_MATRIX trong state_builder.py
  [ ] sumocfg path trong traffic_env.py (nếu tạo file mới)

Training:
  [ ] Zero-shot test — ghi lại metrics
  [ ] Fine-tune từ checkpoint 2x2
  [ ] So sánh với train từ đầu
  [ ] Update merge_logs.py nếu thêm model mới
```
