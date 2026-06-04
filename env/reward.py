"""
reward.py — Max Pressure reward (PressLight, KDD 2019)

reward_i = -|sum(queue_incoming) - sum(queue_outgoing)|

Tính tại mỗi timestep, không cumulative.
Minimize pressure = maximize network throughput (có proof toán học).
"""


def compute_pressure(
    incoming_queues: list[float],
    outgoing_queues: list[float],
) -> float:
    """
    Tính pressure tại một ngã tư.

    Args:
        incoming_queues: queue length các lane đi VÀO ngã tư
        outgoing_queues: queue length các lane đi RA khỏi ngã tư

    Returns:
        pressure (float, >= 0)
    """
    return abs(sum(incoming_queues) - sum(outgoing_queues))


def compute_reward(
    incoming_queues: list[float],
    outgoing_queues: list[float],
) -> float:
    """
    Reward = -pressure.

    Agent tối đa hóa reward = tối thiểu hóa pressure.

    Args:
        incoming_queues: queue length các lane đi vào (normalized 0-1)
        outgoing_queues: queue length các lane đi ra (normalized 0-1)

    Returns:
        reward (float, <= 0)
    """
    return -compute_pressure(incoming_queues, outgoing_queues)


def compute_global_reward(pressures: dict[str, float]) -> float:
    """
    Tổng reward toàn mạng — dùng để log/eval, không dùng để train.

    Args:
        pressures: {intersection_id: pressure_value}

    Returns:
        global_reward (float, <= 0)
    """
    return -sum(pressures.values())