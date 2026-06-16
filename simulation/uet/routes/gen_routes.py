"""
gen_routes.py — Sinh 3 file routes cho map UET (15 ngã tư, khu Cầu Giấy):
  - routes_peak_morning.rou.xml  : Peak sáng 7-9h  (Sink cao — SV/GV đổ vào trường)
  - routes_peak_evening.rou.xml  : Peak chiều 17-19h (Source cao — tan học/làm ra về)
  - routes_night.rou.xml         : Ban đêm 22h-5h   (tất cả thấp)

Layout UET:
    Row 1 (Xuân Thủy / Phạm Văn Đồng): N01=N02=N03=N04=N05=N06
    Row M (đường nội bộ):                      N07—N08—N09—N10
    Row 2 (Nguyễn Phong Sắc):          N11=N12=N13=N14=N15

Tỉ lệ thiết kế:
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
    <vType id="passenger"  vClass="passenger"  length="4.5"  maxSpeed="16.67" accel="2.6" decel="4.5" sigma="0.5"/>
    <vType id="motorcycle" vClass="motorcycle" length="2.2"  maxSpeed="16.67" accel="3.0" decel="5.0" sigma="0.6"/>
    <vType id="bus"        vClass="bus"        length="12.0" maxSpeed="13.89" accel="1.5" decel="3.5" sigma="0.3"/>"""

MIX_PEAK  = [("passenger", 0.60), ("motorcycle", 0.35), ("bus", 0.05)]
MIX_NIGHT = [("passenger", 0.50), ("motorcycle", 0.45), ("bus", 0.05)]

# ══════════════════════════════════════════════════════════════════
#  FLOWS
#  Format: (from_edge, to_edge, type, morning_vph, evening_vph, night_vph)
#  type: "through" | "sink" | "source"
#
#  Through  = xe đi qua khu vực (commuter, xe tải đường dài)
#  Sink     = xe đi VÀO khu vực rồi dừng (SV/GV đến trường, đi làm)
#  Source   = xe từ khu vực đi RA (tan học/làm, ra về)
# ══════════════════════════════════════════════════════════════════
FLOWS = [
    # ────────────────────────────────────────────────────────────
    #  ROW 1 — XUÂN THỦY / PHẠM VĂN ĐỒNG (arterial ngang lớn nhất)
    #  Through: xe vượt qua không dừng
    # ────────────────────────────────────────────────────────────
    ("EXT_W_N01_in", "N06_EXT_E_N06", "through",  900,  900, 120),  # T→Đ
    ("EXT_E_N06_in", "N01_EXT_W_N01", "through",  900,  900, 120),  # Đ→T

    # ────────────────────────────────────────────────────────────
    #  ROW 2 — NGUYỄN PHONG SẮC / TRẦN THÁI TÔNG (arterial ngang)
    # ────────────────────────────────────────────────────────────
    ("EXT_W_N11_in", "N15_EXT_E_N15", "through",  750,  750, 100),  # T→Đ
    ("EXT_E_N15_in", "N11_EXT_W_N11", "through",  750,  750, 100),  # Đ→T

    # ────────────────────────────────────────────────────────────
    #  TRỤC DỌC N01↔N11 (arterial dọc lớn nhất)
    #  Sáng: Bắc→Nam (Sink — vào trường/cơ quan)
    #  Chiều: Nam→Bắc (Source — tan học/làm ra về)
    # ────────────────────────────────────────────────────────────
    ("EXT_W_N01_in", "N11_EXT_S_N11", "sink",     360,  120,  70),  # Bắc→Nam
    ("EXT_S_N11_in", "N01_EXT_W_N01", "source",   120,  360,  70),  # Nam→Bắc

    # ────────────────────────────────────────────────────────────
    #  TRỤC DỌC N02↔N12
    # ────────────────────────────────────────────────────────────
    ("EXT_W_N01_in", "N12_SRC_R2_BC", "sink",     300,  100,  60),
    ("EXT_W_N11_in", "N02_SRC_R1_BC", "source",   100,  300,  60),

    # ────────────────────────────────────────────────────────────
    #  TRỤC DỌC N06↔N10 (kết nối cao tốc)
    # ────────────────────────────────────────────────────────────
    ("EXT_N_N06_in", "N10_EXT_E_N10", "sink",     390,  130,  80),  # Bắc→Nam
    ("EXT_E_N10_in", "N06_EXT_N_N06", "source",   130,  390,  80),  # Nam→Bắc

    # ────────────────────────────────────────────────────────────
    #  TRỤC DỌC SECONDARY (N03↔N13, N04↔N14, N05↔N15)
    # ────────────────────────────────────────────────────────────
    ("EXT_N_N03_in", "N13_EXT_S_N13", "sink",     210,   70,  50),
    ("EXT_S_N13_in", "N03_EXT_N_N03", "source",    70,  210,  50),

    ("EXT_N_N04_in", "N14_EXT_S_N14", "sink",     210,   70,  50),
    ("EXT_S_N14_in", "N04_EXT_N_N04", "source",    70,  210,  50),

    ("EXT_N_N05_in", "N15_EXT_S_N15", "sink",     180,   60,  40),
    ("EXT_S_N15_in", "N05_EXT_N_N05", "source",    60,  180,  40),

    # ────────────────────────────────────────────────────────────
    #  ROW M — ĐƯỜNG NỘI BỘ (secondary ngang)
    # ────────────────────────────────────────────────────────────
    ("EXT_W_N01_in", "N10_EXT_E_N10", "through",  250,  250,  30),
    ("EXT_E_N10_in", "N01_EXT_W_N01", "through",  250,  250,  30),

    # ────────────────────────────────────────────────────────────
    #  CỔNG TRƯỜNG UET (N07) — Sink sáng, Source chiều mạnh hơn trung bình
    # ────────────────────────────────────────────────────────────
    ("EXT_N_N03_in", "N07_SRC_V3S",   "sink",     240,   80,  50),  # SV vào
    ("EXT_W_N01_in", "N07_SRC_RM_AB", "source",    80,  240,  50),  # SV ra

    # ────────────────────────────────────────────────────────────
    #  N10↔N15 — đường cong góc
    # ────────────────────────────────────────────────────────────
    ("EXT_E_N10_in", "N15_EXT_S_N15", "through",  200,  200,  30),
    ("EXT_S_N15_in", "N10_EXT_E_N10", "through",  200,  200,  30),
]

# ══════════════════════════════════════════════════════════════════
def write_rou(filename, scenario, mix, duration=SIM_END):
    col = {"morning": 3, "evening": 4, "night": 5}[scenario]
    SCALE = 3600 / duration

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
    print("  routes_peak_morning.rou.xml — Peak sáng 7-9h    (Sink cao — SV/GV vào trường)")
    print("  routes_peak_evening.rou.xml — Peak chiều 17-19h (Source cao — tan học ra về)")
    print("  routes_night.rou.xml        — Ban đêm 22h-5h    (tất cả thấp)")
    print()
    print("  Through / Sink / Source ratio theo giờ:")
    print("    Sáng  : 60% / 30% / 10%")
    print("    Chiều : 60% / 10% / 30%")
    print("    Đêm   : 50% / 25% / 25%")