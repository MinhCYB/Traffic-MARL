"""
gen_routes.py — Sinh routes_peak.rou.xml và routes_night.rou.xml
cho map Mỹ Đình 8 ngã tư.

Dùng SUMO randomTrips.py làm backend, nhưng override với flow definitions
để kiểm soát chính xác mật độ theo từng corridor.

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

NET_FILE  = "net/mydinh.net.xml"
OUT_DIR   = "routes"
os.makedirs(OUT_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════
#  FLOW DEFINITIONS
#  Mỗi flow: (edge_from, edge_to, vehsPerHour_peak, vehsPerHour_night)
#
#  Logic traffic thực tế khu Mỹ Đình:
#  - Hồ Tùng Mậu (ngang): luồng Đông↔Tây rất lớn cả 2 chiều
#  - Lê Đức Thọ / Phạm Hùng (dọc): luồng Bắc→Nam sáng, Nam→Bắc chiều
#  - Nguyễn Cơ Thạch, Hàm Nghi: secondary, nhẹ hơn ~50%
#
#  Format: (from_edge, to_edge, peak_vph, night_vph, depart_speed)
# ══════════════════════════════════════════════════════════════════
FLOWS = [
    # ── Hồ Tùng Mậu: Đông → Tây (vào từ EXT_E_N03, ra EXT_W_N01) ──
    ("EXT_E_N03_in",  "N01_EXT_W_N01",  900, 120, "max"),
    # ── Hồ Tùng Mậu: Tây → Đông ──
    ("EXT_W_N01_in",  "N03_EXT_E_N03",  900, 120, "max"),

    # ── Lê Đức Thọ: Bắc → Nam (sáng peak) ──
    ("EXT_N_N02_in",  "N08_EXT_S_N08",  700, 80,  "max"),
    # ── Lê Đức Thọ: Nam → Bắc (chiều peak) ──
    ("EXT_S_N08_in",  "N02_EXT_N_N02",  700, 80,  "max"),

    # ── Phạm Hùng: Bắc → Nam ──
    ("EXT_N_N03_in",  "N06_EXT_E_N06",  600, 70,  "max"),
    # ── Phạm Hùng: Nam → Bắc (từ EXT_E_N06 lên N03) ──
    ("EXT_E_N06_in",  "N03_EXT_N_N03",  600, 70,  "max"),

    # ── Nguyễn Cơ Thạch: dọc Bắc-Nam ──
    ("EXT_N_N01_in",  "N07_EXT_S_N07",  350, 50,  "max"),
    ("EXT_S_N07_in",  "N01_EXT_N_N01",  350, 50,  "max"),

    # ── Hàm Nghi: ngang Tây-Đông ──
    ("EXT_W_N04_in",  "N05_SRC_LDT_N",  300, 40,  "max"),  # sang N05
    ("EXT_W_N07_in",  "N07_EXT_W_N07",  200, 30,  "max"),  # quay đầu (local)

    # ── Trần Hữu Dực: ngang ──
    ("EXT_W_N07_in",  "N08_EXT_S_N08",  250, 35,  "max"),
    ("EXT_S_N08_in",  "N07_EXT_W_N07",  250, 35,  "max"),

    # ── Internal turns: xe từ Hồ Tùng Mậu rẽ vào Lê Đức Thọ ──
    ("EXT_W_N01_in",  "N05_SRC_LDT_S",  200, 25,  "max"),
    ("EXT_E_N03_in",  "N05_SRC_LDT_S",  200, 25,  "max"),

    # ── Internal turns: xe từ Phạm Hùng rẽ vào Hồ Tùng Mậu ──
    ("EXT_N_N03_in",  "N01_EXT_W_N01",  150, 20,  "max"),
]

# ══════════════════════════════════════════════════════════════════
#  VEHICLE TYPES
# ══════════════════════════════════════════════════════════════════
VTYPES = """    <vType id="passenger" vClass="passenger" length="4.5" maxSpeed="16.67"
           accel="2.6" decel="4.5" sigma="0.5" color="0.7,0.7,1.0"/>
    <vType id="motorcycle" vClass="motorcycle" length="2.0" maxSpeed="19.44"
           accel="3.5" decel="5.0" sigma="0.6" color="1.0,0.6,0.0"/>
    <vType id="bus" vClass="bus" length="12.0" maxSpeed="13.89"
           accel="1.2" decel="3.5" sigma="0.3" color="0.2,0.8,0.2"/>
"""

# Tỉ lệ phương tiện: peak vs night
MIX_PEAK  = [("passenger", 0.65), ("motorcycle", 0.30), ("bus", 0.05)]
MIX_NIGHT = [("passenger", 0.55), ("motorcycle", 0.40), ("bus", 0.05)]

# ══════════════════════════════════════════════════════════════════
def write_rou(filename: str, flows_vph: list, mix: list, duration: int = SIM_END):
    """Ghi file .rou.xml với flow definitions.
    
    vehsPerHour được scale theo tỉ lệ 3600/duration để giữ mật độ xe
    thực tế bất kể episode dài bao lâu.
    """
    SCALE = 3600 / duration  # = 2.0 nếu duration=1800
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
             '        xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">',
             "",
             "    <!-- Vehicle types -->",
             VTYPES]

    flow_id = 0
    for (from_e, to_e, vph, depart_speed) in flows_vph:
        for vtype, ratio in mix:
            scaled_vph = max(1, int(vph * ratio * SCALE))
            lines.append(
                f'    <flow id="f{flow_id}" type="{vtype}" '
                f'from="{from_e}" to="{to_e}" '
                f'begin="0" end="{duration}" '
                f'vehsPerHour="{scaled_vph}" '
                f'departSpeed="{depart_speed}" '
                f'departLane="best"/>'
            )
            flow_id += 1

    lines += ["", "</routes>"]
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[OK] {filename}  ({flow_id} flows, end={duration}s, scale×{SCALE:.1f})")


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Peak: dùng vph_peak (index 2)
    peak_flows  = [(f, t, p, spd) for f, t, p, _, spd in FLOWS]
    # Night: dùng vph_night (index 3)
    night_flows = [(f, t, n, spd) for f, t, _, n, spd in FLOWS]

    write_rou(f"{OUT_DIR}/routes_peak.rou.xml",  peak_flows,  MIX_PEAK)
    write_rou(f"{OUT_DIR}/routes_night.rou.xml", night_flows, MIX_NIGHT)

    print("\nDone! Files saved to routes/")
    print("  routes_peak.rou.xml  — giờ cao điểm (7-9h, 17-19h)")
    print("  routes_night.rou.xml — ban đêm (22h-5h)")