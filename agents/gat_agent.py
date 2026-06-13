"""
gat_agent.py — GAT-MARL agent (inference + learning)

Wrap GATMARLNet, xử lý:
- Epsilon-greedy action selection
- Experience storage và update từ replay buffer
- Target network sync
- Save/load checkpoints
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

from agents.base_agent import BaseAgent
from models.gat_marl import GATMARLNet
from environment.state_builder import INTERSECTION_IDS, EDGE_INDEX


class GATAgent(BaseAgent):
    """
    GAT-MARL agent với DQN training.

    Dùng Double DQN:
        Q_target = r + γ * Q_target_net(s', argmax_a Q_online(s', a))
    Tránh overestimation so với vanilla DQN.
    """

    def __init__(
        self,
        state_dim:    int   = 21,
        hidden_dim:   int   = 64,
        num_heads:    int   = 4,
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

        self.gamma         = gamma
        self.epsilon       = epsilon
        self.epsilon_min   = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.target_update_freq = target_update_freq
        self._update_count = 0

        # Online network + target network (Double DQN)
        self.online_net = GATMARLNet(state_dim, hidden_dim, num_heads, num_actions).to(self.device)
        self.target_net = GATMARLNet(state_dim, hidden_dim, num_heads, num_actions).to(self.device)
        self.target_net.load_state_dict(self.online_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.online_net.parameters(), lr=lr)
        self.loss_fn   = nn.SmoothL1Loss()  # Huber loss — ổn định hơn MSE

        # Edge index cố định cho topology 2x2
        self.edge_index = torch.tensor(EDGE_INDEX, dtype=torch.long).to(self.device)

    # ── Inference ─────────────────────────────────────────────────────────────

    def select_actions(self, obs: dict) -> dict[str, int]:
        """
        Epsilon-greedy action selection.

        Args:
            obs: {"states": dict[str, np.ndarray], "node_features": np.ndarray (4, 21)}

        Returns:
            actions: {intersection_id: 0 | 1}
        """
        if np.random.random() < self.epsilon:
            # Random exploration
            return {nid: np.random.randint(0, 2) for nid in INTERSECTION_IDS}

        node_features = obs["node_features"]  # (4, 21)
        x = torch.tensor(node_features, dtype=torch.float32).to(self.device)

        self.online_net.eval()
        with torch.no_grad():
            q_values = self.online_net(x, self.edge_index)  # (4, 2)

        actions = q_values.argmax(dim=-1).cpu().numpy()  # (4,)
        return {nid: int(actions[i]) for i, nid in enumerate(INTERSECTION_IDS)}

    def get_attention_weights(self) -> np.ndarray | None:
        """
        Lấy attention matrix từ forward pass gần nhất.
        Dùng cho dashboard visualization.

        Returns:
            attn_matrix: (4, 4) numpy array hoặc None
        """
        matrix = self.online_net.get_attention_matrix(self.edge_index, n_nodes=4)
        return matrix.cpu().numpy() if matrix is not None else None

    # ── Learning ──────────────────────────────────────────────────────────────

    def update(self, batch: dict) -> dict[str, float]:
        """
        Double DQN update từ một batch.

        Args:
            batch: {
                "states":      (B, 4, 21) float32
                "actions":     (B, 4)     int64
                "rewards":     (B, 4)     float32
                "next_states": (B, 4, 21) float32
                "dones":       (B,)       float32
                "edge_index":  (2, E)     int64  [optional, dùng default nếu thiếu]
            }

        Returns:
            {"loss": float, "epsilon": float}
        """
        self.online_net.train()

        B = batch["states"].shape[0]
        N = len(INTERSECTION_IDS)

        states      = torch.tensor(batch["states"],      dtype=torch.float32).to(self.device)   # (B, 4, 21)
        actions     = torch.tensor(batch["actions"],     dtype=torch.long).to(self.device)       # (B, 4)
        rewards     = torch.tensor(batch["rewards"],     dtype=torch.float32).to(self.device)    # (B, 4)
        next_states = torch.tensor(batch["next_states"], dtype=torch.float32).to(self.device)    # (B, 4, 21)
        dones       = torch.tensor(batch["dones"],       dtype=torch.float32).to(self.device)    # (B,)

        edge_index = self.edge_index

        # Reshape để forward từng sample: (B*4, 21)
        states_flat      = states.view(B * N, -1)
        next_states_flat = next_states.view(B * N, -1)

        # Repeat edge_index cho B samples
        # edge_index: (2, E) → (2, B*E) với offset mỗi graph
        edge_indices = []
        for b in range(B):
            edge_indices.append(edge_index + b * N)
        edge_index_batched = torch.cat(edge_indices, dim=1)  # (2, B*E)

        # Current Q values
        q_all = self.online_net(states_flat, edge_index_batched)   # (B*4, 2)
        q_all = q_all.view(B, N, -1)                               # (B, 4, 2)
        q_taken = q_all.gather(2, actions.unsqueeze(-1)).squeeze(-1)  # (B, 4)

        # Double DQN target
        with torch.no_grad():
            # Online net chọn action
            q_next_online = self.online_net(next_states_flat, edge_index_batched).view(B, N, -1)
            next_actions = q_next_online.argmax(dim=-1, keepdim=True)  # (B, 4, 1)

            # Target net đánh giá action đó
            q_next_target = self.target_net(next_states_flat, edge_index_batched).view(B, N, -1)
            q_next = q_next_target.gather(2, next_actions).squeeze(-1)  # (B, 4)

            # Broadcast dones: (B,) → (B, 4)
            dones_expanded = dones.unsqueeze(1).expand_as(q_next)
            targets = rewards + self.gamma * q_next * (1 - dones_expanded)

        loss = self.loss_fn(q_taken, targets)

        self.optimizer.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.online_net.parameters(), max_norm=10.0)
        self.optimizer.step()

        # Epsilon decay
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

        # Target network sync
        self._update_count += 1
        if self._update_count % self.target_update_freq == 0:
            self.target_net.load_state_dict(self.online_net.state_dict())

        return {"loss": loss.item(), "epsilon": self.epsilon}

    # ── Checkpoint ────────────────────────────────────────────────────────────

    def save(self, path: str):
        torch.save({
            "online_net":   self.online_net.state_dict(),
            "target_net":   self.target_net.state_dict(),
            "optimizer":    self.optimizer.state_dict(),
            "epsilon":      self.epsilon,
            "update_count": self._update_count,
        }, path)

    def load(self, path: str, finetune: bool = False):
        """
        Load checkpoint.
        finetune=True: chỉ load weights (warm-start), reset optimizer + epsilon.
        finetune=False: load toàn bộ state (resume).
        """
        ckpt = torch.load(path, map_location=self.device)
        self.online_net.load_state_dict(ckpt["online_net"])
        self.target_net.load_state_dict(ckpt["target_net"])
        if not finetune:
            self.optimizer.load_state_dict(ckpt["optimizer"])
            self.epsilon       = ckpt.get("epsilon", self.epsilon_min)
            self._update_count = ckpt.get("update_count", 0)
        # finetune: giữ epsilon_start để explore map mới

    def freeze_gat(self):
        """Freeze GAT layer — chỉ train Q-head khi finetune giai đoạn đầu."""
        for name, param in self.online_net.named_parameters():
            if "gat" in name.lower():
                param.requires_grad = False

    def unfreeze_gat(self):
        """Unfreeze GAT layer sau freeze_gat_epochs."""
        for param in self.online_net.parameters():
            param.requires_grad = True

    def set_eval(self):
        self.online_net.eval()
        self.epsilon = 0.0

    def set_train(self):
        self.online_net.train()