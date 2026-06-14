"""
reward.py — Waiting Time reward (primary) + Pressure penalty (secondary)

Thay thế pure Weighted Pressure bằng hybrid reward sát thực tế hơn:

Formula (per agent):
    waiting_time_i = mean waiting time (giây) của xe trên các incoming edges của ngã tư i
    pressure_i     = |Σ(queue_in × w_e) - Σ(queue_out × w_e)| / N_lanes_i  (như cũ)

    reward_i = - (α × waiting_time_i_norm + β × pressure_i)

    α = 0.7  → waiting time là primary signal (sát tiêu chí HCM / SCOOT)
    β = 0.3  → pressure giữ vai trò regularizer, tránh spillback

Lý do hybrid thay vì pure waiting time:
    - Waiting time phản ánh trải nghiệm xe (tiêu chí số 1 thực tế)
    - Pressure giữ dòng chảy cân bằng, tránh agent "sacrifice" 1 hướng
    - Pure waiting time có thể bị sparse signal đầu episode khi xe chưa nhiều

Tham khảo:
    - HCM 7th Edition — Level of Service dựa trên control delay (giây/xe)
    - SCOOT/SCATS — tối ưu delay minimization là primary objective
    - PressLight (KDD 2019)    — https://arxiv.org/abs/1909.09905
    - Efficient Pressure (2022) — https://arxiv.org/abs/2204.03220
    - MPLight / AttentionLight  — waiting time as reward signal
"""

from environment.maps import INCOMING_EDGES, OUTGOING_EDGES, EDGE_WEIGHTS, get_edge_lanes

# ── Hyperparameters ────────────────────────────────────────────────────────────
ALPHA           = 0.7   # weight cho waiting time
BETA            = 0.3   # weight cho pressure (regularizer)
WEIGHT_DEFAULT  = 1.0
MAX_WAIT_NORM   = 120.0  # giây — normalize waiting time về [0,1], clip tại 2 phút


def _edge_weight(edge_id: str) -> float:
    return EDGE_WEIGHTS.get(edge_id, WEIGHT_DEFAULT)


def compute_pressure(
    intersection_id: str,
    incoming_queues: list[float],
    outgoing_queues: list[float],
) -> float:
    """
    Tính weighted pressure tại một ngã tư (giữ nguyên từ phiên bản cũ).

    Args:
        intersection_id : "N01" ... "N15"
        incoming_queues : flat list queue length lanes đi VÀO
        outgoing_queues : flat list queue length lanes đi RA

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
    avg_waiting_time: float = 0.0,
) -> float:
    """
    Hybrid reward = -(α × waiting_time_norm + β × pressure)

    Args:
        intersection_id  : "N01" ... "N15"
        incoming_queues  : flat list queue length lanes đi VÀO
        outgoing_queues  : flat list queue length lanes đi RA
        avg_waiting_time : waiting time trung bình (giây) của xe tại ngã tư này.
                           Nếu không truyền (= 0.0) thì chỉ dùng pressure.

    Returns:
        reward (float, <= 0)
    """
    pressure = compute_pressure(intersection_id, incoming_queues, outgoing_queues)

    # Normalize waiting time về [0, 1]
    wait_norm = min(avg_waiting_time, MAX_WAIT_NORM) / MAX_WAIT_NORM

    return -(ALPHA * wait_norm + BETA * pressure)


def compute_global_reward(pressures: dict[str, float]) -> float:
    """Tổng reward toàn mạng — dùng để log/eval, không train."""
    return -sum(pressures.values())
