"""
worker_fixed.py — Fixed-time worker
"""

from workers.worker_base import WorkerBase
from training.config import PORT_FIXED


class FixedWorker(WorkerBase):

    model_name = "fixed_time"

    def __init__(self, use_gui: bool = False):
        super().__init__(port=PORT_FIXED, use_gui=use_gui)

    def build_agent(self):
        from agents.fixed_agent import FixedAgent
        return FixedAgent()


if __name__ == "__main__":
    worker = FixedWorker()
    try:
        worker.run()
    finally:
        worker.close()