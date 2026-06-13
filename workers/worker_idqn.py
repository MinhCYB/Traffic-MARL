"""
worker_idqn.py — IDQN worker

Chạy IDQNAgent trong eval mode, POST data lên server mỗi DELTA_TIME giây.
Interface giống GATWorker — không cần thêm extra payload vì IDQN
không có attention weights để visualize.
"""

from workers.worker_base import WorkerBase
from training.config import PORT_IDQN, FINAL_DIR


class IDQNWorker(WorkerBase):

    model_name = "idqn"

    def __init__(self, use_gui: bool = False):
        super().__init__(port=PORT_IDQN, use_gui=use_gui)

    def build_agent(self):
        """
        Khởi tạo IDQNAgent và load checkpoint nếu có.
        Luôn trả về agent ở eval mode (epsilon = 0).
        """
        from agents.idqn_agent import IDQNAgent
        from training.config import (
            STATE_DIM, HIDDEN_DIM, NUM_ACTIONS, EPSILON_MIN,
        )

        agent = IDQNAgent(
            state_dim   = STATE_DIM,
            hidden_dim  = HIDDEN_DIM,
            num_actions = NUM_ACTIONS,
            epsilon     = EPSILON_MIN,  # bắt đầu ở epsilon thấp cho demo
        )

        ckpt = FINAL_DIR / "idqn_mydinh_final.pt"
        if ckpt.exists():
            agent.load(str(ckpt))
            print(f"[idqn] Loaded checkpoint: {ckpt}")
        else:
            print(f"[idqn] Warning: checkpoint không tồn tại tại {ckpt}")
            print(f"[idqn] Chạy với random weights — train trước bằng:")
            print(f"[idqn]   python -m training.train --model idqn")

        agent.set_eval()
        return agent


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true", help="Mở sumo-gui")
    args = parser.parse_args()

    worker = IDQNWorker(use_gui=args.gui)
    try:
        worker.run()
    finally:
        worker.close()