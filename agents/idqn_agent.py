"""
idqn_agent.py — Independent DQN agent

Mỗi agent học độc lập, không communication.
Interface giống GATAgent để training loop dùng chung.

TODO (teammate):
    [ ] Implement select_actions() — không cần edge_index
    [ ] Implement update() — forward từng agent độc lập
    [ ] Verify output giống GATAgent: {"loss": float, "epsilon": float}
    [ ] Test save/load checkpoint
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from agents.base_agent import BaseAgent
from models.idqn import IDQNNet
from env.state_builder import INTERSECTION_IDS


class IDQNAgent(BaseAgent):
    """
    Independent DQN agent.

    Khác GATAgent:
    - Không có edge_index / GAT communication
    - Mỗi agent forward độc lập với obs của chính nó
    - Vẫn dùng parameter sharing (1 network cho 4 agents)
    """

    def __init__(
        self,
        state_dim:    int   = 21,
        hidden_dim:   int   = 64,
        num_actions:  int   = 2,
        lr:           float = 1e-3,
        gamma:        float = 0.99,
        epsilon:      float = 1.0,
        epsilon_min:  float = 0.05,
        epsilon_decay: float = 0.995,
        target_update_freq: int = 100,
        device:       str   = "auto",
    ):
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        ) if device == "auto" else torch.device(device)

        self.gamma          = gamma
        self.epsilon        = epsilon
        self.epsilon_min    = epsilon_min
        self.epsilon_decay  = epsilon_decay
        self.target_update_freq = target_update_freq
        self._update_count  = 0

        # TODO: khởi tạo online_net và target_net từ IDQNNet
        # self.online_net = ...
        # self.target_net = ...
        raise NotImplementedError

        self.optimizer = optim.Adam(self.online_net.parameters(), lr=lr)
        self.loss_fn   = nn.SmoothL1Loss()

    # ── Inference ─────────────────────────────────────────────────────────────

    def select_actions(self, obs: dict) -> dict[str, int]:
        """
        Epsilon-greedy, không dùng edge_index.

        Args:
            obs: {"states": dict[str, np.ndarray], "node_features": np.ndarray (4, 21)}

        Returns:
            actions: {intersection_id: 0 | 1}

        TODO: implement
        """
        raise NotImplementedError

    # ── Learning ──────────────────────────────────────────────────────────────

    def update(self, batch: dict) -> dict[str, float]:
        """
        Double DQN update — không có GAT, mỗi agent độc lập.

        Args:
            batch: {
                "states":      (B, 4, 21) float32
                "actions":     (B, 4)     int64
                "rewards":     (B, 4)     float32
                "next_states": (B, 4, 21) float32
                "dones":       (B,)       float32
            }
            Lưu ý: không có "edge_index" — IDQN không cần

        Returns:
            {"loss": float, "epsilon": float}

        TODO: implement
        Gợi ý: reshape (B, 4, 21) → (B*4, 21) rồi forward 1 lần
        """
        raise NotImplementedError

    # ── Checkpoint ────────────────────────────────────────────────────────────

    def save(self, path: str):
        # TODO: implement — tương tự GATAgent
        raise NotImplementedError

    def load(self, path: str):
        # TODO: implement
        raise NotImplementedError

    def set_eval(self):
        self.online_net.eval()
        self.epsilon = 0.0

    def set_train(self):
        self.online_net.train()