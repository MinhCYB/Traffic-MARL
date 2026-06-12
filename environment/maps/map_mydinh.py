"""
map_mydinh.py — Topology data cho map Mỹ Đình (8 ngã tư thực tế)

Layout:
    N01 ── N02 ── N03       ← Hồ Tùng Mậu
     |      |      |
    N04 ── N05 ── N06       ← Hàm Nghi / Phạm Hùng
     |      |
    N07 ── N08              ← Trần Hữu Dực

Đường cao tải (arterial, 3 lane):
    Ngang: N01─N02─N03 (Hồ Tùng Mậu)
    Dọc:   N02─N05─N08 (Lê Đức Thọ), N03─N06 (Phạm Hùng)

Đường thứ cấp (secondary, 2 lane):
    Dọc:   N01─N04─N07 (Nguyễn Cơ Thạch)
    Ngang: N04─N05 (Hàm Nghi), N07─N08 (Trần Hữu Dực)
"""

import numpy as np

INTERSECTION_IDS = ["N01", "N02", "N03", "N04", "N05", "N06", "N07", "N08"]

# Arterial: 3 lanes → NUM_LANES_ARTERIAL = 3
# Secondary/Outskirts: 2 lanes → NUM_LANES_DEFAULT = 2
# build_state dùng dict này để biết mỗi edge có bao nhiêu lane
EDGE_LANES = {
    # ── Hồ Tùng Mậu (arterial) ──
    "SRC_HTM_W_N01": 3, "SRC_HTM_W_N02": 3,
    "SRC_HTM_E_N02": 3, "SRC_HTM_E_N03": 3,
    # ── Lê Đức Thọ (arterial) ──
    "SRC_LDT_N_N02": 3, "SRC_LDT_N_N05": 3,
    "SRC_LDT_S_N05": 3, "SRC_LDT_S_N08": 3,
    # ── Phạm Hùng (arterial) ──
    "SRC_PH_N03": 3, "SRC_PH_N06": 3,
    # ── Boundary arterial ──
    "EXT_N_N03_in": 2, "EXT_E_N03_in": 2, "EXT_E_N06_in": 2,
    # ── Secondary / Outskirts (default 2) ──
}
DEFAULT_LANES = 2

def get_edge_lanes(edge_id: str) -> int:
    return EDGE_LANES.get(edge_id, DEFAULT_LANES)

INCOMING_EDGES = {
    "N01": ["EXT_W_N01_in", "EXT_N_N01_in", "SRC_HTM_W_N01", "SRC_NCT_N_N01"],
    "N02": ["EXT_N_N02_in", "SRC_HTM_W_N02", "SRC_HTM_E_N02", "SRC_LDT_N_N02"],
    "N03": ["EXT_N_N03_in", "EXT_E_N03_in",  "SRC_HTM_E_N03", "SRC_PH_N03"],
    "N04": ["EXT_W_N04_in", "SRC_NCT_N_N04", "SRC_HN_N04",    "SRC_NCT_S_N04"],
    "N05": ["SRC_LDT_N_N05","SRC_HN_N05",    "SRC_LDT_S_N05"],
    "N06": ["SRC_PH_N06",   "EXT_E_N06_in"],
    "N07": ["EXT_W_N07_in", "SRC_NCT_S_N07", "EXT_S_N07_in",  "SRC_THD_N07"],
    "N08": ["SRC_LDT_S_N08","EXT_S_N08_in",  "SRC_THD_N08"],
}

OUTGOING_EDGES = {
    "N01": ["N01_EXT_W_N01", "N01_EXT_N_N01", "N01_SRC_HTM_W", "N01_SRC_NCT_N"],
    "N02": ["N02_EXT_N_N02", "N02_SRC_HTM_W", "N02_SRC_HTM_E", "N02_SRC_LDT_N"],
    "N03": ["N03_EXT_N_N03", "N03_EXT_E_N03", "N03_SRC_HTM_E", "N03_SRC_PH"],
    "N04": ["N04_EXT_W_N04", "N04_SRC_NCT_N", "N04_SRC_HN",    "N04_SRC_NCT_S"],
    "N05": ["N05_SRC_LDT_N", "N05_SRC_HN",    "N05_SRC_LDT_S"],
    "N06": ["N06_SRC_PH",    "N06_EXT_E_N06"],
    "N07": ["N07_EXT_W_N07", "N07_SRC_NCT_S", "N07_EXT_S_N07", "N07_SRC_THD"],
    "N08": ["N08_SRC_LDT_S", "N08_EXT_S_N08", "N08_SRC_THD"],
}

NUM_LANES = 2  # default, dùng get_edge_lanes() cho chính xác

#         N01 N02 N03 N04 N05 N06 N07 N08
ADJACENCY_MATRIX = np.array([
    [0,  1,  0,  1,  0,  0,  0,  0],  # N01 ─ N02, N04
    [1,  0,  1,  0,  1,  0,  0,  0],  # N02 ─ N01, N03, N05
    [0,  1,  0,  0,  0,  1,  0,  0],  # N03 ─ N02, N06
    [1,  0,  0,  0,  1,  0,  1,  0],  # N04 ─ N01, N05, N07
    [0,  1,  0,  1,  0,  0,  0,  1],  # N05 ─ N02, N04, N08
    [0,  0,  1,  0,  0,  0,  0,  0],  # N06 ─ N03
    [0,  0,  0,  1,  0,  0,  0,  1],  # N07 ─ N04, N08
    [0,  0,  0,  0,  1,  0,  1,  0],  # N08 ─ N05, N07
], dtype=np.float32)
