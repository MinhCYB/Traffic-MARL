"""
state_builder.py — Xây dựng state vector và adjacency graph cho GAT

State mỗi ngã tư:
    [density_per_lane (x8), queue_per_lane (x8), phase_onehot (x4), time_since_change (x1)]
    → tổng 21 chiều

Không có agent_id — GAT tự differentiate qua graph topology.

Graph:
    Node = ngã tư (4 node)
    Edge = đoạn đường nối trực tiếp (không qua SRC)
    adjacency_matrix[i][j] = 1 nếu có đường nối, 0 nếu không
"""

import numpy as np

from environment.maps import (
    INTERSECTION_IDS,
    INCOMING_EDGES,
    OUTGOING_EDGES,
    ADJACENCY_MATRIX,
    NUM_LANES,
    get_edge_lanes,
)

INTERSECTION_INDEX = {nid: i for i, nid in enumerate(INTERSECTION_IDS)}

# Số phase của mỗi ngã tư (4 phase: NS_green, NS_yellow, EW_green, EW_yellow)
NUM_PHASES = 4

# Max queue để normalize (xe)
MAX_QUEUE = 20.0

# Max thời gian giữ phase để normalize (giây)
MAX_TIME_SINCE_CHANGE = 120.0

# Edge index cho PyG (COO format) — tự động từ adjacency matrix
_src, _dst = np.where(ADJACENCY_MATRIX == 1)
EDGE_INDEX = np.stack([_src, _dst], axis=0).astype(np.int64)


# ── State builder ─────────────────────────────────────────────────────────────

def build_state(
    intersection_id: str,
    queue_per_lane: dict[str, list[float]],
    density_per_lane: dict[str, list[float]],
    current_phase: int,
    time_since_change: float,
) -> np.ndarray:
    """
    Xây dựng state vector cho một ngã tư.

    Args:
        intersection_id    : "N01" | "N02" | "N03" | "N04"
        queue_per_lane     : {edge_id: [lane0_queue, lane1_queue]} — raw từ TraCI
        density_per_lane   : {edge_id: [lane0_density, lane1_density]} — raw từ TraCI
        current_phase      : index phase hiện tại (0-3)
        time_since_change  : giây từ lần đổi phase cuối

    Returns:
        state: np.ndarray shape (21,) — normalized 0-1
    """
    incoming = INCOMING_EDGES[intersection_id]

    # density (n_lanes per edge), normalize 0-1
    density_vec = []
    for edge in incoming:
        n = get_edge_lanes(edge)
        lanes = density_per_lane.get(edge, [0.0] * n)
        density_vec.extend([min(v, 1.0) for v in lanes])

    # queue (n_lanes per edge), normalize bằng MAX_QUEUE
    queue_vec = []
    for edge in incoming:
        n = get_edge_lanes(edge)
        lanes = queue_per_lane.get(edge, [0.0] * n)
        queue_vec.extend([min(v / MAX_QUEUE, 1.0) for v in lanes])

    # phase one-hot 4 chiều
    phase_vec = [0.0] * NUM_PHASES
    if 0 <= current_phase < NUM_PHASES:
        phase_vec[current_phase] = 1.0

    # time since change, normalize
    time_vec = [min(time_since_change / MAX_TIME_SINCE_CHANGE, 1.0)]

    state = np.array(
        density_vec + queue_vec + phase_vec + time_vec,
        dtype=np.float32,
    )  # shape (21,)

    return state


def build_all_states(
    queue_per_lane: dict[str, dict[str, list[float]]],
    density_per_lane: dict[str, dict[str, list[float]]],
    current_phases: dict[str, int],
    time_since_change: dict[str, float],
) -> dict[str, np.ndarray]:
    """
    Build state cho tất cả 4 ngã tư.

    Args:
        queue_per_lane    : {intersection_id: {edge_id: [lane0, lane1]}}
        density_per_lane  : {intersection_id: {edge_id: [lane0, lane1]}}
        current_phases    : {intersection_id: phase_index}
        time_since_change : {intersection_id: seconds}

    Returns:
        {intersection_id: state_vector (21,)}
    """
    return {
        nid: build_state(
            intersection_id=nid,
            queue_per_lane=queue_per_lane.get(nid, {}),
            density_per_lane=density_per_lane.get(nid, {}),
            current_phase=current_phases.get(nid, 0),
            time_since_change=time_since_change.get(nid, 0.0),
        )
        for nid in INTERSECTION_IDS
    }


def build_node_features(states: dict[str, np.ndarray]) -> np.ndarray:
    """
    Stack state vectors thành node feature matrix cho GAT.

    Returns:
        x: np.ndarray shape (4, 21) — node features
    """
    return np.stack(
        [states[nid] for nid in INTERSECTION_IDS],
        axis=0,
    )  # (4, 21)


def get_incoming_queues(
    intersection_id: str,
    queue_per_lane: dict[str, list[float]],
) -> list[float]:
    """Lấy raw queue values của tất cả incoming lanes — dùng cho reward."""
    result = []
    for edge in INCOMING_EDGES[intersection_id]:
        n = get_edge_lanes(edge)
        result.extend(queue_per_lane.get(edge, [0.0] * n))
    return result


def get_outgoing_queues(
    intersection_id: str,
    queue_per_lane: dict[str, list[float]],
) -> list[float]:
    """Lấy raw queue values của tất cả outgoing lanes — dùng cho reward."""
    result = []
    for edge in OUTGOING_EDGES[intersection_id]:
        n = get_edge_lanes(edge)
        result.extend(queue_per_lane.get(edge, [0.0] * n))
    return result