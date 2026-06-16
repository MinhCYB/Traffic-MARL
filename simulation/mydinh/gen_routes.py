"""
gen_routes.py — Sinh 3 file routes cho map Mỹ Đình 8 ngã tư:
  - routes_peak_morning.rou.xml  : Peak sáng 7-9h  (Sink cao — người đổ vào trung tâm)
  - routes_peak_evening.rou.xml  : Peak chiều 17-19h (Source cao — tan làm ra về)
  - routes_night.rou.xml         : Ban đêm 22h-5h   (tất cả thấp)

Tỉ lệ thiết kế theo giờ:
  Peak sáng  : Through 60% / Sink 30% / Source 10%
  Peak chiều : Through 60% / Source 30% / Sink 10%
  Ban đêm    : Through 50% / Sink 25% / Source 25%

Chạy: python gen_routes.py
"""

import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))
try:
    from training.config import SIM_END
except ImportError:
    SIM_END = 1800

OUT_DIR = "routes"
os.makedirs(OUT_DIR, exist_ok=True)

# ══════════════════════════════════════════════════════════════════
#  VEHICLE TYPES
# ══════════════════════════════════════════════════════════════════
VTYPES = """\
    <vType id="passenger"  vClass="passenger"  length="4.5"  maxSpeed="16.67" accel="2.6" decel="4.5" sigma="0.5" color="0.7,0.7,1.0"/>
    <vType id="motorcycle" vClass="motorcycle" length="2.0"  maxSpeed="19.44" accel="3.5" decel="5.0" sigma="0.6" color="1.0,0.6,0.0"/>
    <vType id="bus"        vClass="bus"        length="12.0" maxSpeed="13.89" accel="1.2" decel="3.5" sigma="0.3" color="0.2,0.8,0.2"/>"""

MIX_PEAK  = [("passenger", 0.65), ("motorcycle", 0.30), ("bus", 0.05)]
MIX_NIGHT = [("passenger", 0.55), ("motorcycle", 0.40), ("bus", 0.05)]

# ══════════════════════════════════════════════════════════════════
#  FLOWS
#  Format: (from_edge, to_edge, type, morning_vph, evening_vph, night_vph)
#  type: "through" | "sink" | "source"
#
#  Through  = xe đi qua khu vực (commuter, xe tải đường dài)
#  Sink     = xe đi VÀO trung tâm rồi dừng (đi làm, mua sắm)
#  Source   = xe từ trung tâm đi RA (tan làm, ra về)
#
#  Tổng BASE_VPH mỗi corridor:
#  Hồ Tùng Mậu (arterial ngang): 1500 vph
#  Lê Đức Thọ / Phạm Hùng (arterial dọc): 1000 vph
#  Secondary: 400-600 vph
# ══════════════════════════════════════════════════════════════════
FLOWS = [
    # ────────────────────────────────────────────────────────────
    #  HỒ TÙNG MẬU — ngang Đông↔Tây (arterial chính)
    #  Through: xe vượt qua không dừng
    # ────────────────────────────────────────────────────────────
    ("EXT_E_N03_in", "N01_EXT_W_N01", "through",  900,  900, 120),  # Đ→T
    ("EXT_W_N01_in", "N03_EXT_E_N03", "through",  900,  900, 120),  # T→Đ

    # ────────────────────────────────────────────────────────────
    #  LÊ ĐỨC THỌ — dọc Bắc↔Nam (arterial thứ 2)
    #  Sáng: Bắc→Nam nhiều (Sink — vào trung tâm làm việc)
    #  Chiều: Nam→Bắc nhiều (Source — tan làm về)
    # ────────────────────────────────────────────────────────────
    ("EXT_N_N02_in", "N08_EXT_S_N08", "sink",     420,  140,  80),  # Bắc→Nam
    ("EXT_S_N08_in", "N02_EXT_N_N02", "source",   140,  420,  80),  # Nam→Bắc

    # ────────────────────────────────────────────────────────────
    #  PHẠM HÙNG — dọc Bắc↔Nam
    # ────────────────────────────────────────────────────────────
    ("EXT_N_N03_in", "N06_EXT_E_N06", "sink",     360,  120,  70),  # Bắc→Nam
    ("EXT_E_N06_in", "N03_EXT_N_N03", "source",   120,  360,  70),  # Nam→Bắc

    # ────────────────────────────────────────────────────────────
    #  NGUYỄN CƠ THẠCH — dọc secondary
    # ────────────────────────────────────────────────────────────
    ("EXT_N_N01_in", "N07_EXT_S_N07", "sink",     200,   65,  50),
    ("EXT_S_N07_in", "N01_EXT_N_N01", "source",    65,  200,  50),

    # ────────────────────────────────────────────────────────────
    #  HÀM NGHI — ngang secondary
    # ────────────────────────────────────────────────────────────
    ("EXT_W_N04_in", "N05_SRC_LDT_N", "through",  300,  300,  40),

    # ────────────────────────────────────────────────────────────
    #  TRẦN HỮU DỨC — ngang secondary
    # ────────────────────────────────────────────────────────────
    ("EXT_W_N07_in", "N08_EXT_S_N08", "through",  250,  250,  35),
    ("EXT_S_N08_in", "N07_EXT_W_N07", "through",  250,  250,  35),

    # ────────────────────────────────────────────────────────────
    #  INTERNAL TURNS
    #  Xe từ Hồ Tùng Mậu rẽ vào Lê Đức Thọ (Sink sáng, Source chiều)
    # ────────────────────────────────────────────────────────────
    ("EXT_W_N01_in", "N05_SRC_LDT_S", "sink",     120,   40,  25),
    ("EXT_E_N03_in", "N05_SRC_LDT_S", "sink",     120,   40,  25),

    # Xe từ Phạm Hùng rẽ ra Hồ Tùng Mậu (Source chiều)
    ("EXT_N_N03_in", "N01_EXT_W_N01", "source",    50,  150,  20),
]

# ══════════════════════════════════════════════════════════════════
def write_rou(filename, scenario, mix, duration=SIM_END):
    """
    scenario: "morning" | "evening" | "night"
    Chọn cột vph tương ứng từ FLOWS.
    """
    col = {"morning": 3, "evening": 4, "night": 5}[scenario]
    SCALE = 3600 / duration  # giữ mật độ thực tế dù episode ngắn

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"',
        '        xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">',
        "",
        "    <!-- Vehicle types -->",
        VTYPES,
        "",
        f"    <!-- Scenario: {scenario} | scale x{SCALE:.1f} -->",
    ]

    fid = 0
    for row in FLOWS:
        from_e, to_e, ftype = row[0], row[1], row[2]
        vph = row[col]
        for vtype, ratio in mix:
            scaled = max(1, int(vph * ratio * SCALE))
            lines.append(
                f'    <flow id="f{fid}" type="{vtype}" from="{from_e}" to="{to_e}"'
                f' begin="0" end="{duration}" vehsPerHour="{scaled}"'
                f' departSpeed="max" departLane="best"/>'
                f'    <!-- {ftype} -->'
            )
            fid += 1

    lines += ["", "</routes>"]
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    total_vph = sum(row[col] for row in FLOWS)
    print(f"[OK] {filename}  ({fid} flows, {total_vph} vph tổng, scale×{SCALE:.1f})")


# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    write_rou(f"{OUT_DIR}/routes_peak_morning.rou.xml", "morning", MIX_PEAK)
    write_rou(f"{OUT_DIR}/routes_peak_evening.rou.xml", "evening", MIX_PEAK)
    write_rou(f"{OUT_DIR}/routes_night.rou.xml",        "night",   MIX_NIGHT)

    print("\nDone!")
    print("  routes_peak_morning.rou.xml — Peak sáng 7-9h   (Sink cao)")
    print("  routes_peak_evening.rou.xml — Peak chiều 17-19h (Source cao)")
    print("  routes_night.rou.xml        — Ban đêm 22h-5h    (tất cả thấp)")
    print()
    print("  Through / Sink / Source ratio theo giờ:")
    print("    Sáng  : 60% / 30% / 10%")
    print("    Chiều : 60% / 10% / 30%")
    print("    Đêm   : 50% / 25% / 25%")