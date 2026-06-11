"""
worker_idqn.py — IDQN worker cho live demo

Load checkpoint đã train, chạy inference realtime,
gửi metrics lên server mỗi 5s để hiển thị trên dashboard.
"""

from workers.worker_base import WorkerBase
from training.config import (
    PORT_IDQN, CHECKPOINT_DIR,
    STATE_DIM, HIDDEN_DIM, NUM_ACTIONS,
    LR, GAMMA, EPSILON_MIN, EPSILON_DECAY, TARGET_UPDATE_FREQ,
)


class IDQNWorker(WorkerBase):

    model_name = "idqn"

    def __init__(self, use_gui: bool = False):
        super().__init__(port=PORT_IDQN, use_gui=use_gui)

    def build_agent(self):
        """
        Load IDQNAgent từ checkpoint đã train.
        Nếu chưa có checkpoint thì chạy với epsilon=0 (random policy).
        """
        from agents.idqn_agent import IDQNAgent

        agent = IDQNAgent(
            state_dim=STATE_DIM,
            hidden_dim=HIDDEN_DIM,
            num_actions=NUM_ACTIONS,
            lr=LR,
            gamma=GAMMA,
            epsilon=0.0,             # demo mode: không explore
            epsilon_min=EPSILON_MIN,
            epsilon_decay=EPSILON_DECAY,
            target_update_freq=TARGET_UPDATE_FREQ,
        )

        # Load checkpoint nếu có
        ckpt = CHECKPOINT_DIR / "idqn_final.pt"
        if ckpt.exists():
            agent.load(str(ckpt))
            print(f"[IDQNWorker] Loaded checkpoint: {ckpt}")
        else:
            print(f"[IDQNWorker] Không tìm thấy checkpoint tại {ckpt}")
            print(f"[IDQNWorker] Chạy với random policy — hãy train trước bằng:")
            print(f"             python training/train.py --model idqn")

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