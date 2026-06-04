"""
base_agent.py — Abstract interface cho tất cả agents

Tất cả agents (GAT-MARL, IDQN, Fixed-time) implement interface này
để training loop và workers dùng chung một API.
"""

from abc import ABC, abstractmethod
import numpy as np


class BaseAgent(ABC):
    """Abstract base class cho traffic signal agents."""

    @abstractmethod
    def select_actions(self, obs: dict) -> dict[str, int]:
        """
        Chọn actions cho tất cả ngã tư.

        Args:
            obs: {"states": dict[str, np.ndarray], "node_features": np.ndarray}

        Returns:
            actions: {intersection_id: 0 (keep) | 1 (switch)}
        """
        raise NotImplementedError

    @abstractmethod
    def update(self, batch: dict) -> dict[str, float]:
        """
        Cập nhật model từ một batch experience.

        Args:
            batch: {
                "states":       np.ndarray (B, N, state_dim),
                "actions":      np.ndarray (B, N),
                "rewards":      np.ndarray (B, N),
                "next_states":  np.ndarray (B, N, state_dim),
                "dones":        np.ndarray (B,),
                "edge_index":   np.ndarray (2, E),
            }

        Returns:
            metrics: {"loss": float, ...}
        """
        raise NotImplementedError

    @abstractmethod
    def save(self, path: str):
        """Lưu model weights."""
        raise NotImplementedError

    @abstractmethod
    def load(self, path: str):
        """Load model weights."""
        raise NotImplementedError

    def set_eval(self):
        """Chuyển sang eval mode (inference only)."""
        pass

    def set_train(self):
        """Chuyển sang train mode."""
        pass