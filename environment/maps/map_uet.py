"""
map_uet.py — Topology data cho map UET (15 ngã tư — khu ĐH Công Nghệ, Cầu Giấy)

Layout:
    N01 = N02 = N03 = N04 = N05 = N06   ← Row 1 (Xuân Thủy / Phạm Văn Đồng, arterial)
     |     |     |     |     |     |
    N11   N12   N07 ─ N08 ─ N09 ─ N10   ← Row M (đường nội bộ, secondary) + N11,N12
     |     |     |     |     |
    N11 = N12 = N13 = N14 = N15         ← Row 2 (Nguyễn Phong Sắc, arterial)

Chi tiết kết nối:
    Ngang arterial Row 1:  N01─N02─N03─N04─N05─N06
    Ngang arterial Row 2:  N11─N12─N13─N14─N15
    Ngang secondary Row M: N07─N08─N09─N10
    Dọc arterial:          N01─N11, N02─N12, N06─N10
    Dọc secondary:         N03─N07─N13, N04─N08─N14, N05─N09─N15, N10─N15

Ngã 3 (xanh): N01, N02, N07, N12
Ngã 4 (đỏ):   N03, N04, N05, N06, N08, N09, N10, N11, N13, N14, N15
"""

import numpy as np

INTERSECTION_IDS = [
    "N01", "N02", "N03", "N04", "N05", "N06",
    "N07", "N08", "N09", "N10",
    "N11", "N12", "N13", "N14", "N15",
]

# ══════════════════════════════════════════════════════════════════
#  EDGE LANES — số lane của mỗi incoming edge
#  arterial = 3, secondary/outskirts = 2 (DEFAULT_LANES)
# ══════════════════════════════════════════════════════════════════
EDGE_LANES = {
    # ── Row 1 arterial (3 làn) ──
    "SRC_R1_AB_N01": 3, "SRC_R1_AB_N02": 3,
    "SRC_R1_BC_N02": 3, "SRC_R1_BC_N03": 3,
    "SRC_R1_CD_N03": 3, "SRC_R1_CD_N04": 3,
    "SRC_R1_DE_N04": 3, "SRC_R1_DE_N05": 3,
    "SRC_R1_EF_N05": 3, "SRC_R1_EF_N06": 3,

    # ── Row 2 arterial (3 làn) ──
    "SRC_R2_AB_N11": 3, "SRC_R2_AB_N12": 3,
    "SRC_R2_BC_N12": 3, "SRC_R2_BC_N13": 3,
    "SRC_R2_CD_N13": 3, "SRC_R2_CD_N14": 3,
    "SRC_R2_DE_N14": 3, "SRC_R2_DE_N15": 3,

    # ── Dọc arterial (3 làn) ──
    "SRC_V1_N01": 3, "SRC_V1_N11": 3,
    "SRC_V2_N02": 3, "SRC_V2_N12": 3,
    "SRC_V6_N06": 3, "SRC_V6_N10": 3,

    # ── Boundary arterial (2 làn — outskirts) ──
    # Tất cả EXT_* mặc định 2 làn → không cần khai báo
}
DEFAULT_LANES = 2


def get_edge_lanes(edge_id: str) -> int:
    return EDGE_LANES.get(edge_id, DEFAULT_LANES)


# ══════════════════════════════════════════════════════════════════
#  INCOMING / OUTGOING EDGES
# ══════════════════════════════════════════════════════════════════
INCOMING_EDGES = {
    # Ngã 3: N01 — có Tây (boundary), Đông (Row 1), Nam (dọc V1)
    "N01": [
        "EXT_W_N01_in",    # từ Tây vào
        "SRC_R1_AB_N01",   # từ Đông (N02) vào
        "SRC_V1_N01",      # từ Nam (N11) vào
    ],
    # Ngã 3: N02 — có Tây (N01), Đông (N03), Nam (dọc V2)
    "N02": [
        "SRC_R1_AB_N02",   # từ Tây (N01)
        "SRC_R1_BC_N02",   # từ Đông (N03)
        "SRC_V2_N02",      # từ Nam (N12)
    ],
    # Ngã 4: N03
    "N03": [
        "EXT_N_N03_in",    # từ Bắc (boundary)
        "SRC_R1_BC_N03",   # từ Tây (N02)
        "SRC_R1_CD_N03",   # từ Đông (N04)
        "SRC_V3N_N03",     # từ Nam (N07)
    ],
    # Ngã 4: N04
    "N04": [
        "EXT_N_N04_in",
        "SRC_R1_CD_N04",   # từ Tây (N03)
        "SRC_R1_DE_N04",   # từ Đông (N05)
        "SRC_V4N_N04",     # từ Nam (N08)
    ],
    # Ngã 4: N05
    "N05": [
        "EXT_N_N05_in",
        "SRC_R1_DE_N05",   # từ Tây (N04)
        "SRC_R1_EF_N05",   # từ Đông (N06)
        "SRC_V5N_N05",     # từ Nam (N09)
    ],
    # Ngã 4: N06
    "N06": [
        "EXT_N_N06_in",
        "EXT_E_N06_in",
        "SRC_R1_EF_N06",   # từ Tây (N05)
        "SRC_V6_N06",      # từ Nam (N10)
    ],
    # Ngã 3: N07 — có Bắc (N03), Đông (N08), Nam (N13)
    "N07": [
        "SRC_V3N_N07",     # từ Bắc (N03)
        "SRC_RM_AB_N07",   # từ Đông (N08)
        "SRC_V3S_N07",     # từ Nam (N13)
    ],
    # Ngã 4: N08
    "N08": [
        "SRC_V4N_N08",     # từ Bắc (N04)
        "SRC_RM_AB_N08",   # từ Tây (N07)
        "SRC_RM_BC_N08",   # từ Đông (N09)
        "SRC_V4S_N08",     # từ Nam (N14)
    ],
    # Ngã 4: N09
    "N09": [
        "SRC_V5N_N09",     # từ Bắc (N05)
        "SRC_RM_BC_N09",   # từ Tây (N08)
        "SRC_RM_CD_N09",   # từ Đông (N10)
        "SRC_V5S_N09",     # từ Nam (N15)
    ],
    # Ngã 4: N10
    "N10": [
        "SRC_RM_CD_N10",   # từ Tây (N09)
        "EXT_E_N10_in",    # từ Đông (boundary)
        "SRC_V6_N10",      # từ Bắc (N06)
        "SRC_V10_N10",     # từ Nam-Tây (N15, đường cong)
    ],
    # Ngã 4: N11
    "N11": [
        "EXT_W_N11_in",
        "EXT_S_N11_in",
        "SRC_R2_AB_N11",   # từ Đông (N12)
        "SRC_V1_N11",      # từ Bắc (N01)
    ],
    # Ngã 3: N12 — có Tây (N11), Bắc (N02), Đông (N13)
    "N12": [
        "SRC_R2_AB_N12",   # từ Tây (N11)
        "SRC_V2_N12",      # từ Bắc (N02)
        "SRC_R2_BC_N12",   # từ Đông (N13)
    ],
    # Ngã 4: N13
    "N13": [
        "SRC_V3S_N13",     # từ Bắc (N07)
        "SRC_R2_BC_N13",   # từ Tây (N12)
        "SRC_R2_CD_N13",   # từ Đông (N14)
        "EXT_S_N13_in",
    ],
    # Ngã 4: N14
    "N14": [
        "SRC_V4S_N14",     # từ Bắc (N08)
        "SRC_R2_CD_N14",   # từ Tây (N13)
        "SRC_R2_DE_N14",   # từ Đông (N15)
        "EXT_S_N14_in",
    ],
    # Ngã 4: N15
    "N15": [
        "SRC_V5S_N15",     # từ Bắc (N09)
        "SRC_R2_DE_N15",   # từ Tây (N14)
        "EXT_E_N15_in",
        "SRC_V10_N15",     # từ Bắc-Đông (N10, đường cong)
        "EXT_S_N15_in",
    ],
}

OUTGOING_EDGES = {
    "N01": [
        "N01_EXT_W_N01",
        "N01_SRC_R1_AB",   # sang N02
        "N01_SRC_V1",      # xuống N11
    ],
    "N02": [
        "N02_SRC_R1_AB",   # sang N01
        "N02_SRC_R1_BC",   # sang N03
        "N02_SRC_V2",      # xuống N12
    ],
    "N03": [
        "N03_EXT_N_N03",
        "N03_SRC_R1_BC",   # sang N02
        "N03_SRC_R1_CD",   # sang N04
        "N03_SRC_V3N",     # xuống N07
    ],
    "N04": [
        "N04_EXT_N_N04",
        "N04_SRC_R1_CD",   # sang N03
        "N04_SRC_R1_DE",   # sang N05
        "N04_SRC_V4N",     # xuống N08
    ],
    "N05": [
        "N05_EXT_N_N05",
        "N05_SRC_R1_DE",   # sang N04
        "N05_SRC_R1_EF",   # sang N06
        "N05_SRC_V5N",     # xuống N09
    ],
    "N06": [
        "N06_EXT_N_N06",
        "N06_EXT_E_N06",
        "N06_SRC_R1_EF",   # sang N05
        "N06_SRC_V6",      # xuống N10
    ],
    "N07": [
        "N07_SRC_V3N",     # lên N03
        "N07_SRC_RM_AB",   # sang N08
        "N07_SRC_V3S",     # xuống N13
    ],
    "N08": [
        "N08_SRC_V4N",     # lên N04
        "N08_SRC_RM_AB",   # sang N07
        "N08_SRC_RM_BC",   # sang N09
        "N08_SRC_V4S",     # xuống N14
    ],
    "N09": [
        "N09_SRC_V5N",     # lên N05
        "N09_SRC_RM_BC",   # sang N08
        "N09_SRC_RM_CD",   # sang N10
        "N09_SRC_V5S",     # xuống N15
    ],
    "N10": [
        "N10_SRC_RM_CD",   # sang N09
        "N10_EXT_E_N10",
        "N10_SRC_V6",      # lên N06
        "N10_SRC_V10",     # đường cong sang N15
    ],
    "N11": [
        "N11_EXT_W_N11",
        "N11_EXT_S_N11",
        "N11_SRC_R2_AB",   # sang N12
        "N11_SRC_V1",      # lên N01
    ],
    "N12": [
        "N12_SRC_R2_AB",   # sang N11
        "N12_SRC_V2",      # lên N02
        "N12_SRC_R2_BC",   # sang N13
    ],
    "N13": [
        "N13_SRC_V3S",     # lên N07
        "N13_SRC_R2_BC",   # sang N12
        "N13_SRC_R2_CD",   # sang N14
        "N13_EXT_S_N13",
    ],
    "N14": [
        "N14_SRC_V4S",     # lên N08
        "N14_SRC_R2_CD",   # sang N13
        "N14_SRC_R2_DE",   # sang N15
        "N14_EXT_S_N14",
    ],
    "N15": [
        "N15_SRC_V5S",     # lên N09
        "N15_SRC_R2_DE",   # sang N14
        "N15_EXT_E_N15",
        "N15_SRC_V10",     # đường cong sang N10
        "N15_EXT_S_N15",
    ],
}

NUM_LANES = 2  # default, dùng get_edge_lanes() cho chính xác

# ══════════════════════════════════════════════════════════════════
#  EDGE WEIGHTS — tầm quan trọng thực tế
#  Mặc định = 1.0, chỉ khai báo các edge có weight khác
# ══════════════════════════════════════════════════════════════════
EDGE_WEIGHTS = {
    # Row 1 arterial — Xuân Thủy / Phạm Văn Đồng (đường trục, 900 veh/h peak)
    "SRC_R1_AB_N01": 2.0, "SRC_R1_AB_N02": 2.0,
    "SRC_R1_BC_N02": 2.0, "SRC_R1_BC_N03": 2.0,
    "SRC_R1_CD_N03": 2.0, "SRC_R1_CD_N04": 2.0,
    "SRC_R1_DE_N04": 2.0, "SRC_R1_DE_N05": 2.0,
    "SRC_R1_EF_N05": 2.0, "SRC_R1_EF_N06": 2.0,

    # Row 2 arterial — Nguyễn Phong Sắc (750 veh/h peak)
    "SRC_R2_AB_N11": 1.8, "SRC_R2_AB_N12": 1.8,
    "SRC_R2_BC_N12": 1.8, "SRC_R2_BC_N13": 1.8,
    "SRC_R2_CD_N13": 1.8, "SRC_R2_CD_N14": 1.8,
    "SRC_R2_DE_N14": 1.8, "SRC_R2_DE_N15": 1.8,

    # Dọc arterial N01-N11 (600 veh/h peak)
    "SRC_V1_N01": 1.8, "SRC_V1_N11": 1.8,

    # Dọc arterial N02-N12
    "SRC_V2_N02": 1.6, "SRC_V2_N12": 1.6,

    # Dọc arterial N06-N10 (650 veh/h peak)
    "SRC_V6_N06": 1.8, "SRC_V6_N10": 1.8,
}

# ══════════════════════════════════════════════════════════════════
#  ADJACENCY MATRIX — 15×15
#  Index theo INTERSECTION_IDS: N01=0, N02=1, ..., N15=14
#
#  Kết nối trực tiếp:
#    Row 1: N01-N02, N02-N03, N03-N04, N04-N05, N05-N06
#    Row M: N07-N08, N08-N09, N09-N10
#    Row 2: N11-N12, N12-N13, N13-N14, N14-N15
#    Dọc:   N01-N11, N02-N12, N03-N07, N04-N08, N05-N09, N06-N10
#           N07-N13, N08-N14, N09-N15, N10-N15
# ══════════════════════════════════════════════════════════════════
#         N01 N02 N03 N04 N05 N06 N07 N08 N09 N10 N11 N12 N13 N14 N15
ADJACENCY_MATRIX = np.array([
    [0,  1,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  0],  # N01
    [1,  0,  1,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0],  # N02
    [0,  1,  0,  1,  0,  0,  1,  0,  0,  0,  0,  0,  0,  0,  0],  # N03
    [0,  0,  1,  0,  1,  0,  0,  1,  0,  0,  0,  0,  0,  0,  0],  # N04
    [0,  0,  0,  1,  0,  1,  0,  0,  1,  0,  0,  0,  0,  0,  0],  # N05
    [0,  0,  0,  0,  1,  0,  0,  0,  0,  1,  0,  0,  0,  0,  0],  # N06
    [0,  0,  1,  0,  0,  0,  0,  1,  0,  0,  0,  0,  1,  0,  0],  # N07
    [0,  0,  0,  1,  0,  0,  1,  0,  1,  0,  0,  0,  0,  1,  0],  # N08
    [0,  0,  0,  0,  1,  0,  0,  1,  0,  1,  0,  0,  0,  0,  1],  # N09
    [0,  0,  0,  0,  0,  1,  0,  0,  1,  0,  0,  0,  0,  0,  1],  # N10
    [1,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0],  # N11
    [0,  1,  0,  0,  0,  0,  0,  0,  0,  0,  1,  0,  1,  0,  0],  # N12
    [0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  1,  0,  1,  0],  # N13
    [0,  0,  0,  0,  0,  0,  0,  1,  0,  0,  0,  0,  1,  0,  1],  # N14
    [0,  0,  0,  0,  0,  0,  0,  0,  1,  1,  0,  0,  0,  1,  0],  # N15
], dtype=np.float32)
