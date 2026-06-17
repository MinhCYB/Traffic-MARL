"""
idqn_agent.py — Independent DQN agent

Mỗi agent học độc lập, không communication.
Interface giống GATAgent để training loop dùng chung.

Điểm khác biệt duy nhất so với GATAgent:
    - Không có edge_index / GAT communication
    - IDQNNet.forward(x) chỉ nhận 1 argument (không có edge_index)
    - update() không cần repeat/batch edge_index
    - Tất cả logic khác (Double DQN, epsilon, target sync) giữ nguyên
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from agents.base_agent import BaseAgent
from models.idqn import IDQNNet
from environment.state_builder import INTERSECTION_IDS
from training.config import GRAD_CLIP


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
        state_dim:          int   = 21,
        hidden_dim:         int   = 64,
        num_actions:        int   = 2,
        lr:                 float = 1e-3,
        gamma:              float = 0.99,
        epsilon:            float = 1.0,
        epsilon_min:        float = 0.05,
        epsilon_decay:      float = 0.995,
        target_update_freq: int   = 100,
        device:             str   = "auto",
    ):
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        ) if device == "auto" else torch.device(device)

        self.gamma              = gamma
        self.epsilon            = epsilon
        self.epsilon_min        = epsilon_min
        self.epsilon_decay      = epsilon_decay
        self.target_update_freq = target_update_freq
        self._update_count      = 0

        # Online network + target network (Double DQN)
        self.online_net = IDQNNet(state_dim, hidden_dim, num_actions).to(self.device)
        self.target_net = IDQNNet(state_dim, hidden_dim, num_actions).to(self.device)
        self.target_net.load_state_dict(self.online_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.online_net.parameters(), lr=lr)
        self.loss_fn   = nn.SmoothL1Loss()  # Huber loss — ổn định hơn MSE

    # ── Inference ─────────────────────────────────────────────────────────────

    def select_actions(self, obs: dict) -> dict[str, int]:
        """
        Epsilon-greedy action selection — không dùng edge_index.

        Args:
            obs: {
                "states":        dict[str, np.ndarray],
                "node_features": np.ndarray (4, 21)
            }

        Returns:
            actions: {intersection_id: 0 (keep) | 1 (switch)}
        """
        if np.random.random() < self.epsilon:
            # Random exploration
            return {nid: np.random.randint(0, 2) for nid in INTERSECTION_IDS}

        node_features = obs["node_features"]  # (4, 21)
        x = torch.tensor(node_features, dtype=torch.float32).to(self.device)

        self.online_net.eval()
        with torch.no_grad():
            q_values = self.online_net(x)   # (4, 2) — không cần edge_index

        actions = q_values.argmax(dim=-1).cpu().numpy()  # (4,)
        return {nid: int(actions[i]) for i, nid in enumerate(INTERSECTION_IDS)}

    # ── Learning ──────────────────────────────────────────────────────────────

    def update(self, batch: dict) -> dict[str, float]:
        """
        Double DQN update — không có GAT, mỗi agent độc lập.

        Trick reshape: (B, 4, 21) → (B*4, 21) rồi forward 1 lần.
        Điều này tương đương với forward 4 agents × B samples cùng lúc,
        nhưng không có communication giữa các agent.

        Args:
            batch: {
                "states":      (B, 4, 21) float32
                "actions":     (B, 4)     int64
                "rewards":     (B, 4)     float32
                "next_states": (B, 4, 21) float32
                "dones":       (B,)       float32
                "edge_index":  ignored    — IDQN không dùng
            }

        Returns:
            {"loss": float, "epsilon": float}
        """
        self.online_net.train()

        B = batch["states"].shape[0]
        N = len(INTERSECTION_IDS)  # 4

        # ── Bước 1: Convert sang tensor ──────────────────────────────────────
        states      = torch.tensor(batch["states"],      dtype=torch.float32).to(self.device)  # (B, 4, 21)
        actions     = torch.tensor(batch["actions"],     dtype=torch.long).to(self.device)      # (B, 4)
        rewards     = torch.tensor(batch["rewards"],     dtype=torch.float32).to(self.device)   # (B, 4)
        next_states = torch.tensor(batch["next_states"], dtype=torch.float32).to(self.device)   # (B, 4, 21)
        dones       = torch.tensor(batch["dones"],       dtype=torch.float32).to(self.device)   # (B,)

        # ── Bước 2: Reshape để forward batch lớn 1 lần ───────────────────────
        # (B, 4, 21) → (B*4, 21): 4 agents × B samples = B*4 "samples" độc lập
        states_flat      = states.view(B * N, -1)       # (B*4, 21)
        next_states_flat = next_states.view(B * N, -1)  # (B*4, 21)

        # ── Bước 3: Current Q values ─────────────────────────────────────────
        q_all   = self.online_net(states_flat)           # (B*4, 2)
        q_all   = q_all.view(B, N, -1)                  # (B, 4, 2)
        q_taken = q_all.gather(2, actions.unsqueeze(-1)).squeeze(-1)  # (B, 4)

        # ── Bước 4: Double DQN target ─────────────────────────────────────────
        with torch.no_grad():
            # Online net chọn action tốt nhất cho next state
            q_next_online = self.online_net(next_states_flat).view(B, N, -1)  # (B, 4, 2)
            next_actions  = q_next_online.argmax(dim=-1, keepdim=True)        # (B, 4, 1)

            # Target net đánh giá action đó (tránh overestimation)
            q_next_target = self.target_net(next_states_flat).view(B, N, -1)  # (B, 4, 2)
            q_next        = q_next_target.gather(2, next_actions).squeeze(-1) # (B, 4)

            # Broadcast dones từ (B,) → (B, 4)
            dones_expanded = dones.unsqueeze(1).expand_as(q_next)
            targets = rewards + self.gamma * q_next * (1 - dones_expanded)    # (B, 4)

        # ── Bước 5: Loss + backprop ───────────────────────────────────────────
        loss = self.loss_fn(q_taken, targets)

        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online_net.parameters(), max_norm=GRAD_CLIP)
        self.optimizer.step()

        # ── Bước 6: Epsilon decay ─────────────────────────────────────────────
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        # ── Bước 7: Target network sync định kỳ ──────────────────────────────
        self._update_count += 1
        if self._update_count % self.target_update_freq == 0:
            self.target_net.load_state_dict(self.online_net.state_dict())

        return {"loss": loss.item(), "epsilon": self.epsilon}

    # ── Checkpoint ────────────────────────────────────────────────────────────

    def save(self, path: str):
        """Lưu toàn bộ training state để resume."""
        torch.save({
            "online_net":   self.online_net.state_dict(),
            "target_net":   self.target_net.state_dict(),
            "optimizer":    self.optimizer.state_dict(),
            "epsilon":      self.epsilon,
            "update_count": self._update_count,
        }, path)

    def load(self, path: str):
        """Load checkpoint — dùng map_location để tương thích CPU/GPU."""
        ckpt = torch.load(path, map_location=self.device, weights_only=True)
        self.online_net.load_state_dict(ckpt["online_net"])
        self.target_net.load_state_dict(ckpt["target_net"])
        self.optimizer.load_state_dict(ckpt["optimizer"])
        self.epsilon       = ckpt.get("epsilon",      self.epsilon_min)
        self._update_count = ckpt.get("update_count", 0)

    def set_eval(self):
        """Chuyển sang eval mode — tắt epsilon để greedy hoàn toàn."""
        self.online_net.eval()
        self.epsilon = 0.0

    def set_train(self):
        """Chuyển sang train mode."""
        self.online_net.train()