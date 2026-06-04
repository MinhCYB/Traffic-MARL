"""
fixed_agent.py — Fixed-time agent wrapper

Wrap FixedTimeModel vào BaseAgent interface
để training loop và workers dùng chung API.
"""

import numpy as np
from agents.base_agent import BaseAgent
from models.fixed_time import FixedTimeModel


class FixedAgent(BaseAgent):
    """Fixed-cycle agent — không học, không update."""

    def __init__(self, green_duration: int = 30, delta_time: int = 5):
        self.model      = FixedTimeModel(green_duration)
        self.delta_time = delta_time

    def select_actions(self, obs: dict) -> dict[str, int]:
        """Bỏ qua obs, trả về action theo timer cố định."""
        return self.model.select_actions(self.delta_time)

    def update(self, batch: dict) -> dict[str, float]:
        """Không học gì — trả về loss = 0."""
        return {"loss": 0.0, "epsilon": 0.0}

    def save(self, path: str):
        """Không có gì để save."""
        pass

    def load(self, path: str):
        """Không có gì để load."""
        pass

    def reset(self):
        """Reset timer về 0 cho episode mới."""
        self.model.reset()