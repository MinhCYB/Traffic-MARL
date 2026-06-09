"""
worker_base.py — Base worker class

Mỗi worker chạy trong 1 process riêng:
    - Khởi động SUMO trên port riêng
    - Chạy agent inference
    - POST JSON lên server mỗi DELTA_TIME giây
    - Nhận lệnh từ server qua polling (start/inject_accident/reset)
"""

import time
import json
import requests
import numpy as np
from abc import ABC, abstractmethod

from training.config import (
    SERVER_HOST, SERVER_PORT, DELTA_TIME, SEED, TOPOLOGY,
)
from env.traffic_env import TrafficEnv
from env.state_builder import INTERSECTION_IDS, EDGE_INDEX


class WorkerBase(ABC):
    """
    Abstract base worker.

    Subclass override:
        - model_name: str
        - build_agent(): trả về agent đã load checkpoint
        - get_extra_payload(): dict bổ sung vào JSON (vd: attention_weights)
    """

    model_name: str = "base"

    def __init__(self, port: int, use_gui: bool = False):
        self.port    = port
        self.env     = TrafficEnv(port=port, topology=TOPOLOGY, use_gui=use_gui, seed=SEED)
        self.agent   = self.build_agent()
        self.base_url = f"http://{SERVER_HOST}:{SERVER_PORT}"
        self._running = False
        self._step    = 0

    # ── Abstract ──────────────────────────────────────────────────────────────

    @abstractmethod
    def build_agent(self):
        """Khởi tạo và load agent. Trả về agent đã set_eval()."""
        raise NotImplementedError

    def get_extra_payload(self) -> dict:
        """
        Data bổ sung vào JSON payload — override trong subclass.
        Vd: GATWorker trả về attention_weights.
        """
        return {}

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self):
        """Main loop — chạy đến khi nhận lệnh stop."""
        print(f"[{self.model_name}] Worker started, port={self.port}")
        route_type, volume = self._wait_for_start()

        while True:
            try:
                obs  = self.env.reset(route_type=route_type, volume_scale=volume)
                done = False
                self._step = 0

                while not done:
                    actions = self.agent.select_actions(obs)
                    next_obs, rewards, done, info = self.env.step(actions)
                    self._step += 1

                    payload = self._build_payload(next_obs, rewards, info)
                    self._post(payload)

                    cmd = self._poll_command()
                    if cmd and cmd.startswith("reset"):
                        break
                    elif cmd and cmd.startswith("start"):
                        # Restart với config mới
                        parts      = cmd.split(":")
                        route_type = parts[1] if len(parts) > 1 else None
                        volume     = float(parts[2]) if len(parts) > 2 else 1.0
                        break
                    elif cmd and cmd.startswith("inject_accident"):
                        parts      = cmd.split(":")
                        edge_id    = parts[1] if len(parts) > 1 else "SRC1_N02"
                        block_mode = parts[2] if len(parts) > 2 else "1"
                        self.env.inject_accident(edge_id, block_mode)

                    obs = next_obs

                self._post({"mode": self.model_name, "event": "episode_done", "step": self._step})

            except Exception as e:
                print(f"[{self.model_name}] Error: {e} — restarting...")
                try:
                    self.env.close()
                except Exception:
                    pass
                import time
                time.sleep(2)

            route_type, volume = self._wait_for_start()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_payload(self, obs: dict, rewards: dict, info: dict) -> dict:
        """Xây dựng JSON payload theo schema."""
        states = obs["states"]

        intersections = []
        for nid in INTERSECTION_IDS:
            s = states[nid]
            # State layout: density(8) + queue(8) + phase(4) + time(1)
            queue_per_lane   = s[8:16].tolist()
            density_per_lane = s[0:8].tolist()
            phase_onehot     = s[16:20].tolist()
            current_phase    = int(np.argmax(phase_onehot))

            intersections.append({
                "id":              nid,
                "phase":           current_phase,
                "queue_per_lane":  queue_per_lane,
                "density_per_lane": density_per_lane,
                "waiting_time":    round(float(info.get("avg_waiting_time", 0)), 2),
                "reward":          round(float(rewards.get(nid, 0)), 4),
            })

        payload = {
            "mode":           self.model_name,
            "step":           self._step,
            "timestamp":      time.time(),
            "intersections":  intersections,
            "vehicles":       self._read_vehicles(),
            "edge_speeds":    info.get("edge_speeds", {}),
            "accident_edges": info.get("accident_edges", {}),
            "metrics": {
                "avg_speed":        round(info.get("avg_speed", 0), 2),
                "avg_waiting_time": round(info.get("avg_waiting_time", 0), 2),
                "throughput":       info.get("throughput", 0),
                "n_vehicles":       info.get("n_vehicles", 0),
                "global_reward":    round(info.get("global_reward", 0), 4),
            },
        }

        # Merge extra data từ subclass (vd: attention weights)
        payload.update(self.get_extra_payload())
        return payload

    def _read_vehicles(self) -> list[dict]:
        """Đọc vị trí, tốc độ, loại xe từ TraCI để frontend vẽ trên map."""
        try:
            import traci
            vehicles = []
            for vid in traci.vehicle.getIDList():
                try:
                    edge_id  = traci.vehicle.getRoadID(vid)
                    lane_idx = traci.vehicle.getLaneIndex(vid)
                    lane_pos = traci.vehicle.getLanePosition(vid)
                    speed    = traci.vehicle.getSpeed(vid)
                    vtype    = traci.vehicle.getTypeID(vid)
                    angle    = traci.vehicle.getAngle(vid)

                    try:
                        lane_len = traci.lane.getLength(f"{edge_id}_{lane_idx}")
                        pos_norm = round(lane_pos / lane_len, 3) if lane_len > 0 else 0.0
                    except Exception:
                        pos_norm = 0.0

                    vehicles.append({
                        "id":    vid,
                        "edge":  edge_id,
                        "lane":  lane_idx,
                        "pos":   pos_norm,
                        "speed": round(speed * 3.6, 1),
                        "type":  vtype,
                        "angle": round(angle, 1),
                    })
                except Exception:
                    continue
            return vehicles
        except Exception:
            return []

    def _post(self, payload: dict):
        """POST JSON lên server, bỏ qua nếu server chưa sẵn sàng."""
        try:
            requests.post(
                f"{self.base_url}/data",
                json=payload,
                timeout=1.0,
            )
        except requests.exceptions.RequestException:
            pass  # server chưa sẵn sàng hoặc lag — bỏ qua

    def _poll_command(self) -> str | None:
        """GET lệnh từ server command channel."""
        try:
            resp = requests.get(
                f"{self.base_url}/command/{self.model_name}",
                timeout=0.5,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("command")
        except requests.exceptions.RequestException:
            pass
        return None

    def _wait_for_start(self) -> tuple[str | None, float]:
        """Block cho đến khi nhận lệnh start. Trả về (route_type, volume_scale)."""
        print(f"[{self.model_name}] Waiting for start command...")
        while True:
            cmd = self._poll_command()
            if cmd and cmd.startswith("start"):
                parts      = cmd.split(":")
                route_type = parts[1] if len(parts) > 1 and parts[1] else None
                volume     = float(parts[2]) if len(parts) > 2 else 1.0
                print(f"[{self.model_name}] Start received — route={route_type}, volume={volume}x")
                return route_type, volume
            time.sleep(0.5)

    def close(self):
        self.env.close()