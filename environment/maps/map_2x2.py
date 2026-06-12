"""
map_2x2.py — Topology data cho map 2x2 (4 ngã tư synthetic)

Layout:
    N01 ── N02
     |      |
    N03 ── N04
"""

import numpy as np

INTERSECTION_IDS = ["N01", "N02", "N03", "N04"]

INCOMING_EDGES = {
    "N01": ["NT_N_W_N01", "NT_W_N_N01", "SRC1_N01", "SRC3_N01"],
    "N02": ["NT_N_E_N02", "NT_E_N_N02", "SRC1_N02", "SRC4_N02"],
    "N03": ["NT_S_W_N03", "NT_W_S_N03", "SRC2_N03", "SRC3_N03"],
    "N04": ["NT_S_E_N04", "NT_E_S_N04", "SRC2_N04", "SRC4_N04"],
}

OUTGOING_EDGES = {
    "N01": ["N01_NT_N_W", "N01_NT_W_N", "N01_SRC1", "N01_SRC3"],
    "N02": ["N02_NT_N_E", "N02_NT_E_N", "N02_SRC1", "N02_SRC4"],
    "N03": ["N03_NT_S_W", "N03_NT_W_S", "N03_SRC2", "N03_SRC3"],
    "N04": ["N04_NT_S_E", "N04_NT_E_S", "N04_SRC2", "N04_SRC4"],
}

NUM_LANES = 2

#         N01  N02  N03  N04
ADJACENCY_MATRIX = np.array([
    [0,   1,   1,   0],  # N01
    [1,   0,   0,   1],  # N02
    [1,   0,   0,   1],  # N03
    [0,   1,   1,   0],  # N04
], dtype=np.float32)
