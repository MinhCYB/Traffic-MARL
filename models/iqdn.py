"""
idqn.py — Independent DQN baseline

Mỗi agent học độc lập, không communication với agents khác.
Không có GAT layer — mỗi ngã tư chỉ nhìn vào observation của bản thân.

Kiến trúc:
    obs_i (21,)
        │
    [MLP Encoder]    → h_i ∈ R^64
        │
    [Q-head]         → Q(s, keep), Q(s, switch)
"""

import torch
import torch.nn as nn

# ── Hyperparams — giữ giống GAT-MARL để so sánh công bằng ───────────────────
STATE_DIM   = 21
HIDDEN_DIM  = 64
NUM_ACTIONS = 2


class IDQNNet(nn.Module):
    """
    Independent DQN network — không có GAT, không có communication.

    Dùng chung 1 network cho tất cả agents (parameter sharing)
    để so sánh công bằng với GAT-MARL.
    """

    def __init__(
        self,
        state_dim:   int = STATE_DIM,
        hidden_dim:  int = HIDDEN_DIM,
        num_actions: int = NUM_ACTIONS,
    ):
        super().__init__()

        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_actions),   # output: [Q(keep), Q(switch)]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (N, state_dim) — N agents, mỗi agent xử lý độc lập

        Returns:
            q_values: (N, num_actions)
        """
        return self.net(x)