"""
worker_gat.py — GAT-MARL worker

Thêm attention_weights vào payload để dashboard visualize.
"""

import numpy as np
from workers.worker_base import WorkerBase
from training.config import PORT_GAT, CHECKPOINT_DIR


class GATWorker(WorkerBase):

    model_name = "gat_marl"

    def __init__(self, use_gui: bool = False):
        super().__init__(port=PORT_GAT, use_gui=use_gui)

    def build_agent(self):
        from agents.gat_agent import GATAgent
        from training.config import (
            STATE_DIM, HIDDEN_DIM, NUM_HEADS, NUM_ACTIONS,
            EPSILON_MIN,
        )
        agent = GATAgent(
            state_dim=STATE_DIM, hidden_dim=HIDDEN_DIM,
            num_heads=NUM_HEADS, num_actions=NUM_ACTIONS,
            epsilon=EPSILON_MIN,
        )
        ckpt = CHECKPOINT_DIR / "gat_marl_final.pt"
        if ckpt.exists():
            agent.load(str(ckpt))
            print(f"[gat_marl] Loaded checkpoint: {ckpt}")
        else:
            print(f"[gat_marl] Warning: checkpoint không tồn tại, dùng random weights")
        agent.set_eval()
        return agent

    def get_extra_payload(self) -> dict:
        """Thêm attention matrix (4x4) vào payload."""
        attn = self.agent.get_attention_weights()
        if attn is not None:
            return {"attention_weights": attn.tolist()}
        return {"attention_weights": [[0.0] * 4 for _ in range(4)]}


if __name__ == "__main__":
    worker = GATWorker()
    try:
        worker.run()
    finally:
        worker.close()