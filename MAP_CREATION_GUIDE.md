# Hướng dẫn tạo map mới cho Traffic-MARL

> Tài liệu này dành cho AI assistant làm việc cùng developer trên project.
> Đọc toàn bộ trước khi tạo bất kỳ file nào.

---

## Tổng quan kiến trúc map

Mỗi map gồm 2 phần độc lập:

```
simulation/<map_name>/          ← SUMO files (physical simulation)
environment/maps/map_<name>.py  ← Python topology data (RL agent)
```

Hai phần phải **nhất quán** với nhau — edge ID trong Python phải khớp chính xác với edge ID trong SUMO.

---

## Phần 1 — SUMO Files

### 1.1 Quy tắc đặt tên node

```
Ngã tư chính:   N01, N02, N03, ... (traffic_light)
Boundary nodes: EXT_N_N01, EXT_S_N01, EXT_W_N01, EXT_E_N01 (priority)
Source nodes:   SRC_<TÊN_ĐƯỜNG> (priority) — đặt giữa 2 ngã tư
```

**Quan trọng:** Source node (SRC) là các node trung gian đặt giữa 2 ngã tư — dùng để xe spawn giữa đường và để detector đặt đúng chỗ. **Không dùng `--geometry.remove` khi chạy netconvert** vì sẽ merge SRC node vào edge, làm mất lane ID.

### 1.2 Quy tắc đặt tên edge

Edge ID = `<from_node>_<to_node>`, ví dụ:
```
N01_SRC_HTM_W     (từ N01 đến SRC_HTM_W)
SRC_HTM_W_N02     (từ SRC_HTM_W đến N02)
EXT_W_N01_in      (boundary vào N01 từ phía Tây)
N01_EXT_W_N01     (boundary ra khỏi N01 về phía Tây)
```

Mỗi đoạn đường 2 chiều = **4 edges** (A→SRC, SRC→B, B→SRC, SRC→A).

### 1.3 Lane ID trong SUMO

SUMO tự sinh lane ID theo format: `<edge_id>_<lane_index>`

```
SRC_HTM_W_N01_0   (edge SRC_HTM_W_N01, lane 0)
SRC_HTM_W_N01_1   (edge SRC_HTM_W_N01, lane 1)
SRC_HTM_W_N01_2   (edge SRC_HTM_W_N01, lane 2)
```

**Detector file phải dùng đúng lane ID này.** Nếu lane ID sai → SUMO báo lỗi `lane not known`.

### 1.4 Type file (typ.xml)

Định nghĩa 3 loại đường:

| type | numLanes | speed | Dùng cho |
|------|----------|-------|----------|
| `arterial` | 3 | 16.67 m/s (60 km/h) | Đường trục chính |
| `secondary` | 2 | 13.89 m/s (50 km/h) | Đường thứ cấp |
| `outskirts` | 2 | 19.44 m/s (70 km/h) | Boundary source/sink |

**Lưu ý thực tế:** Đường có nhiều làn xe mỗi chiều trong thực tế (ví dụ Lê Đức Thọ 2 làn/chiều) vẫn có thể là `secondary` trong SUMO vì SUMO model mỗi chiều là 1 edge riêng. Tầm quan trọng của đường **không** phụ thuộc vào `numLanes` trong SUMO — xem Phần 2.4 về `EDGE_WEIGHTS`.

### 1.5 Detector file (e2_detectors.add.xml)

- Loại detector: **E2 (laneAreaDetector)**
- `pos="-1"`: tính từ cuối edge (sát vạch dừng)
- `length="200"`: đo 200m queue
- `freq="5"`: sync với delta_time của RL agent
- `file="NUL"`: không ghi file, đọc qua TraCI

Đặt detector trên **tất cả incoming lanes** của mỗi ngã tư. Số detector = tổng số lane incoming của tất cả ngã tư.

Detector ID format: `e2_<edge_id>_<lane_index>`

```xml
<laneAreaDetector id="e2_SRC_HTM_W_N01_0" lane="SRC_HTM_W_N01_0"
                  pos="-1" length="200" freq="5" file="NUL"/>
```

### 1.6 Tọa độ node (nod.xml)

Dùng hệ tọa độ mét, ánh xạ từ Google Maps:
- x: Tây(−) → Đông(+)
- y: Nam(−) → Bắc(+)

Khoảng cách giữa 2 ngã tư thực tế ~400–600m. SRC node đặt chính giữa (x hoặc y = trung bình 2 ngã tư). Boundary node đặt ~300m ra ngoài ngã tư biên.

### 1.7 Lệnh build

```bash
python scripts/build_map.py <map_name>
```

Script tự chạy:
1. `netconvert` → `net/<map_name>.net.xml`
2. `routes/gen_routes.py` → `routes_peak.rou.xml` + `routes_night.rou.xml`

**Flags netconvert bắt buộc:**
```
--tls.default-type=actuated
--tls.cycle.time=90
--no-turnarounds=true
--junctions.corner-detail=5
```

**Flags KHÔNG dùng:** `--geometry.remove` — sẽ merge SRC nodes, phá vỡ lane ID.

---

## Phần 2 — Python Topology (environment/maps/)

### 2.1 File cần tạo

```
environment/maps/map_<map_name>.py
```

Sau đó đăng ký trong `environment/maps/__init__.py`.

### 2.2 INTERSECTION_IDS

List các ngã tư theo thứ tự **row-major** (trái→phải, trên→dưới):

```python
INTERSECTION_IDS = ["N01", "N02", "N03", "N04", "N05", "N06", "N07", "N08"]
```

Index trong list = node index trong GAT graph. Thứ tự này ảnh hưởng đến `ADJACENCY_MATRIX`.

### 2.3 INCOMING_EDGES và OUTGOING_EDGES

```python
INCOMING_EDGES = {
    "N01": ["EXT_W_N01_in", "EXT_N_N01_in", "SRC_HTM_W_N01", "SRC_NCT_N_N01"],
    ...
}
```

**Quan trọng:**
- Thứ tự edges trong list phải **nhất quán** giữa `INCOMING_EDGES` và cách `get_incoming_queues()` flatten lanes
- `reward.py` tính weighted sum theo đúng thứ tự này
- Edge ID phải khớp chính xác với `mydinh.edg.xml`

### 2.4 EDGE_WEIGHTS

**Đây là nơi khai báo tầm quan trọng thực tế của đường — không detect tự động.**

```python
EDGE_WEIGHTS = {
    # Khai báo các edge có weight > 1.0
    # Mặc định = 1.0, không cần khai báo
    "SRC_HTM_W_N01": 2.0,   # Hồ Tùng Mậu — đường trục chính
    "SRC_LDT_N_N02": 2.0,   # Lê Đức Thọ — 2 lane/chiều nhưng rất bận
    ...
}
```

**Lý do không detect qua numLanes:** Đường 2 lane/chiều có thể là arterial thực tế (Lê Đức Thọ) hoặc secondary thực tế (Hàm Nghi) — SUMO không phân biệt được. Developer biết rõ thực địa hơn.

Tham khảo `routes/gen_routes.py` (trường `vehsPerHour_peak`) để quyết định weight — đường nào có vph cao hơn thì weight cao hơn.

### 2.5 EDGE_LANES (get_edge_lanes)

```python
EDGE_LANES = {
    "SRC_HTM_W_N01": 3,   # arterial
    "SRC_LDT_N_N02": 2,   # secondary nhưng bận
    ...
}
DEFAULT_LANES = 2

def get_edge_lanes(edge_id: str) -> int:
    return EDGE_LANES.get(edge_id, DEFAULT_LANES)
```

Số lane phải khớp với `numLanes` trong `typ.xml`. Dùng để:
- Build state vector (density/queue per lane)
- Tính `STATE_DIM` động trong `state_builder.py`
- Tính `N_lanes` cho reward normalization

### 2.6 ADJACENCY_MATRIX

Ma trận đối xứng `N×N` (N = số ngã tư). `[i][j] = 1` nếu có đường nối trực tiếp.

```python
#         N01 N02 N03 N04 N05 N06 N07 N08
ADJACENCY_MATRIX = np.array([
    [0,  1,  0,  1,  0,  0,  0,  0],  # N01
    ...
], dtype=np.float32)
```

**Checklist:**
- Ma trận phải đối xứng (`A[i][j] == A[j][i]`)
- Chỉ kết nối ngã tư **trực tiếp** (không qua ngã tư khác)
- Không tự kết nối (`A[i][i] = 0`)

### 2.7 Đăng ký trong `__init__.py`

Thêm `elif` vào `environment/maps/__init__.py`:

```python
elif TOPOLOGY == "<map_name>":
    from environment.maps.map_<map_name> import (
        INTERSECTION_IDS,
        INCOMING_EDGES,
        OUTGOING_EDGES,
        ADJACENCY_MATRIX,
        NUM_LANES,
        EDGE_WEIGHTS,
        get_edge_lanes,
    )
```

---

## Phần 3 — Route file (gen_routes.py)

### 3.1 Cấu trúc FLOWS

```python
# (from_edge, to_edge, peak_vph, night_vph, depart_speed)
FLOWS = [
    ("EXT_W_N01_in", "N03_EXT_E_N03", 900, 120, "max"),  # Hồ Tùng Mậu Tây→Đông
    ...
]
```

**Nguyên tắc:**
- `from_edge` và `to_edge` phải là **boundary edges** (EXT_*) hoặc edges đủ xa để xe đi qua nhiều ngã tư
- `peak_vph / night_vph` tỉ lệ ~7:1 là realistic (khu đô thị Hà Nội)
- Đường xanh lá trên Google Maps = peak_vph cao (600–900), secondary = 200–350

### 3.2 Vehicle mix

```python
MIX_PEAK  = [("passenger", 0.65), ("motorcycle", 0.30), ("bus", 0.05)]
MIX_NIGHT = [("passenger", 0.55), ("motorcycle", 0.40), ("bus", 0.05)]
```

Motorcycle tăng về đêm là đặc trưng của traffic Hà Nội.

---

## Phần 4 — Checklist trước khi train

```
[ ] netconvert chạy không có error
[ ] sumo-gui <map>.sumocfg mở được, không báo lỗi detector
[ ] Số node trong INTERSECTION_IDS = số TLS trong net.xml
[ ] ADJACENCY_MATRIX đối xứng
[ ] Edge ID trong INCOMING/OUTGOING khớp với edg.xml
[ ] EDGE_WEIGHTS khai báo đúng các đường arterial thực tế
[ ] get_edge_lanes() trả về đúng số lane theo typ.xml
[ ] TOPOLOGY đã đổi trong training/config.py
[ ] build_map.py chạy thành công (gen được net.xml + routes)
```

---

## Phần 5 — Lỗi thường gặp

| Lỗi | Nguyên nhân | Fix |
|-----|-------------|-----|
| `lane not known` khi load detector | SRC node bị merge do `--geometry.remove` | Bỏ flag đó khỏi netconvert |
| `all input arrays must have the same shape` | Các ngã tư có STATE_DIM khác nhau | Kiểm tra `get_edge_lanes()` và `MAX_LANES_TOTAL` trong state_builder |
| `No module named 'training'` | Chạy sai cách | Dùng `python -m training.train` từ root |
| SUMO port conflict khi train song song | 2 model dùng chung port | Mỗi model dùng PORT riêng trong config.py |
| Route error, xe không spawn | Edge ID trong gen_routes.py sai | Kiểm tra boundary edge ID trong nod.xml/edg.xml |

---

## Ví dụ tham khảo

Map Mỹ Đình (8 ngã tư) là implementation đầy đủ nhất:
```
simulation/mydinh/
environment/maps/map_mydinh.py
```

Map 2x2 là synthetic đơn giản, dùng để hiểu cấu trúc cơ bản:
```
simulation/2x2/
environment/maps/map_2x2.py
```
