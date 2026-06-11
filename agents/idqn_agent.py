"""
idqn_agent.py — Independent DQN agent

Mỗi agent học độc lập, không communication.
Interface giống GATAgent để training loop dùng chung.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from agents.base_agent import BaseAgent
from models.iqdn import IDQNNet
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

        # 1 bộ network dùng chung cho 4 agents (parameter sharing)
        # online_net: cập nhật mỗi bước
        # target_net: copy định kỳ để ổn định training
        self.online_net = IDQNNet(state_dim, hidden_dim, num_actions).to(self.device)
        self.target_net = IDQNNet(state_dim, hidden_dim, num_actions).to(self.device)
        self.target_net.load_state_dict(self.online_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.online_net.parameters(), lr=lr)
        self.loss_fn   = nn.SmoothL1Loss()

    # ── Inference ─────────────────────────────────────────────────────────────

    def select_actions(self, obs: dict) -> dict[str, int]:
        """
        Epsilon-greedy cho 4 agents, không dùng edge_index.

        Args:
            obs: {"states": dict[str, np.ndarray], "node_features": np.ndarray (4, 21)}

        Returns:
            actions: {intersection_id: 0 | 1}
        """
        actions = {}

        # node_features shape: (4, 21)
        node_features = obs["node_features"]  # np.ndarray (4, 21)

        x = torch.FloatTensor(node_features).to(self.device)  # (4, 21)

        with torch.no_grad():
            q_values = self.online_net(x)   # (4, 2)

        for i, nid in enumerate(INTERSECTION_IDS):
            if np.random.random() < self.epsilon:
                # Exploration: random action
                actions[nid] = np.random.randint(0, 2)
            else:
                # Exploitation: chọn action có Q cao nhất
                actions[nid] = q_values[i].argmax().item()

        return actions

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

        Returns:
            {"loss": float, "epsilon": float}
        """
        # Chuyển sang tensor
        states      = torch.FloatTensor(batch["states"]).to(self.device)       # (B, 4, 21)
        actions     = torch.LongTensor(batch["actions"]).to(self.device)       # (B, 4)
        rewards     = torch.FloatTensor(batch["rewards"]).to(self.device)      # (B, 4)
        next_states = torch.FloatTensor(batch["next_states"]).to(self.device)  # (B, 4, 21)
        dones       = torch.FloatTensor(batch["dones"]).to(self.device)        # (B,)

        B = states.shape[0]

        # Reshape: (B, 4, 21) → (B*4, 21) để forward 1 lần cho tất cả agents
        states_flat      = states.view(B * 4, -1)       # (B*4, 21)
        next_states_flat = next_states.view(B * 4, -1)  # (B*4, 21)
        actions_flat     = actions.view(B * 4)           # (B*4,)
        rewards_flat     = rewards.view(B * 4)           # (B*4,)

        # done broadcast: mỗi agent trong cùng timestep có cùng done flag
        dones_flat = dones.unsqueeze(1).expand(B, 4).reshape(B * 4)  # (B*4,)

        # ── Q hiện tại ────────────────────────────────────────────────────────
        # online_net dự đoán Q cho tất cả actions
        # gather lấy đúng Q của action đã thực hiện
        q_pred_all = self.online_net(states_flat)                          # (B*4, 2)
        q_pred     = q_pred_all.gather(1, actions_flat.unsqueeze(1)).squeeze(1)  # (B*4,)

        # ── Q target — Double DQN ─────────────────────────────────────────────
        # Double DQN: online_net chọn action, target_net đánh giá Q
        # Tránh overestimation so với vanilla DQN
        with torch.no_grad():
            # online_net chọn action tốt nhất ở next_state
            next_actions = self.online_net(next_states_flat).argmax(dim=1)  # (B*4,)
            # target_net đánh giá Q của action đó
            q_next = self.target_net(next_states_flat).gather(
                1, next_actions.unsqueeze(1)
            ).squeeze(1)                                                     # (B*4,)
            # Bellman equation
            q_target = rewards_flat + self.gamma * q_next * (1 - dones_flat)  # (B*4,)

        # ── Loss + backprop ───────────────────────────────────────────────────
        loss = self.loss_fn(q_pred, q_target)
        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online_net.parameters(), 10.0)  # tránh gradient explode
        self.optimizer.step()

        # ── Epsilon decay ─────────────────────────────────────────────────────
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        # ── Sync target net định kỳ ───────────────────────────────────────────
        self._update_count += 1
        if self._update_count % self.target_update_freq == 0:
            self.target_net.load_state_dict(self.online_net.state_dict())

        return {"loss": loss.item(), "epsilon": self.epsilon}

    # ── Checkpoint ────────────────────────────────────────────────────────────

    def save(self, path: str):
        torch.save({
            "online_net":    self.online_net.state_dict(),
            "target_net":    self.target_net.state_dict(),
            "optimizer":     self.optimizer.state_dict(),
            "epsilon":       self.epsilon,
            "update_count":  self._update_count,
        }, path)
        print(f"[IDQNAgent] Saved → {path}")

    def load(self, path: str):
        ckpt = torch.load(path, map_location=self.device)
        self.online_net.load_state_dict(ckpt["online_net"])
        self.target_net.load_state_dict(ckpt["target_net"])
        self.optimizer.load_state_dict(ckpt["optimizer"])
        self.epsilon       = ckpt.get("epsilon", self.epsilon_min)
        self._update_count = ckpt.get("update_count", 0)
        print(f"[IDQNAgent] Loaded ← {path}")

    def set_eval(self):
        self.online_net.eval()
        self.epsilon = 0.0

    def set_train(self):
        self.online_net.train()