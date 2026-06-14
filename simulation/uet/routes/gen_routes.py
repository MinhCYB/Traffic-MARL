"""
gen_routes.py — Sinh routes_peak.rou.xml và routes_night.rou.xml
cho map UET (15 ngã tư — khu ĐH Công Nghệ, Cầu Giấy).

Layout:
    Row 1 (ngang lớn): N01 = N02 = N03 = N04 = N05 = N06
    Row M (ngang nhỏ):          N07 — N08 — N09 — N10
    Row 2 (ngang lớn): N11 = N12 = N13 = N14 = N15

Dọc arterial:  N01↔N11, N02↔N12, N06↔N10
Dọc secondary: N03↔N07↔N13, N04↔N08↔N14, N05↔N09↔N15, N10↔N15

Chạy:
    python gen_routes.py
Yêu cầu:
    SUMO_HOME set, duarouter trong PATH
"""

import os
import subprocess
import sys
from pathlib import Path

# Import SIM_END từ config trung tâm
sys.path.insert(0, str(Path(__file__).parents[3]))  # root project
try:
    from training.config import SIM_END
except ImportError:
    SIM_END = 1800  # fallback nếu chạy standalone không có package

SUMO_HOME = os.environ.get("SUMO_HOME", "")
if not SUMO_HOME:
    sys.exit("[ERROR] SUMO_HOME chưa được set. Export SUMO_HOME trước khi chạy.")

NET_FILE = "net/uet.net.xml"
OUT_DIR  = "routes"
os.makedirs(OUT_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════
#  FLOW DEFINITIONS
#  Format: (from_edge, to_edge, peak_vph, night_vph, depart_speed)
#
#  Traffic thực tế khu UET / Cầu Giấy:
#  - Xuân Thủy / Phạm Văn Đồng (Row 1): luồng Đông↔Tây rất lớn
#  - Nguyễn Phong Sắc / Trần Thái Tông (Row 2): luồng Đông↔Tây lớn
#  - Trục dọc N01-N11, N02-N12: vào/ra ĐH, peak sáng/chiều
#  - Trục dọc N06-N10: kết nối cao tốc, nhiều xe
#  - Đường nội bộ Row M: secondary, nhẹ hơn ~50%
# ══════════════════════════════════════════════════════════════════
FLOWS = [
    # ── Row 1 ngang: Tây → Đông (EXT_W_N01 → EXT_E_N06) ──
    ("EXT_W_N01_in",   "N06_EXT_E_N06",   900, 120, "max"),
    # ── Row 1 ngang: Đông → Tây ──
    ("EXT_E_N06_in",   "N01_EXT_W_N01",   900, 120, "max"),

    # ── Row 2 ngang: Tây → Đông (EXT_W_N11 → EXT_E_N15) ──
    ("EXT_W_N11_in",   "N15_EXT_E_N15",   750, 100, "max"),
    # ── Row 2 ngang: Đông → Tây ──
    ("EXT_E_N15_in",   "N11_EXT_W_N11",   750, 100, "max"),

    # ── Trục dọc N01-N11 (arterial): Bắc → Nam (sáng peak) ──
    ("EXT_W_N01_in",   "N11_EXT_S_N11",   600, 70,  "max"),
    # ── Trục dọc N01-N11: Nam → Bắc (chiều peak) ──
    ("EXT_S_N11_in",   "N01_EXT_W_N01",   600, 70,  "max"),

    # ── Trục dọc N02-N12 (arterial): Bắc → Nam ──
    ("EXT_W_N01_in",   "N12_SRC_R2_BC",   500, 60,  "max"),  # xe rẽ vào N12
    ("EXT_W_N11_in",   "N02_SRC_R1_BC",   500, 60,  "max"),  # ngược lại

    # ── Trục dọc N06-N10 (arterial): Bắc → Nam ──
    ("EXT_N_N06_in",   "N10_EXT_E_N10",   650, 80,  "max"),
    ("EXT_E_N10_in",   "N06_EXT_N_N06",   650, 80,  "max"),

    # ── Vào từ Bắc (Row 1) → đi về phía Nam ──
    ("EXT_N_N03_in",   "N13_EXT_S_N13",   350, 50,  "max"),
    ("EXT_N_N04_in",   "N14_EXT_S_N14",   350, 50,  "max"),
    ("EXT_N_N05_in",   "N15_EXT_S_N15",   300, 40,  "max"),

    # ── Từ Nam (Row 2) → đi về phía Bắc ──
    ("EXT_S_N13_in",   "N03_EXT_N_N03",   350, 50,  "max"),
    ("EXT_S_N14_in",   "N04_EXT_N_N04",   350, 50,  "max"),
    ("EXT_S_N15_in",   "N05_EXT_N_N05",   300, 40,  "max"),

    # ── Đường nội bộ (Row M, secondary): ngang ──
    ("EXT_W_N01_in",   "N10_EXT_E_N10",   250, 30,  "max"),  # đi qua N07-N08-N09-N10
    ("EXT_E_N10_in",   "N01_EXT_W_N01",   250, 30,  "max"),  # ngược lại

    # ── Luồng cục bộ: vào/ra cổng trường (N07 khu vực cổng UET) ──
    ("EXT_N_N03_in",   "N07_SRC_V3S",     200, 50,  "max"),  # sinh viên vào
    ("EXT_W_N01_in",   "N07_SRC_RM_AB",   200, 50,  "max"),  # sinh viên ra

    # ── Đường cong N10-N15 ──
    ("EXT_E_N10_in",   "N15_EXT_S_N15",   200, 30,  "max"),
    ("EXT_S_N15_in",   "N10_EXT_E_N10",   200, 30,  "max"),
]

# ══════════════════════════════════════════════════════════════════
#  VEHICLE MIX
#  Motorcycle cao — đặc trưng traffic Hà Nội
# ══════════════════════════════════════════════════════════════════
MIX_PEAK  = [("passenger", 0.60), ("motorcycle", 0.35), ("bus", 0.05)]
MIX_NIGHT = [("passenger", 0.50), ("motorcycle", 0.45), ("bus", 0.05)]

VEHICLE_TYPES = """    <vType id="passenger"   vClass="passenger"   length="4.5" maxSpeed="16.67" accel="2.6" decel="4.5" sigma="0.5"/>
    <vType id="motorcycle"  vClass="motorcycle"  length="2.2" maxSpeed="16.67" accel="3.0" decel="5.0" sigma="0.6"/>
    <vType id="bus"         vClass="bus"         length="12"  maxSpeed="13.89" accel="1.5" decel="3.5" sigma="0.3"/>"""


def gen_flows(mix, suffix):
    # Scale vehsPerHour để giữ mật độ xe khi episode ngắn hơn 3600s
    # Ví dụ: SIM_END=1800 → SCALE=2.0 → xe vẫn đến với tốc độ thực tế
    SCALE = 3600 / SIM_END
    lines = []
    fid = 0
    for (frm, to, peak_vph, night_vph, dspeed) in FLOWS:
        vph = peak_vph if suffix == "peak" else night_vph
        for (vtype, ratio) in mix:
            count = max(1, int(vph * ratio * SCALE))
            lines.append(
                f'    <flow id="f{fid}_{vtype}" type="{vtype}" '
                f'from="{frm}" to="{to}" '
                f'begin="0" end="{SIM_END}" vehsPerHour="{count}" '
                f'departSpeed="{dspeed}" departLane="best"/>'
            )
            fid += 1
    return "\n".join(lines)


for suffix, mix in [("peak", MIX_PEAK), ("night", MIX_NIGHT)]:
    rou_path = f"{OUT_DIR}/routes_{suffix}.rou.xml"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">

{VEHICLE_TYPES}

{gen_flows(mix, suffix)}

</routes>
"""
    with open(rou_path, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"[OK] Đã sinh {rou_path}")

print("\n[DONE] Sinh routes hoàn tất. Build net trước khi chạy SUMO:")
print("       python ../../scripts/build_map.py uet")