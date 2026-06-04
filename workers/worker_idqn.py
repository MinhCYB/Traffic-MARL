"""
worker_idqn.py — IDQN worker

TODO (teammate):
    [ ] Implement build_agent() — load IDQNAgent từ checkpoint
    [ ] Verify model_name = "idqn" khớp với server schema
"""

from workers.worker_base import WorkerBase
from training.config import PORT_IDQN, CHECKPOINT_DIR


class IDQNWorker(WorkerBase):

    model_name = "idqn"

    def __init__(self, use_gui: bool = False):
        super().__init__(port=PORT_IDQN, use_gui=use_gui)

    def build_agent(self):
        # TODO: implement — tương tự GATWorker
        # from agents.idqn_agent import IDQNAgent
        # agent = IDQNAgent(...)
        # ckpt = CHECKPOINT_DIR / "idqn_final.pt"
        # if ckpt.exists(): agent.load(str(ckpt))
        # agent.set_eval()
        # return agent
        raise NotImplementedError


if __name__ == "__main__":
    worker = IDQNWorker()
    try:
        worker.run()
    finally:
        worker.close()