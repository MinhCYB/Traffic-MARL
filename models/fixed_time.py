"""
fixed_time.py — Fixed-time traffic signal baseline

Chu kỳ cố định: green 30s → yellow 3s → green 30s → ...
Không có neural network, không học.
Dùng làm lower bound trong ablation study.
"""

from environment.state_builder import INTERSECTION_IDS

GREEN_DURATION  = 30   # giây
YELLOW_DURATION = 3    # giây
CYCLE           = GREEN_DURATION + YELLOW_DURATION  # 33s mỗi pha


class FixedTimeModel:
    """
    Fixed-cycle controller — 1 object quản lý tất cả 4 ngã tư.

    Không nhận state, không trả Q-values.
    Output là actions dict giống interface của agent khác.
    """

    def __init__(self, green_duration: int = GREEN_DURATION):
        self.green_duration = green_duration
        self._timers: dict[str, int] = {nid: 0 for nid in INTERSECTION_IDS}

    def reset(self):
        self._timers = {nid: 0 for nid in INTERSECTION_IDS}

    def select_actions(self, delta_time: int = 5) -> dict[str, int]:
        """
        Trả về actions dựa trên timer cố định.

        Args:
            delta_time: giây mỗi decision step

        Returns:
            actions: {intersection_id: 0 (keep) | 1 (switch)}
        """
        actions = {}
        for nid in INTERSECTION_IDS:
            self._timers[nid] += delta_time
            if self._timers[nid] >= self.green_duration:
                actions[nid] = 1   # switch
                self._timers[nid] = 0
            else:
                actions[nid] = 0   # keep
        return actions