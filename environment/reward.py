"""
reward.py — Weighted Pressure reward

Cải tiến từ Max Pressure (PressLight, KDD 2019):
  - Weight theo tầm quan trọng thực tế của đường (khai báo trong map_*.py)
  - Normalize theo N_lanes → scale đồng đều giữa các ngã tư

Formula:
    pressure_i = |Σ(queue_in × w_e) - Σ(queue_out × w_e)| / N_lanes_i
    reward_i   = -pressure_i

Weight mặc định = 1.0, arterial = 2.0 — khai báo trong EDGE_WEIGHTS của từng map.
Map mới chỉ cần set EDGE_WEIGHTS, reward.py không cần đổi.

Tham khảo:
  - PressLight:         https://arxiv.org/abs/1909.09905
  - Efficient Pressure: https://arxiv.org/abs/2204.03220
  - AttentionLight:     https://arxiv.org/abs/2307.05170
"""

from environment.maps import INCOMING_EDGES, OUTGOING_EDGES, EDGE_WEIGHTS, get_edge_lanes

WEIGHT_DEFAULT = 1.0


def _edge_weight(edge_id: str) -> float:
    return EDGE_WEIGHTS.get(edge_id, WEIGHT_DEFAULT)


def compute_pressure(
    intersection_id: str,
    incoming_queues: list[float],
    outgoing_queues: list[float],
) -> float:
    """
    Tính weighted pressure tại một ngã tư.

    Args:
        intersection_id : "N01" ... "N08"
        incoming_queues : flat list queue length lanes đi VÀO (theo thứ tự INCOMING_EDGES)
        outgoing_queues : flat list queue length lanes đi RA  (theo thứ tự OUTGOING_EDGES)

    Returns:
        pressure (float, >= 0)
    """
    def weighted_sum(edges, queues):
        total, idx = 0.0, 0
        for edge in edges:
            n = get_edge_lanes(edge)
            w = _edge_weight(edge)
            total += sum(queues[idx: idx + n]) * w
            idx += n
        return total

    inc_edges = INCOMING_EDGES[intersection_id]
    out_edges = OUTGOING_EDGES[intersection_id]

    w_in  = weighted_sum(inc_edges, incoming_queues)
    w_out = weighted_sum(out_edges, outgoing_queues)

    n_lanes = max(sum(get_edge_lanes(e) for e in inc_edges), 1)

    return abs(w_in - w_out) / n_lanes


def compute_reward(
    intersection_id: str,
    incoming_queues: list[float],
    outgoing_queues: list[float],
) -> float:
    """reward = -weighted_pressure / N_lanes"""
    return -compute_pressure(intersection_id, incoming_queues, outgoing_queues)


def compute_global_reward(pressures: dict[str, float]) -> float:
    """Tổng reward toàn mạng — dùng để log/eval, không train."""
    return -sum(pressures.values())