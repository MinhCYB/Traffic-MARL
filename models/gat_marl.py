"""
gat_marl.py — GAT-MARL model (CoLight-style, MPLight parameter sharing)

Kiến trúc:
    obs_i (21,)
        │
    [Local Encoder — Shared MLP]   → h_i ∈ R^64
        │
    [GAT Layer — 4 heads]          → h_i' ∈ R^64 (enriched)
        │
    [Q-head — Shared MLP]          → Q(s, keep), Q(s, switch)

Parameter sharing toàn bộ — không có agent_id.
GAT tự differentiate agent qua graph topology.

Attention weights được expose ra ngoài để visualize trên dashboard.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv


# ── Hyperparams mặc định (override từ training/config.py) ────────────────────
STATE_DIM    = 21    # chiều state vector mỗi ngã tư
HIDDEN_DIM   = 64    # hidden size sau encoder
NUM_HEADS    = 4     # số attention heads trong GAT
NUM_ACTIONS  = 2     # 0=keep, 1=switch
DROPOUT      = 0.1


class LocalEncoder(nn.Module):
    """
    Shared MLP: obs (21,) → hidden (64,)
    Dùng chung cho tất cả agents.
    """

    def __init__(self, state_dim: int = STATE_DIM, hidden_dim: int = HIDDEN_DIM):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (N, state_dim) — N agents
        Returns:
            h: (N, hidden_dim)
        """
        return self.net(x)


class GATCommunication(nn.Module):
    """
    GAT layer: aggregate thông tin từ neighbors qua attention.
    Neighbors truyền h_j (encoded vector), không phải raw obs.

    Dùng GATConv với concat=False để output giữ nguyên hidden_dim.
    Attention weights được lưu lại để visualize.
    """

    def __init__(self, hidden_dim: int = HIDDEN_DIM, num_heads: int = NUM_HEADS, dropout: float = DROPOUT):
        super().__init__()
        self.gat = GATConv(
            in_channels=hidden_dim,
            out_channels=hidden_dim,
            heads=num_heads,
            concat=False,       # output = hidden_dim, không phải num_heads * hidden_dim
            dropout=dropout,
            add_self_loops=True,
        )
        self._attention_weights: torch.Tensor | None = None

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """
        Args:
            h          : (N, hidden_dim) — node features sau encoder
            edge_index : (2, E) — COO format adjacency

        Returns:
            h_prime: (N, hidden_dim) — enriched node features
        """
        h_prime, (edge_idx, attn_weights) = self.gat(
            h, edge_index, return_attention_weights=True
        )
        # Lưu attention weights để expose ra ngoài
        # attn_weights shape: (E, num_heads) → average over heads → (E,)
        self._attention_weights = attn_weights.mean(dim=-1).detach()
        return F.relu(h_prime)

    def get_attention_weights(self) -> torch.Tensor | None:
        """
        Trả về attention weights từ forward pass gần nhất.
        Shape: (E,) — E = số edges trong graph
        """
        return self._attention_weights


class QHead(nn.Module):
    """
    Shared MLP: h_i' (64,) → Q values (2,)
    """

    def __init__(self, hidden_dim: int = HIDDEN_DIM, num_actions: int = NUM_ACTIONS):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, num_actions),
        )

    def forward(self, h: torch.Tensor) -> torch.Tensor:
        """
        Args:
            h: (N, hidden_dim)
        Returns:
            q: (N, num_actions)
        """
        return self.net(h)


class GATMARLNet(nn.Module):
    """
    Full GAT-MARL network.

    Forward pass xử lý tất cả N agents đồng thời (batch = graph).
    Một lần forward = một decision step cho toàn bộ 4 ngã tư.
    """

    def __init__(
        self,
        state_dim:  int = STATE_DIM,
        hidden_dim: int = HIDDEN_DIM,
        num_heads:  int = NUM_HEADS,
        num_actions: int = NUM_ACTIONS,
        dropout:    float = DROPOUT,
    ):
        super().__init__()
        self.encoder = LocalEncoder(state_dim, hidden_dim)
        self.gat     = GATCommunication(hidden_dim, num_heads, dropout)
        self.q_head  = QHead(hidden_dim, num_actions)

    def forward(
        self,
        x: torch.Tensor,
        edge_index: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            x          : (N, state_dim) — node features (N = 4 agents)
            edge_index : (2, E) — graph edges

        Returns:
            q_values: (N, num_actions)
        """
        h       = self.encoder(x)           # (N, 64)
        h_prime = self.gat(h, edge_index)   # (N, 64)
        q       = self.q_head(h_prime)      # (N, 2)
        return q

    def get_attention_weights(self) -> torch.Tensor | None:
        """
        Expose attention weights từ GAT layer gần nhất.
        Dùng cho dashboard visualization.

        Returns:
            attn: (E,) hoặc None nếu chưa forward
        """
        return self.gat.get_attention_weights()

    def get_attention_matrix(
        self,
        edge_index: torch.Tensor,
        n_nodes: int = 8,   # default mydinh — luôn truyền tường minh từ agent
    ) -> torch.Tensor:
        """
        Convert attention weights sang dạng matrix (N, N) để dễ visualize.

        Returns:
            attn_matrix: (N, N) — attn_matrix[i][j] = attention từ j đến i
        """
        attn = self.get_attention_weights()
        if attn is None:
            return torch.zeros(n_nodes, n_nodes)

        matrix = torch.zeros(n_nodes, n_nodes)
        src, dst = edge_index
        for k in range(len(src)):
            matrix[dst[k], src[k]] = attn[k]
        return matrix