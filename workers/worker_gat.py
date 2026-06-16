"""
worker_gat.py — GAT-MARL worker

Thêm attention_weights vào payload để dashboard visualize.
"""

import numpy as np
from workers.worker_base import WorkerBase
from training.config import PORT_GAT, FINAL_DIR, TOPOLOGY


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
        ckpt = FINAL_DIR / f"gat_marl_{TOPOLOGY}_best.pt"
        if ckpt.exists():
            agent.load(str(ckpt))
            print(f"[gat_marl] Loaded checkpoint: {ckpt}")
        else:
            print(f"[gat_marl] Warning: checkpoint không tồn tại, dùng random weights")
        agent.set_eval()
        return agent

    def get_extra_payload(self) -> dict:
        """Thêm attention matrix (N x N) và comm_this_step vào payload."""
        from environment.state_builder import INTERSECTION_IDS
        n = len(INTERSECTION_IDS)
        attn = self.agent.get_attention_weights()
        if attn is not None:
            # Threshold: 1.5x trung bình softmax (avg = 1/n cho neighbors)
            threshold = 1.5 / n
            comm = int(sum(
                1 for i in range(n) for j in range(n)
                if i != j and attn[i][j] > threshold
            ))
            # Debug log mỗi 50 step để xác nhận attention hoạt động
            if hasattr(self, '_step') and self._step % 50 == 0:
                max_w = float(attn.max())
                n_active = int((attn > threshold).sum()) - n  # trừ diagonal
                print(f"[gat_marl] step={self._step} attn_max={max_w:.3f} "
                      f"threshold={threshold:.3f} active_edges={n_active} comm={comm}")
            return {"attention_weights": attn.tolist(), "comm_this_step": comm}
        print(f"[gat_marl] WARNING: attention_weights is None — model chưa forward?")
        return {"attention_weights": [[0.0] * n for _ in range(n)], "comm_this_step": 0}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true", help="Mở sumo-gui")
    args = parser.parse_args()
    worker = GATWorker(use_gui=args.gui)
    try:
        worker.run()
    finally:
        worker.close()