"""
replay_buffer.py — Experience replay buffer

Lưu transitions (s, a, r, s', done) và sample random batch.
Dùng chung cho cả GAT-MARL và IDQN.

Mỗi transition lưu data của tất cả 4 agents cùng lúc
→ đảm bảo temporal consistency khi sample.
"""

import numpy as np
from collections import deque
import random

from environment.state_builder import INTERSECTION_IDS, EDGE_INDEX


class ReplayBuffer:
    """
    Circular buffer lưu transitions cho multi-agent setting.

    Transition schema:
        states      : (4, 21)  — node features tất cả agents
        actions     : (4,)     — action mỗi agent
        rewards     : (4,)     — reward mỗi agent
        next_states : (4, 21)
        done        : bool
    """

    def __init__(self, capacity: int = 50_000):
        self.capacity = capacity
        self.buffer: deque = deque(maxlen=capacity)

    def push(
        self,
        states:      np.ndarray,   # (4, 21)
        actions:     dict[str, int],
        rewards:     dict[str, float],
        next_states: np.ndarray,   # (4, 21)
        done:        bool,
    ):
        """Thêm 1 transition vào buffer."""
        action_arr = np.array(
            [actions[nid] for nid in INTERSECTION_IDS], dtype=np.int64
        )
        reward_arr = np.array(
            [rewards[nid] for nid in INTERSECTION_IDS], dtype=np.float32
        )
        self.buffer.append((
            states.astype(np.float32),
            action_arr,
            reward_arr,
            next_states.astype(np.float32),
            np.float32(done),
        ))

    def sample(self, batch_size: int) -> dict:
        """
        Sample random batch.

        Returns:
            {
                "states":      (B, 4, 21)
                "actions":     (B, 4)
                "rewards":     (B, 4)
                "next_states": (B, 4, 21)
                "dones":       (B,)
                "edge_index":  (2, E)  — cố định cho topology 2x2
            }
        """
        batch = random.sample(self.buffer, batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)

        return {
            "states":      np.stack(states),       # (B, 4, 21)
            "actions":     np.stack(actions),       # (B, 4)
            "rewards":     np.stack(rewards),       # (B, 4)
            "next_states": np.stack(next_states),   # (B, 4, 21)
            "dones":       np.array(dones),         # (B,)
            "edge_index":  EDGE_INDEX,              # (2, E)
        }

    def __len__(self) -> int:
        return len(self.buffer)

    def is_ready(self, min_size: int) -> bool:
        return len(self) >= min_size